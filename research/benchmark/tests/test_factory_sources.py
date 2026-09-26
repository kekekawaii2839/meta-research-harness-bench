import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench import factory_sources as fs
from mrhbench.io import ProtocolError, file_hash, read_json, write_json

TITLE = "Scalar Regression Adaptation: A {Simple} Approach"
AID = "2410.01234"


def feed(*entries):
    body = "".join(f"<entry><id>http://arxiv.org/abs/{i}v{v}</id><title>{t}</title></entry>" for i, v, t in entries)
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'.encode()


ABS = b"""<html><body><div class="submission-history">
<h2>Submission history</h2> From: A. Author [<a href="/show-email/x">view email</a>]<br/>
<strong><a href="/abs/2410.01234v1" rel="nofollow">[v1]</a></strong> Wed, 2 Oct 2024 17:59:59 UTC (1,234 KB)<br/>
<strong><a href="/abs/2410.01234v2" rel="nofollow">[v2]</a></strong> Mon, 3 Feb 2025 10:00:00 UTC (2,345 KB)<br/>
<strong>[v3]</strong> Thu, 1 May 2025 09:00:00 UTC (2,400 KB)<br/>
</div></body></html>"""


class FakeHTTP:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, max_bytes):
        self.calls.append(url)
        if url in self.routes:
            return (*self.routes[url][:1], url, {}, self.routes[url][1])
        keys = sorted((k for k in self.routes if "/api/query" in k and url.startswith(k)), key=len)
        if keys:
            status, body = self.routes[keys[-1]]
            return status, url, {}, body
        return 404, url, {}, b""


def arxiv_routes(html=True):
    r = {"https://export.arxiv.org/api/query": (200, feed((AID, 3, "Scalar  Regression\n Adaptation: a Simple approach"))),
         f"https://arxiv.org/abs/{AID}v2": (200, b"<html>abs v2</html>"),
         f"https://arxiv.org/abs/{AID}": (200, ABS),
         f"https://arxiv.org/pdf/{AID}v2": (200, b"%PDF-1.5 fake")}
    if html:
        r[f"https://arxiv.org/html/{AID}v2"] = (200, b"<!DOCTYPE html><html>paper</html>")
    return r


NOSLEEP = dict(sleep=lambda s: None, clock=lambda: 0.0)


def git(*args, cwd, date=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True).stdout


def make_repo(root: Path):
    root.mkdir()
    git("init", "-q", "-b", "main", cwd=root)
    git("config", "core.autocrlf", "false", cwd=root)
    (root / "README.md").write_text("old readme\n")
    (root / "LICENSE").write_text("MIT\n")
    (root / "src").mkdir()
    (root / "src" / "model.py").write_text("print('never executed')\n")
    (root / "big.py").write_bytes(b"x" * (fs.CODE_FILE_CAP + 1))
    (root / "weights.bin").write_bytes(b"\x00\x01")
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "one", cwd=root, date="2025-03-01T12:00:00Z")
    (root / "README.md").write_text("new readme after conference\n")
    git("commit", "-q", "-am", "two", cwd=root, date="2025-06-01T12:00:00Z")
    return git("rev-list", "-1", "HEAD~1", cwd=root).decode().strip()


