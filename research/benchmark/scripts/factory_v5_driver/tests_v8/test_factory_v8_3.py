"""Offline tests for factory_v8_3 (zero model calls, no network): the first-disclosure record written at fetch is the
single cutoff source, is visible in the adjudication workspace, and leaves papers with an arXiv v1 unchanged."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

DRIVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DRIVER))
import factory_v8_3 as v83  # noqa: E402
import factory_v6  # noqa: E402
import factory_v5  # noqa: E402
import openreview_fetch  # noqa: E402
from tests_v8 import test_factory_v8 as T  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

ODATE = "2024-10-04"


def found(date):
    return lambda forum: (date, {"odate": 0})


def missing(forum):
    raise openreview_fetch.OpenReviewFetchError("OpenReview note has no public date (odate) for " + forum)


def arxiv_manifest(date=None):
    a = {"status": "arxiv_not_found", "earliest_known_public_version": None}
    if date:
        a = {"status": "found", "earliest_known_public_version": {"version": 1, "date": date + "T17:59:00Z"}}
    return {"arxiv": a, "sources": []}


class Record(unittest.TestCase):
    def test_no_arxiv_uses_openreview_public_date(self):
        r = v83.disclosure_record(arxiv_manifest(), "X", found(ODATE))
        self.assertEqual((r["arxiv_v1"], r["openreview_public"], r["disclosure_cutoff"], r["public_cutoff"], r["basis"]),
                         (None, ODATE, ODATE, "2024-09-20", "openreview_public"))

    def test_earlier_of_the_two(self):
        r = v83.disclosure_record(arxiv_manifest("2024-06-01"), "X", found(ODATE))
        self.assertEqual((r["disclosure_cutoff"], r["basis"]), ("2024-06-01", "arxiv_v1"))
        r = v83.disclosure_record(arxiv_manifest("2025-01-15"), "X", found(ODATE))
        self.assertEqual((r["disclosure_cutoff"], r["basis"]), (ODATE, "openreview_public"))

    def test_lookup_failure_and_no_date(self):
        r = v83.disclosure_record(arxiv_manifest("2024-06-01"), "X", missing)
        self.assertEqual((r["disclosure_cutoff"], r["openreview_public"]), ("2024-06-01", None))
        self.assertTrue(r["openreview_lookup"].startswith("failed"))
        r = v83.disclosure_record(arxiv_manifest(), "X", missing)
        self.assertEqual((r["disclosure_cutoff"], r["public_cutoff"], r["basis"]), (None, None, "none"))


class Flow(unittest.TestCase):
    setUp, tearDown, make = T.Flow.setUp, T.Flow.tearDown, T.Flow.make

    def make83(self, arxiv_date=None, lookup=found(ODATE)):
        f = self.make(T.Script())
        f.__class__ = v83.FactoryV83  # same fixture as the v8 tests, v8.3 controller methods
        del f.background_cutoff  # the v8 fixture stubs it; v8.3 must read the manifest record
        pdir = f.paper_dir(T.PID)
        m = read_json(pdir / "sources/manifest.json")
        m["arxiv"] = arxiv_manifest(arxiv_date)["arxiv"]
        write_json(pdir / "sources/manifest.json", m)
        old = openreview_fetch.submission_date
        openreview_fetch.submission_date = lookup
        self.addCleanup(setattr, openreview_fetch, "submission_date", old)
        return f, pdir

    def test_fetch_stamps_record_and_adjudication_sees_it(self):
        f, pdir = self.make83()
        orig = factory_v6.FactoryV6.stage_fetch
        factory_v6.FactoryV6.stage_fetch = lambda self, state: self._record(state, "fetch", DONE, {}, notes=["fake fetch"])
        self.addCleanup(setattr, factory_v6.FactoryV6, "stage_fetch", orig)
        state = f.state(T.PID)
        f.stage_fetch(state)
        fd = read_json(pdir / "sources/manifest.json")["first_disclosure"]
        self.assertEqual((fd["disclosure_cutoff"], fd["public_cutoff"]), (ODATE, "2024-09-20"))
        self.assertIn("first disclosure 2024-10-04", " ".join(f.state(T.PID)["stages"]["fetch"]["notes"]))
        ws = self.tmp / "adj_ws"
        f._candidate = lambda pid: {"project_id": T.PID, "title": "t", "abstract": "a"}
        f._source_workspace(f.state(T.PID), ws)
        self.assertEqual(read_json(ws / "source_manifest.json")["first_disclosure"]["disclosure_cutoff"], ODATE)

    def test_background_and_job_use_the_recorded_value(self):
        f, pdir = self.make83()
        v83.stamp_manifest(pdir, found(ODATE))
        openreview_fetch.submission_date = found("2023-01-01")  # a later live lookup must not be used
        self.assertEqual(f.background_cutoff(pdir)[0], ODATE)
        self.assertEqual(f.controller_cutoff(T.PID)[0], "2024-09-20")
        job = f.build_job(f.unit_state(T.PID, "IDEA"))
        self.assertEqual(job["first_disclosure"]["date"], "2024-09-20")

    def test_missing_record_is_an_error(self):
        f, pdir = self.make83()
        with self.assertRaises(Exception):
            f.background_cutoff(pdir)

    def test_paper_with_arxiv_unchanged(self):
        for arxiv_date in ("2024-06-01", "2025-01-15"):
            shutil.rmtree(self.root, ignore_errors=True)
            f, pdir = self.make83(arxiv_date)
            v6 = factory_v6.FactoryV6.background_cutoff(f, pdir)
            v83.stamp_manifest(pdir)
            self.assertEqual(f.background_cutoff(pdir)[0], v6[0])
            self.assertEqual(f.background_cutoff(pdir)[1]["openreview_public"], v6[1]["openreview_public"])

    def test_carry_dated_stamps_only_the_copy(self):
        f, pdir = self.make83()
        write_json(pdir / "state.json", {"project_id": T.PID, "stages": {"fetch": {"status": DONE},
                                                                          "adjudication": {"status": DONE}}, "flags": []})
        before = file_hash(pdir / "sources/manifest.json")
        new_root = self.tmp / "factory-v8_3"
        out = v83.cmd_carry_dated(new_root, self.root, [T.PID], lookup=found(ODATE))
        self.assertEqual(file_hash(pdir / "sources/manifest.json"), before)
        d = new_root / "papers" / T.PID
        self.assertEqual(read_json(d / "sources/manifest.json")["first_disclosure"]["disclosure_cutoff"], ODATE)
        self.assertEqual(list(read_json(d / "state.json")["stages"]), ["fetch"])
        self.assertFalse((d / "adjudication").exists())
        self.assertEqual(out[0]["first_disclosure"]["public_cutoff"], "2024-09-20")


if __name__ == "__main__":
    unittest.main()
