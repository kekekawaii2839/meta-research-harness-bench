"""Factory source acquisition: candidate pool, per-paper original sources, background papers.

Boundaries:
- Network only through an injectable ``http(url, max_bytes) -> (status, final_url, headers, bytes)``
  callable restricted to an explicit host allowlist (checked before the request and on every
  redirect/final URL). Code comes from an injectable ``git(args, cwd, timeout)`` runner and an
  injectable clone-URL builder. Tests inject both; nothing here reaches the network by itself.
- Downloaded bytes (HTML, PDF, code, notebooks) are stored and hashed only; never executed,
  imported, rendered or checked out as a working tree (``git show`` of selected blobs only).
- arXiv matching accepts only an exact normalized title; anything else is recorded as not found,
  never guessed. Version choice uses the arXiv submission-history dates; v1 date is recorded as the
  earliest *known* public version, not proof of earliest disclosure.
- Every failure is a recorded status string; no content is invented. Existing snapshot directories
  are never overwritten. Hashes are integrity records, not signatures.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path, PurePosixPath

from mrhbench.io import ProtocolError, contained, file_hash, read_json, relative_path, utc_now, write_json

ALLOWED_HOSTS = {"raw.githubusercontent.com", "export.arxiv.org", "arxiv.org"}
USER_AGENT = "MetaResearchMaterialFactory/0.1 (academic benchmark source audit)"
README_NAMES = ("README.md", "README.rst", "README.txt", "README", "readme.md")
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
POOL_FILE_CAP = 1024 * 1024
PAPER_CAP = 30 * 1024 * 1024
CODE_FILE_CAP = 200 * 1024
CODE_MAX_FILES = 300
CODE_TOTAL_CAP = 10 * 1024 * 1024
CODE_EXTS = (".py", ".ipynb", ".md", ".yaml", ".yml", ".toml", ".cfg", ".json", ".sh", ".txt")
ARXIV_INTERVAL = 3.0
GIT_TIMEOUT = 600
_ARXIV_LAST = [float("-inf")]
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_GH_PART = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ----------------------------------------------------------------------------- HTTP
def check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS or p.username or p.password:
        raise ProtocolError(f"URL outside factory allowlist: {url}")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def urllib_http(url: str, max_bytes: int):
    """Default transport: allowlisted HTTPS GET, redirect-checked, read bound max_bytes+1."""
    check_url(url)
    opener = urllib.request.build_opener(_CheckedRedirect())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=60) as r:
            return r.status, r.url, dict(r.headers.items()), r.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        return e.code, url, dict(e.headers.items()) if e.headers else {}, b""


def _get(http, url, max_bytes, *, retries=3, sleep=time.sleep, backoff=2.0):
    """Returns (status_string, bytes|None, final_url). Retries only transient failures."""
    check_url(url)
    last = "fetch_failed"
    for attempt in range(retries):
        try:
            status, final, _headers, body = http(url, max_bytes)
            check_url(final)
        except ProtocolError:
            return "disallowed_redirect", None, url
        except Exception as exc:  # network error: transient
            last = f"fetch_failed:{type(exc).__name__}"
        else:
            if status == 200:
                if len(body) > max_bytes:
                    return "too_large", None, final
                return "ok", body, final
            if status in (404, 410):
                return "not_found", None, final
            last = f"http_{status}"
            if status not in (429, 500, 502, 503, 504):
                return last, None, final
        if attempt + 1 < retries:
            sleep(backoff * (attempt + 1))
    return last, None, url


def _arxiv_wait(sleep, clock):
    wait = _ARXIV_LAST[0] + ARXIV_INTERVAL - clock()
    if wait > 0:
        sleep(wait)
    _ARXIV_LAST[0] = clock()


def _arxiv_get(http, url, max_bytes, sleep, clock):
    _arxiv_wait(sleep, clock)
    return _get(http, url, max_bytes, sleep=sleep)


# ----------------------------------------------------------------------------- arXiv
def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", html_lib.unescape(title or "")).lower()
    t = re.sub(r"\\[a-zA-Z]+", " ", t)  # latex commands such as \emph
    t = "".join(ch if ch.isalnum() else " " for ch in t)
    return " ".join(t.split())


def titles_match(a: str, b: str) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    return bool(na) and na == nb


_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_arxiv_feed(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    out = []
    for entry in root.findall(f"{_ATOM}entry"):
        raw_id = (entry.findtext(f"{_ATOM}id") or "").strip()
        m = re.search(r"arxiv\.org/abs/(.+?)(?:v(\d+))?$", raw_id)
        if not m:
            continue
        out.append({"id": m.group(1), "title": " ".join((entry.findtext(f"{_ATOM}title") or "").split())})
    return out


def exact_arxiv_match(entries: list[dict], title: str):
    """Returns (status, id). Several distinct exact ids are ambiguous, not guessed."""
    ids = sorted({e["id"] for e in entries if titles_match(e["title"], title)})
    if not ids:
        return "arxiv_not_found", None
    if len(ids) > 1:
        return "arxiv_ambiguous", None
    return "found", ids[0]


def parse_submission_history(page: bytes | str) -> list[dict]:
    text = page.decode("utf-8", "replace") if isinstance(page, bytes) else page
    i = text.find("Submission history")
    if i < 0:
        return []
    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", text[i:]))
    seen = {}
    for m in re.finditer(r"\[v(\d+)\]\s+(?:[A-Z][a-z]{2},\s+)?(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})", plain):
        try:
            d = datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)}", "%d %b %Y").date().isoformat()
        except ValueError:
            continue
        seen.setdefault(int(m.group(1)), d)
    return [{"version": v, "date": seen[v]} for v in sorted(seen)]


def choose_version(versions: list[dict], boundary: str, *, inclusive: bool):
    if not _DATE.match(boundary):
        raise ProtocolError("Boundary date must be YYYY-MM-DD")
    ok = [v for v in versions if (v["date"] <= boundary if inclusive else v["date"] < boundary)]
    return max(ok, key=lambda v: v["version"]) if ok else None


def _safe_arxiv_id(aid: str) -> str:
    if not re.fullmatch(r"(\d{4}\.\d{4,5}|[a-z\-]+(\.[A-Z]{2})?/\d{7})", aid or ""):
        raise ProtocolError(f"Unsafe arXiv id: {aid!r}")
    return aid


class _Store:
    """Writes source files under a base directory and builds manifest rows."""
    def __init__(self, base: Path, files_dir: Path):
        self.base, self.files_dir, self.rows, self.ids = base, files_dir, [], set()
        files_dir.mkdir(parents=True, exist_ok=True)

    def add(self, source_id, rel_name, data: bytes, *, url, version, role):
        if not _SAFE_ID.match(source_id) or source_id in self.ids:
            raise ProtocolError(f"Unsafe or duplicate source id: {source_id}")
        target = contained(self.files_dir, rel_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as f:
            f.write(data)
        self.ids.add(source_id)
        row = {"source_id": source_id, "url": url, "version": version, "sha256": file_hash(target),
               "bytes": len(data), "role": role, "local_path": target.relative_to(self.base.resolve()).as_posix()}
        self.rows.append(row)
        return row


def _fetch_arxiv_paper(http, sleep, clock, store: _Store, aid, k, prefix, paper_role, abs_role):
    """Abs page for version k always; HTML else PDF. Returns status string."""
    ver = f"arXiv:{aid}v{k}"
    st, body, url = _arxiv_get(http, f"https://arxiv.org/abs/{aid}v{k}", PAPER_CAP, sleep, clock)
    if st == "ok":
        store.add(f"{prefix}abs_page", f"{prefix}abs_page.html", body, url=url, version=ver, role=abs_role)
    st, body, url = _arxiv_get(http, f"https://arxiv.org/html/{aid}v{k}", PAPER_CAP, sleep, clock)
    if st == "ok" and body.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        store.add(f"{prefix}paper_html", f"{prefix}paper.html", body, url=url, version=ver, role=paper_role[0])
        return "fetched"
    st, body, url = _arxiv_get(http, f"https://arxiv.org/pdf/{aid}v{k}", PAPER_CAP, sleep, clock)
    if st == "ok" and body.startswith(b"%PDF"):
        store.add(f"{prefix}paper_pdf", f"{prefix}paper.pdf", body, url=url, version=ver, role=paper_role[1])
        return "fetched"
    return "paper_fetch_failed"


def _versions(http, aid, sleep, clock):
    st, body, _ = _arxiv_get(http, f"https://arxiv.org/abs/{aid}", PAPER_CAP, sleep, clock)
    return parse_submission_history(body) if st == "ok" else None


def _search_title(http, title, sleep, clock):
    q = urllib.parse.quote(f'ti:"{normalize_title(title)}"')
    st, body, _ = _arxiv_get(http, f"https://export.arxiv.org/api/query?search_query={q}&max_results=5", 4 * 1024 * 1024, sleep, clock)
    if st != "ok":
        return f"arxiv_query_{st}", None
    try:
        return exact_arxiv_match(parse_arxiv_feed(body), title)
    except ET.ParseError:
        return "arxiv_query_unparseable", None


# ----------------------------------------------------------------------------- git
def subprocess_git(args, cwd=None, timeout=GIT_TIMEOUT):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "GCM_INTERACTIVE": "never"}
    r = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-c", "credential.helper=", *args],
                       cwd=cwd, capture_output=True, timeout=timeout, env=env)
    return r.returncode, r.stdout, r.stderr


def github_clone_url(owner, name):
    return f"https://github.com/{owner}/{name}.git"


def _code_tier(path: str):
    base = PurePosixPath(path).name.lower()
    if base.startswith("readme"):
        return 0, "readme"
    if base.startswith(("license", "licence", "copying")):
        return 1, "license_file"
    for i, ext in enumerate(CODE_EXTS):
        if base.endswith(ext):
            return 2 + i, "code_file"
    return None, None


def parse_ls_tree_z(out: bytes) -> list[dict]:
    rows = []
    for rec in out.split(b"\x00"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, typ, sha, size = meta.decode().split()
        rows.append({"mode": mode, "type": typ, "sha": sha, "size": None if size == "-" else int(size),
                     "path": path.decode("utf-8", "surrogateescape")})
    return rows


def select_code_files(entries: list[dict]):
    """Priority/cap selection over ls-tree entries. Returns (selected [(entry, role)], skipped counts)."""
    skipped, cands = {}, []
    bump = lambda k: skipped.__setitem__(k, skipped.get(k, 0) + 1)
    for e in entries:
        if e["type"] != "blob" or e["mode"] == "120000":
            bump("not_regular_blob"); continue
        tier, role = _code_tier(e["path"])
        if tier is None:
            bump("unsupported_type"); continue
        try:
            relative_path(e["path"])
        except ProtocolError:
            bump("unsafe_path"); continue
        if e["size"] is None or e["size"] > CODE_FILE_CAP:
            bump("file_too_large"); continue
        cands.append((tier, e["path"].count("/"), e["path"], e, role))
    cands.sort(key=lambda c: c[:3])
    chosen, total, lowered = [], 0, set()
    for _tier, _depth, path, e, role in cands:
        if len(chosen) >= CODE_MAX_FILES:
            bump("max_files_cap"); continue
        if total + e["size"] > CODE_TOTAL_CAP:
            bump("total_bytes_cap"); continue
        if path.lower() in lowered:
            bump("case_collision"); continue
        lowered.add(path.lower()); chosen.append((e, role)); total += e["size"]
    return chosen, skipped


def _rmtree(path):
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def _fetch_code(repo, conference_end, git, clone_url, store: _Store) -> dict:
    info = {"status": None, "url": f"https://github.com/{repo['owner']}/{repo['name']}", "commit": None,
            "commit_date": None, "files_included": 0, "files_skipped": {}}
    tmp = Path(tempfile.mkdtemp(prefix="mrh-clone-"))
    clone = tmp / "repo"
    try:
        try:
            rc, _o, err = git(["clone", "--filter=blob:none", "--no-checkout", "--quiet",
                               clone_url(repo["owner"], repo["name"]), str(clone)], None, GIT_TIMEOUT)
            if rc != 0:
                info["status"] = "clone_failed"; info["error"] = err.decode("utf-8", "replace")[-500:]; return info
            rc, out, _ = git(["-C", str(clone), "rev-list", "-1", f"--before={conference_end}T23:59:59Z", "HEAD"], None, 120)
            commit = out.decode().strip() if rc == 0 else ""
            if not re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", commit):
                info["status"] = "no_commit_before_conference_end" if rc == 0 else "rev_list_failed"; return info
            info["commit"] = commit
            _rc, out, _ = git(["-C", str(clone), "show", "-s", "--format=%cI", commit], None, 120)
            info["commit_date"] = out.decode().strip() or None
            ver = f"git:{commit}"
            rc1, tree_txt, _ = git(["-C", str(clone), "ls-tree", "-r", "--long", commit], None, GIT_TIMEOUT)
            rc2, tree_z, _ = git(["-C", str(clone), "ls-tree", "-r", "--long", "-z", commit], None, GIT_TIMEOUT)
            if rc1 or rc2:
                info["status"] = "tree_failed"; return info
            store.add("code_tree", "code_tree.txt", tree_txt, url=info["url"], version=ver, role="code_tree")
            chosen, skipped = select_code_files(parse_ls_tree_z(tree_z))
            n = 0
            for e, role in chosen:
                rc, data, _ = git(["-C", str(clone), "show", f"{commit}:{e['path']}"], None, GIT_TIMEOUT)
                if rc != 0 or len(data) > CODE_FILE_CAP:
                    skipped["show_failed"] = skipped.get("show_failed", 0) + 1; continue
                n += 1
                try:
                    store.add(f"code_{n:04d}", f"code/{e['path']}", data,
                              url=f"{info['url']}/blob/{commit}/{urllib.parse.quote(e['path'])}", version=ver, role=role)
                except (ProtocolError, OSError):
                    n -= 1; skipped["write_failed"] = skipped.get("write_failed", 0) + 1
            info.update(status="fetched", files_included=n, files_skipped=skipped)
            return info
        except subprocess.TimeoutExpired:
            info["status"] = "git_timeout"; return info
    finally:
        _rmtree(tmp)


# ----------------------------------------------------------------------------- public API
def normalize_repo(candidates) -> dict | None:
    for c in candidates or []:
        url = c.get("url") if isinstance(c, dict) else c
        p = urllib.parse.urlparse(url or "")
        if p.scheme not in ("http", "https") or (p.hostname or "").lower() not in ("github.com", "www.github.com"):
            continue
        parts = [x for x in p.path.split("/") if x]
        if len(parts) < 2:
            continue
        owner, name = parts[0], re.sub(r"\.git$", "", parts[1])
        if _GH_PART.match(owner) and _GH_PART.match(name) and name not in (".", ".."):
            return {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}"}
    return None


def _fetch_first(http, owner, name, names, max_bytes, sleep):
    statuses = []
    for fname in names:
        url = f"https://raw.githubusercontent.com/{owner}/{name}/HEAD/{fname}"
        st, body, final = _get(http, url, max_bytes, sleep=sleep)
        if st == "ok":
            return "found", fname, body, url
        statuses.append(st)
        if st != "not_found":
            return st, fname, None, url
    return "not_found", None, None, None


def _reusable(out_dir: Path, rec) -> bool:
    if not rec:
        return False
    if rec.get("status") == "not_found":
        return True
    if rec.get("status") != "found" or not rec.get("path"):
        return False
    try:
        return file_hash(contained(out_dir, rec["path"], must_exist=True)) == rec.get("sha256")
    except (ProtocolError, OSError):
        return False


def build_pool(candidate_index: Path, iclr_json: Path, out_dir: Path, *, fetch_readmes=True, http=None,
               sleep=time.sleep, polite_interval=0.2, checkpoint_every=25) -> dict:
    http = http or urllib_http
    out_dir.mkdir(parents=True, exist_ok=True)
    events = read_json(iclr_json)["results"]
    abstracts = {int(e["id"]): e.get("abstract") for e in events if str(e.get("id", "")).isdigit()}
    cands = [json.loads(line) for line in candidate_index.read_text(encoding="utf-8").splitlines() if line.strip()]
    pool_path = out_dir / "candidates.jsonl"
    previous = {}
    if pool_path.exists():
        previous = {r["project_id"]: r for r in map(json.loads, pool_path.read_text(encoding="utf-8").splitlines()) if r}
    rows, failures, fetched_any = [], [], 0

    def dump(done):
        ids = {r["project_id"] for r in done}
        rest = [previous[c["project_id"]] for c in cands if c["project_id"] in previous and c["project_id"] not in ids]
        tmp = pool_path.with_name(pool_path.name + ".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in done + rest), encoding="utf-8")
        os.replace(tmp, pool_path)

    for c in cands:
        pid = c["project_id"]
        if not _SAFE_ID.match(pid):
            raise ProtocolError(f"Unsafe project id {pid!r}")
        repo = normalize_repo(c.get("repository_candidates"))
        prev = previous.get(pid, {})
        row = {"project_id": pid, "forum_id": c.get("forum_id"), "title": c.get("title"),
               "abstract": abstracts.get(c.get("source_event_id")), "topic": c.get("topic"),
               "topic_group": c.get("topic_group"), "decision": c.get("decision"),
               "openreview_url": c.get("openreview_url"), "repo": repo, "readme": None, "license_file": None}
        if repo and fetch_readmes:
            same_repo = prev.get("repo") == repo
            for key, names, sub, ext_of in (
                    ("readme", README_NAMES, "readmes", lambda f: {"README.rst": "rst", "README.txt": "txt", "README": "txt"}.get(f, "md")),
                    ("license_file", LICENSE_NAMES, "licenses", lambda f: "txt")):
                if same_repo and _reusable(out_dir, prev.get(key)):
                    row[key] = prev[key]; continue
                if fetched_any:
                    sleep(polite_interval)
                fetched_any += 1
                st, fname, body, url = _fetch_first(http, repo["owner"], repo["name"], names, POOL_FILE_CAP, sleep)
                rec = {"status": st, "url": url, "path": None, "sha256": None}
                if key == "readme":
                    rec["bytes"] = None
                if body is not None:
                    rel = f"{sub}/{pid}.{ext_of(fname)}"
                    target = out_dir / sub / f"{pid}.{ext_of(fname)}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(body)
                    rec.update(path=rel, sha256=file_hash(target))
                    if key == "readme":
                        rec["bytes"] = len(body)
                elif st != "not_found":
                    failures.append({"project_id": pid, "kind": key, "status": st})
                row[key] = rec
        rows.append(row)
        if checkpoint_every and len(rows) % checkpoint_every == 0:
            dump(rows)
    dump(rows)
    count = lambda key: {s: sum(1 for r in rows if (r[key] or {}).get("status") == s)
                         for s in sorted({(r[key] or {}).get("status") for r in rows if r[key]})}
    summary = {"schema_version": "factory-pool-1", "generated_at": utc_now(),
               "inputs": {"candidate_index": {"path": candidate_index.name, "sha256": file_hash(candidate_index)},
                          "iclr_json": {"path": iclr_json.name, "sha256": file_hash(iclr_json)}},
               "counts": {"candidates": len(rows), "with_abstract": sum(1 for r in rows if r["abstract"]),
                          "with_repo": sum(1 for r in rows if r["repo"]), "readme": count("readme"),
                          "license_file": count("license_file")},
               "failures": failures, "fetch_readmes": fetch_readmes,
               "note": "README/LICENSE come from repository HEAD at fetch time, not a paper-time commit."}
    write_json(out_dir / "pool_summary.json", summary)
    return summary


def fetch_paper_sources(candidate_row: dict, paper_dir: Path, *, conference_end="2025-04-30", http=None, git=None,
                        clone_url=github_clone_url, sleep=time.sleep, clock=time.monotonic) -> dict:
    http, git = http or urllib_http, git or subprocess_git
    if not _DATE.match(conference_end):
        raise ProtocolError("conference_end must be YYYY-MM-DD")
    src = paper_dir / "sources"
    if src.exists():
        raise ProtocolError("paper_dir/sources must be new")
    src.mkdir(parents=True)
    store = _Store(paper_dir, src / "files")
    arxiv = {"status": None, "id": None, "versions": [], "chosen_version": None,
             "earliest_known_public_version": None, "note": "earliest_known_public_version is not proof of earliest disclosure"}
    st, aid = _search_title(http, candidate_row.get("title") or "", sleep, clock)
    arxiv["status"] = st
    if st == "found":
        arxiv["id"] = aid = _safe_arxiv_id(aid)
        versions = _versions(http, aid, sleep, clock)
        if not versions:
            arxiv["status"] = "submission_history_unavailable"
        else:
            arxiv["versions"] = versions
            arxiv["earliest_known_public_version"] = min(versions, key=lambda v: v["version"])
            chosen = choose_version(versions, conference_end, inclusive=True)
            if not chosen:
                arxiv["status"] = "no_version_before_conference_end"
            else:
                arxiv["chosen_version"] = chosen["version"]
                arxiv["status"] = _fetch_arxiv_paper(http, sleep, clock, store, aid, chosen["version"], "",
                                                     ("paper_html", "paper_pdf"), "paper_abs_page")
    repo = candidate_row.get("repo")
    if repo:
        repo_info = _fetch_code(repo, conference_end, git, clone_url, store)
    else:
        repo_info = {"status": "no_repo", "url": None, "commit": None, "commit_date": None,
                     "files_included": 0, "files_skipped": {}}
    manifest = {"schema_version": "factory-sources-1", "project_id": candidate_row.get("project_id"),
                "fetched_at": utc_now(), "conference_end": conference_end, "arxiv": arxiv, "repo": repo_info,
                "sources": store.rows}
    write_json(src / "manifest.json", manifest)
    return manifest


def _arxiv_title_by_id(http, aid, sleep, clock):
    st, body, _ = _arxiv_get(http, f"https://export.arxiv.org/api/query?id_list={aid}&max_results=1", 4 * 1024 * 1024, sleep, clock)
    if st != "ok":
        return None
    try:
        entries = [e for e in parse_arxiv_feed(body) if e["id"] == aid]
    except ET.ParseError:
        return None
    return entries[0]["title"] if entries else None


def fetch_background(requests: list[dict], dest_dir: Path, *, base_dir: Path | None = None, http=None,
                     sleep=time.sleep, clock=time.monotonic) -> dict:
    http = http or urllib_http
    base_dir = base_dir or dest_dir.parent
    if dest_dir.exists():
        raise ProtocolError("Background destination must be new")
    ids = [r.get("request_id") for r in requests]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and _SAFE_ID.match(i) for i in ids):
        raise ProtocolError("Request ids must be unique safe ids")
    for r in requests:
        if not _DATE.match(r.get("cutoff_date") or "") or not r.get("title"):
            raise ProtocolError(f"Request {r['request_id']} needs title and YYYY-MM-DD cutoff_date")
    dest_dir.mkdir(parents=True)
    if not dest_dir.resolve().is_relative_to(base_dir.resolve()):
        raise ProtocolError("dest_dir must be inside base_dir")
    store = _Store(base_dir, dest_dir)
    results = []
    for r in requests:
        res = {"request_id": r["request_id"], "title": r["title"], "cutoff_date": r["cutoff_date"], "status": None,
               "arxiv_id": None, "versions": [], "chosen_version": None, "source_ids": []}
        n_before = len(store.rows)
        if r.get("arxiv_id"):
            aid = _safe_arxiv_id(r["arxiv_id"])
            got = _arxiv_title_by_id(http, aid, sleep, clock)
            status = "found" if got and titles_match(got, r["title"]) else "not_found"
        else:
            st, aid = _search_title(http, r["title"], sleep, clock)
            status = "found" if st == "found" else ("fetch_failed" if st.startswith("arxiv_query_") else "not_found")
            aid = _safe_arxiv_id(aid) if aid else None
        if status == "found":
            res["arxiv_id"] = aid
            versions = _versions(http, aid, sleep, clock)
            if not versions:
                status = "fetch_failed"
            else:
                res["versions"] = versions
                chosen = choose_version(versions, r["cutoff_date"], inclusive=False)
                if not chosen:
                    status = "no_version_before_cutoff"
                else:
                    res["chosen_version"] = chosen["version"]
                    got = _fetch_arxiv_paper(http, sleep, clock, store, aid, chosen["version"], f"{r['request_id']}_",
                                             ("background_paper", "background_paper"), "background_abs_page")
                    status = "found" if got == "fetched" else "fetch_failed"
        res["status"] = status
        res["source_ids"] = [row["source_id"] for row in store.rows[n_before:]]
        results.append(res)
    manifest = {"schema_version": "factory-background-1", "fetched_at": utc_now(),
                "base_dir_note": "local_path is relative to base_dir", "requests": results, "sources": store.rows}
    write_json(dest_dir / "manifest.json", manifest)
    return manifest