class TitleAndVersionTests(unittest.TestCase):
    def test_exact_title_only(self):
        self.assertTrue(fs.titles_match("Deep  Nets: \\emph{Fast}!", "deep nets fast"))
        entries = [{"id": "1", "title": "Scalar Regression Adaptation: A Simple Approach Revisited"},
                   {"id": "2", "title": "Scalar Regression Adaption: A Simple Approach"}]
        self.assertEqual(fs.exact_arxiv_match(entries, TITLE), ("arxiv_not_found", None))
        entries.append({"id": "3", "title": "scalar regression adaptation a simple approach"})
        self.assertEqual(fs.exact_arxiv_match(entries, TITLE), ("found", "3"))
        entries.append({"id": "4", "title": TITLE})
        self.assertEqual(fs.exact_arxiv_match(entries, TITLE)[0], "arxiv_ambiguous")
        self.assertFalse(fs.titles_match("", ""))

    def test_submission_history_and_boundaries(self):
        v = fs.parse_submission_history(ABS)
        self.assertEqual(v, [{"version": 1, "date": "2024-10-02"}, {"version": 2, "date": "2025-02-03"},
                             {"version": 3, "date": "2025-05-01"}])
        self.assertEqual(fs.choose_version(v, "2025-04-30", inclusive=True)["version"], 2)
        self.assertEqual(fs.choose_version(v, "2025-05-01", inclusive=True)["version"], 3)
        self.assertEqual(fs.choose_version(v, "2025-05-01", inclusive=False)["version"], 2)
        self.assertEqual(fs.choose_version(v, "2025-02-03", inclusive=False)["version"], 1)
        self.assertIsNone(fs.choose_version(v, "2024-10-02", inclusive=False))
        self.assertEqual(fs.parse_submission_history(b"<html>no history</html>"), [])

    def test_repo_normalization(self):
        self.assertEqual(fs.normalize_repo([{"url": "https://example.com/a/b"}, {"url": "https://github.com/Own/Repo.git/"}]),
                         {"owner": "Own", "name": "Repo", "url": "https://github.com/Own/Repo"})
        self.assertIsNone(fs.normalize_repo([{"url": "https://github.com/onlyowner"}]))


class PathAndSelectionTests(unittest.TestCase):
    def test_unsafe_paths_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = fs._Store(Path(tmp), Path(tmp) / "files")
            for bad in ("../x.py", "/abs.py", "C:/x.py", "a\\b.py", "CON.py", "a/./b.py"):
                with self.assertRaises(ProtocolError):
                    store.add("code_0001", f"code/{bad}", b"x", url="u", version="v", role="code_file")
            self.assertEqual(store.rows, [])

    def test_priority_and_caps(self):
        e = lambda p, size=10, typ="blob", mode="100644": {"path": p, "size": size, "type": typ, "mode": mode, "sha": "0"}
        entries = [e(f"pkg/m{i:03d}.py") for i in range(400)] + [
            e("docs/README.md"), e("LICENSE"), e("data.csv"), e("huge.py", fs.CODE_FILE_CAP + 1), e("../evil.py"),
            e("link.py", mode="120000"), e("sub", typ="commit"), e("Readme.MD"), e("readme.md")]
        chosen, skipped = fs.select_code_files(entries)
        paths = [c[0]["path"] for c in chosen]
        self.assertEqual(len(chosen), fs.CODE_MAX_FILES)
        self.assertEqual(paths[:3], ["Readme.MD", "docs/README.md", "LICENSE"])
        self.assertEqual([c[1] for c in chosen[:3]], ["readme", "readme", "license_file"])
        self.assertEqual(skipped["case_collision"], 1)
        self.assertEqual(skipped["unsupported_type"], 1)
        self.assertEqual(skipped["file_too_large"], 1)
        self.assertEqual(skipped["unsafe_path"], 1)
        self.assertEqual(skipped["not_regular_blob"], 2)
        self.assertEqual(skipped["max_files_cap"], 404 - 1 - fs.CODE_MAX_FILES)
        big = [e(f"f{i}.py", fs.CODE_FILE_CAP) for i in range(60)]
        chosen, skipped = fs.select_code_files(big)
        self.assertLessEqual(sum(c[0]["size"] for c in chosen), fs.CODE_TOTAL_CAP)
        self.assertGreater(skipped["total_bytes_cap"], 0)


