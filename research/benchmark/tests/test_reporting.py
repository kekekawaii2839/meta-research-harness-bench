import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.reporting import summarize_calls
from mrhbench.io import ProtocolError

class ReportingTests(unittest.TestCase):
    def test_missing_cost_and_failures_are_not_zero_or_dropped(self):
        x={"attempts":[{"id":1,"role":"executor","status":"completed","usage":{"input_tokens":12,"cached_input_tokens":4},"wall_seconds":2},
                       {"id":2,"role":"judge","status":"timeout","usage":None}]}
        r=summarize_calls(x,[1,2,2])
        self.assertEqual(r["runs_including_failures"],2)
        self.assertEqual(r["roles"]["judge"]["calls_missing_usage"],[2])
        self.assertIsNone(r["dollar_cost"])
        with self.assertRaises(ProtocolError):summarize_calls(x,[3])

if __name__=="__main__":unittest.main()
