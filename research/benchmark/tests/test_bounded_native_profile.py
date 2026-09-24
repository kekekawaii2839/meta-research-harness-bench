import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from mrhbench.native_codex import NativeCodexRunner, _toml_value
from mrhbench.providers import DISABLED_FEATURES
from mrhbench.io import ProtocolError


class NativeProfileTests(unittest.TestCase):
    def test_bounded_profile_disables_host_features(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d); binary = p/'codex.exe'; binary.write_bytes(b'fixture')
            servers = {'bounded': {'command': 'python', 'args': ['server.py'], 'enabled_tools': ['evidence_read'], 'required': True}}
            runner = NativeCodexRunner(binary=binary, model='gpt-5.6-sol', reasoning_effort='medium', ledger=None,
                                       audit_root=p/'audit', permission_profile=':read-only', tool_profile='bounded_mcp', mcp_servers=servers)
            command = runner.command(p, p/'output')
            for flag in DISABLED_FEATURES:
                self.assertEqual(command[command.index(flag)-1], '--enable' if flag == 'code_mode_host' else '--disable')
            self.assertIn('mcp_servers='+_toml_value(servers), command)
            with self.assertRaises(ProtocolError):
                NativeCodexRunner(binary=binary, model='gpt-5.6-sol', reasoning_effort='medium', ledger=None,
                                  audit_root=p/'audit', tool_profile='bounded_mcp', mcp_servers=servers)


if __name__ == '__main__': unittest.main()