class PaperSourcesTests(unittest.TestCase):
    def test_html_then_pdf_fallback_and_commit_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            old = make_repo(tmp / "origin")
            row = {"project_id": "iclr2025-x", "title": TITLE, "repo": {"owner": "o", "name": "n", "url": "https://github.com/o/n"}}
            http = FakeHTTP(arxiv_routes(html=True))
            m = fs.fetch_paper_sources(row, tmp / "p1", http=http, git=fs.subprocess_git,
                                       clone_url=lambda o, n: str(tmp / "origin"), **NOSLEEP)
            self.assertEqual(m["arxiv"]["status"], "fetched")
            self.assertEqual(m["arxiv"]["chosen_version"], 2)
            self.assertEqual(m["arxiv"]["earliest_known_public_version"], {"version": 1, "date": "2024-10-02"})
            roles = {s["role"] for s in m["sources"]}
            self.assertIn("paper_html", roles); self.assertNotIn("paper_pdf", roles); self.assertIn("paper_abs_page", roles)
            self.assertEqual(m["repo"]["status"], "fetched")
            self.assertEqual(m["repo"]["commit"], old)
            by_path = {s["local_path"]: s for s in m["sources"]}
            readme = tmp / "p1" / "sources/files/code/README.md"
            self.assertEqual(readme.read_text(), "old readme\n")
            self.assertEqual(by_path["sources/files/code/README.md"]["role"], "readme")
            self.assertEqual(by_path["sources/files/code/LICENSE"]["role"], "license_file")
            self.assertEqual(by_path["sources/files/code/src/model.py"]["role"], "code_file")
            self.assertEqual(by_path["sources/files/code_tree.txt"]["version"], f"git:{old}")
            self.assertFalse((tmp / "p1/sources/files/code/big.py").exists())
            self.assertEqual(m["repo"]["files_skipped"], {"file_too_large": 1, "unsupported_type": 1})
            for s in m["sources"]:
                self.assertEqual(file_hash(tmp / "p1" / s["local_path"]), s["sha256"])
            self.assertEqual(len({s["source_id"] for s in m["sources"]}), len(m["sources"]))
            self.assertEqual(read_json(tmp / "p1/sources/manifest.json"), m)
            self.assertTrue(all(urllib.parse.urlparse(u).hostname in fs.ALLOWED_HOSTS for u in http.calls))
            with self.assertRaises(ProtocolError):
                fs.fetch_paper_sources(row, tmp / "p1", http=http, git=fs.subprocess_git, **NOSLEEP)
            # PDF fallback; repo whose history starts after the conference end.
            m2 = fs.fetch_paper_sources(row, tmp / "p2", conference_end="2025-02-01", http=FakeHTTP(arxiv_routes(html=False)),
                                        git=fs.subprocess_git, clone_url=lambda o, n: str(tmp / "origin"), **NOSLEEP)
            self.assertEqual(m2["arxiv"]["chosen_version"], 1)
            self.assertEqual(m2["arxiv"]["status"], "paper_fetch_failed")  # no html/pdf v1 route: recorded, not invented
            self.assertEqual([s["role"] for s in m2["sources"]], [])
            self.assertEqual(m2["repo"]["status"], "no_commit_before_conference_end")
            routes = arxiv_routes(html=False)
            m3 = fs.fetch_paper_sources({**row, "repo": None}, tmp / "p3", http=FakeHTTP(routes), **NOSLEEP)
            self.assertEqual([s["role"] for s in m3["sources"]], ["paper_abs_page", "paper_pdf"])
            self.assertEqual(m3["repo"]["status"], "no_repo")

    def test_title_mismatch_never_guesses(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = {"https://export.arxiv.org/api/query": (200, feed((AID, 1, TITLE + " Revisited")))}
            http = FakeHTTP(routes)
            m = fs.fetch_paper_sources({"project_id": "x", "title": TITLE, "repo": None}, Path(tmp) / "p", http=http, **NOSLEEP)
            self.assertEqual(m["arxiv"]["status"], "arxiv_not_found")
            self.assertEqual(m["sources"], [])
            self.assertEqual(len(http.calls), 1)

    def test_arxiv_politeness_interval(self):
        waits, now = [], [100.0]
        fs._ARXIV_LAST[0] = float("-inf")
        sleep = lambda s: (waits.append(s), now.__setitem__(0, now[0] + s))
        fs._arxiv_wait(sleep, lambda: now[0]); fs._arxiv_wait(sleep, lambda: now[0])
        self.assertEqual(waits, [fs.ARXIV_INTERVAL])
        fs._ARXIV_LAST[0] = float("-inf")


class BackgroundTests(unittest.TestCase):
    def test_strict_cutoff_and_id_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = {**arxiv_routes(), f"https://arxiv.org/abs/{AID}v1": (200, b"<html>v1</html>"),
                      f"https://arxiv.org/pdf/{AID}v1": (200, b"%PDF-1.4 v1")}
            routes["https://export.arxiv.org/api/query?id_list=2410.99999"] = (200, feed(("2410.99999", 1, "Other Paper")))
            reqs = [{"request_id": "a", "title": TITLE, "cutoff_date": "2025-02-03"},
                    {"request_id": "b", "title": TITLE, "cutoff_date": "2024-10-02", "arxiv_id": AID},
                    {"request_id": "c", "title": TITLE, "cutoff_date": "2025-01-01", "arxiv_id": "2410.99999"}]
            routes[f"https://export.arxiv.org/api/query?id_list={AID}"] = (200, feed((AID, 3, TITLE)))
            m = fs.fetch_background(reqs, Path(tmp) / "bg", http=FakeHTTP(routes), **NOSLEEP)
            st = {r["request_id"]: r for r in m["requests"]}
            self.assertEqual(st["a"]["status"], "found"); self.assertEqual(st["a"]["chosen_version"], 1)
            self.assertEqual(st["b"]["status"], "no_version_before_cutoff")
            self.assertEqual(st["c"]["status"], "not_found")
            paper = [s for s in m["sources"] if s["role"] == "background_paper"]
            self.assertEqual(len(paper), 1)
            self.assertEqual(paper[0]["url"], f"https://arxiv.org/pdf/{AID}v1")
            self.assertTrue(paper[0]["local_path"].startswith("bg/"))
            self.assertEqual(file_hash(Path(tmp) / paper[0]["local_path"]), paper[0]["sha256"])
            with self.assertRaises(ProtocolError):
                fs.fetch_background(reqs, Path(tmp) / "bg", http=FakeHTTP(routes), **NOSLEEP)


class PoolTests(unittest.TestCase):
    def test_resumable_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cands = [{"project_id": "iclr2025-a", "forum_id": "a", "title": "A", "topic": "t", "topic_group": "g",
                      "decision": "Accept (Poster)", "openreview_url": "https://openreview.net/forum?id=a",
                      "repository_candidates": [{"url": "https://github.com/o/r", "slug": "o/r"}], "source_event_id": 7},
                     {"project_id": "iclr2025-b", "forum_id": "b", "title": "B", "repository_candidates": [], "source_event_id": 8}]
            (tmp / "idx.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cands), encoding="utf-8")
            write_json(tmp / "iclr.json", {"results": [{"id": 7, "abstract": "Abs A"}]})
            routes = {"https://raw.githubusercontent.com/o/r/HEAD/README.rst": (200, b"readme"),
                      "https://raw.githubusercontent.com/o/r/HEAD/LICENSE.txt": (500, b"")}
            http = FakeHTTP(routes)
            s = fs.build_pool(tmp / "idx.jsonl", tmp / "iclr.json", tmp / "pool", http=http, sleep=lambda x: None)
            rows = [json.loads(l) for l in (tmp / "pool/candidates.jsonl").read_text(encoding="utf-8").splitlines()]
            a = rows[0]
            self.assertEqual(a["abstract"], "Abs A"); self.assertIsNone(rows[1]["abstract"])
            self.assertEqual(a["readme"]["status"], "found"); self.assertEqual(a["readme"]["path"], "readmes/iclr2025-a.rst")
            self.assertEqual(a["readme"]["bytes"], 6)
            self.assertEqual(a["license_file"]["status"], "http_500")
            self.assertEqual(s["counts"]["with_repo"], 1)
            self.assertEqual(s["failures"], [{"project_id": "iclr2025-a", "kind": "license_file", "status": "http_500"}])
            self.assertIsNone(rows[1]["repo"]); self.assertIsNone(rows[1]["readme"])
            self.assertEqual(s["inputs"]["iclr_json"]["sha256"], file_hash(tmp / "iclr.json"))
            # Second run: README reused (hash ok); failed license retried.
            routes["https://raw.githubusercontent.com/o/r/HEAD/LICENSE.txt"] = (200, b"MIT")
            http2 = FakeHTTP(routes)
            fs.build_pool(tmp / "idx.jsonl", tmp / "iclr.json", tmp / "pool", http=http2, sleep=lambda x: None)
            self.assertFalse(any("README" in u for u in http2.calls))
            self.assertTrue(any(u.endswith("LICENSE.txt") for u in http2.calls))
            # Tampered README file is refetched.
            (tmp / "pool/readmes/iclr2025-a.rst").write_bytes(b"tampered")
            http3 = FakeHTTP(routes)
            fs.build_pool(tmp / "idx.jsonl", tmp / "iclr.json", tmp / "pool", http=http3, sleep=lambda x: None)
            self.assertTrue(any("README" in u for u in http3.calls))
            self.assertFalse(any(u.endswith("LICENSE.txt") for u in http3.calls))
            self.assertEqual((tmp / "pool/readmes/iclr2025-a.rst").read_bytes(), b"readme")

    def test_disallowed_host_and_no_network_default(self):
        with self.assertRaises(ProtocolError):
            fs.check_url("https://evil.example.com/x")
        with self.assertRaises(ProtocolError):
            fs.check_url("http://arxiv.org/abs/1")
        redirect = lambda url, mb: (200, "https://evil.example.com/", {}, b"x")
        self.assertEqual(fs._get(redirect, "https://arxiv.org/abs/1", 10, sleep=lambda s: None)[0], "disallowed_redirect")
        big = lambda url, mb: (200, url, {}, b"x" * (mb + 1))
        self.assertEqual(fs._get(big, "https://arxiv.org/abs/1", 10, sleep=lambda s: None)[0], "too_large")
        attempts = []
        def flaky(url, mb):
            attempts.append(url); raise OSError("down")
        self.assertTrue(fs._get(flaky, "https://arxiv.org/abs/1", 10, sleep=lambda s: None)[0].startswith("fetch_failed"))
        self.assertEqual(len(attempts), 3)


if __name__ == "__main__":
    unittest.main()


class RepoFilesTests(unittest.TestCase):
    def test_fetch_requested_files_at_pinned_commit(self):
        import subprocess
        from mrhbench import factory_sources as fs
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "src"
            repo.mkdir()
            run = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
            run("init", "-q")
            run("config", "user.email", "t@t"); run("config", "user.name", "t")
            (repo / "data").mkdir()
            (repo / "data" / "x.bin").write_bytes(bytes(range(256)) * 10)
            (repo / "data" / "big.pt").write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 9\n")
            run("add", "-A"); run("commit", "-q", "-m", "c1")
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
            (repo / "data" / "x.bin").write_bytes(b"later version")
            run("commit", "-qam", "c2")
            dest = Path(tmp) / "paper" / "repo_files"
            m = fs.fetch_repo_files("https://github.com/o/r", commit,
                                    [{"path": "data/x.bin", "why": "d"}, {"path": "data/big.pt", "why": "w"},
                                     {"path": "nope.txt", "why": "n"}, {"path": "../etc", "why": "u"}],
                                    dest, clone_source=str(repo))
            status = {r["path"]: r["status"] for r in m["requests"]}
            self.assertEqual(status, {"data/x.bin": "fetched", "data/big.pt": "lfs_pointer_not_fetched",
                                      "nope.txt": "not_in_tree", "../etc": "unsafe_path"})
            self.assertEqual((dest / "files" / "data" / "x.bin").read_bytes(), bytes(range(256)) * 10)  # pinned, not later
            self.assertEqual(m["sources"][0]["local_path"], "repo_files/files/data/x.bin")
            m2 = fs.fetch_repo_files("https://github.com/o/r", commit, [{"path": "data/x.bin", "why": "d"}],
                                     Path(tmp) / "paper" / "rf2", clone_source=str(repo), max_total_bytes=10)
            self.assertEqual(m2["requests"][0]["status"], "total_cap")
