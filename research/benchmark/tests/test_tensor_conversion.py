import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mrhbench.tensor_conversion import convert_tensor_file, main

try:
    import numpy as np
except ImportError:
    np = None


class TensorConversionImportTests(unittest.TestCase):
    def test_import_does_not_load_torch_or_numpy(self):
        module = Path(__file__).resolve().parents[1] / 'mrhbench/tensor_conversion.py'
        result = subprocess.run([sys.executable, '-c',
            'import runpy,sys; runpy.run_path(sys.argv[1]); '
            'assert "torch" not in sys.modules; assert "numpy" not in sys.modules',
            str(module)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_contract(self):
        with patch('mrhbench.tensor_conversion.convert_tensor_file') as convert:
            main(['--source', 'a.pt', '--output', 'a.npz', '--manifest', 'a.json',
                  '--expected-source-sha256', 'abc'])
            convert.assert_called_once_with('a.pt', 'a.npz', 'a.json', expected_source_sha256='abc',
                                            max_array_bytes=200 * 1024 * 1024)


@unittest.skipIf(np is None, 'numpy not installed in this test runtime')
class TensorConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.output, self.manifest = [self.root / n for n in ('a.pt', 'a.npz', 'a.json')]
        self.source.write_bytes(b'fake serialized source')
        self.calls = []
        class Tensor:
            layout = 'strided'
            is_quantized = False
            def __init__(self, value, dtype=None):
                self.value = np.asarray(value, dtype=dtype)
                self.dtype = 'torch.' + str(self.value.dtype)
            def detach(self): return self
            def cpu(self): return self
            def resolve_conj(self): return self
            def resolve_neg(self): return self
            def numpy(self): return self.value
        self.Tensor = Tensor
        self.value = Tensor([1, 2, 3], 'int16')
        def load(stream, **kwargs):
            self.calls.append(kwargs)
            self.assertEqual(stream.read(), self.source.read_bytes())
            return self.value
        self.torch = SimpleNamespace(Tensor=Tensor, strided='strided', load=load, __version__='2.6.0+cpu')
        self.fake = patch.dict(sys.modules, {'torch': self.torch})
        self.fake.start()
        self.addCleanup(self.fake.stop)

    def convert(self, **kwargs):
        return convert_tensor_file(self.source, self.output, self.manifest, **kwargs)

    def test_single_tensor_roundtrip_and_hashes(self):
        receipt = self.convert(expected_source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(self.calls, [{'weights_only': True, 'map_location': 'cpu'}])
        self.assertEqual(receipt['source']['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(receipt['output']['sha256'], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(json.loads(self.manifest.read_text()), receipt)
        with np.load(self.output, allow_pickle=False) as data:
            self.assertEqual(data.files, ['arr_000000'])
            self.assertEqual(data['arr_000000'].dtype, np.dtype('int16'))
            np.testing.assert_array_equal(data['arr_000000'], self.value.value)

    def test_sequence_preserves_order_shape_and_nonfinite(self):
        for container in (list, tuple):
            self.value = container([self.Tensor([[np.nan, np.inf], [-np.inf, 3.]], 'float64'),
                                    self.Tensor([], 'uint8')])
            receipt = self.convert()
            self.assertEqual(receipt['container_type'], container.__name__)
            self.assertEqual([a['source_locator'] for a in receipt['arrays']], [0, 1])
            self.assertEqual(receipt['arrays'][0]['nonfinite_elements'], 3)
            self.assertEqual(receipt['arrays'][0]['shape'], [2, 2])
            with np.load(self.output, allow_pickle=False) as data:
                np.testing.assert_array_equal(data['arr_000000'], self.value[0].value)
            self.output.unlink(); self.manifest.unlink()

    def test_dict_keys_are_mapping_not_zip_paths(self):
        self.value = {'../../danger': self.Tensor(7, 'int64'), '中文': self.Tensor([True], 'bool')}
        receipt = self.convert()
        self.assertEqual([a['source_locator'] for a in receipt['arrays']], list(self.value))
        with np.load(self.output, allow_pickle=False) as data:
            self.assertEqual(data.files, ['arr_000000', 'arr_000001'])
            self.assertEqual(data['arr_000000'].shape, ())

    def test_unsupported_types_fail_closed(self):
        class SubTensor(self.Tensor): pass
        for value in (None, 3, {'a': 3}, {1: self.value}, [[self.value]], SubTensor([1]),
                      self.Tensor(['a']), self.Tensor([object()])):
            self.value = value
            with self.assertRaises(ValueError): self.convert()
            self.assertFalse(self.output.exists())
            self.assertFalse(self.manifest.exists())

    def test_sparse_and_quantized_rejected(self):
        for attr, value in (('layout', 'sparse'), ('is_quantized', True)):
            self.value = self.Tensor([1])
            setattr(self.value, attr, value)
            with self.assertRaises(ValueError): self.convert()

    def test_hash_mismatch_does_not_load(self):
        with self.assertRaises(ValueError): self.convert(expected_source_sha256='0' * 64)
        self.assertEqual(self.calls, [])

    def test_no_overwrite_output_or_manifest(self):
        for path in (self.output, self.manifest):
            path.write_bytes(b'existing')
            with self.assertRaises(FileExistsError): self.convert()
            self.assertEqual(path.read_bytes(), b'existing')
            path.unlink()
        with self.assertRaises(ValueError):
            convert_tensor_file(self.source, self.source, self.manifest)

    def test_loader_error_no_unsafe_fallback(self):
        def fail(*args, **kwargs): raise RuntimeError('unsupported pickle')
        self.torch.load = fail
        with self.assertRaises(RuntimeError): self.convert()
        self.assertFalse(self.output.exists())

    def test_serialization_error_removes_own_partial_files(self):
        with patch.object(np, 'savez', side_effect=OSError('quota')):
            with self.assertRaises(OSError): self.convert()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.manifest.exists())

    def test_changed_source_rejected(self):
        def change(stream, **kwargs):
            self.source.write_bytes(b'changed')
            return self.value
        self.torch.load = change
        with self.assertRaisesRegex(ValueError, 'changed'): self.convert()
        self.assertFalse(self.output.exists())

    def test_old_torch_and_prerelease_rejected_without_load(self):
        for version in ('2.5.1', '1.13.0', '2.6.0rc1', 'unknown'):
            self.torch.__version__ = version
            with self.assertRaises(ValueError): self.convert()
        self.assertEqual(self.calls, [])

    def test_total_array_byte_limit(self):
        self.value = [self.Tensor([1, 2], 'int64'), self.Tensor([3, 4], 'int64')]
        with self.assertRaisesRegex(ValueError, 'byte limit'): self.convert(max_array_bytes=31)
        self.assertFalse(self.output.exists())
        self.convert(max_array_bytes=32)


if __name__ == '__main__':
    unittest.main()
