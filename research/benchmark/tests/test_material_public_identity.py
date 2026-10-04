"""Opaque identity foundation tests; no model calls or anonymity claims."""
from pathlib import Path
import sys
import tempfile
import unittest
import os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrhbench import material_public_identity as m
from mrhbench.io import ProtocolError,read_json,write_json,file_hash
from mrhbench.material_adapter import compile_package
from mrhbench.materials import export_task

class IdentityTests(unittest.TestCase):
    def fixture(self,root):
        from test_material_adapter import MaterialAdapterTests
        source,args=MaterialAdapterTests().fixture(root)
        package=read_json(source/'package.json')
        package['paper_id']='private-paper-Q9X'
        package['tasks'][0].update(task_id='private-task-Q9X',paper_id='private-paper-Q9X')
        write_json(source/'package.json',package)
        args['execution_budgets']={'private-task-Q9X':args['execution_budgets']['t']}
        args['artifact_collections']={'private-task-Q9X':args['artifact_collections']['t']}
        return source,args

    def test_same_map_two_arms_assets_identical_compile_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,args=self.fixture(root)
            original=m._tree(source)
            identity=m.allocate_map(source,root/'private/map.json',aliases=['Distinctive Method X'])
            private=m.validate_map(identity)
            task_id=private['task_ids']['private-task-Q9X']
            self.assertRegex(task_id,r'^task-[0-9a-f]{32}$')
            for arm in ('old','incremental'):
                dest=root/arm
                result=m.project_candidate(source,dest,identity,receipt_path=root/'private'/(arm+'.json'))
                projected=read_json(dest/'package.json')
                self.assertEqual(projected['paper_id'],'private-paper-Q9X')
                self.assertEqual(projected['tasks'][0]['task_id'],task_id)
                self.assertFalse(result['scan']['semantic_anonymity_verified'])
                self.assertTrue(read_json(Path(result['receipt']['path']))['assets_byte_identical'])
                for name,row in original.items():
                    if name!='package.json':self.assertEqual(m._tree(dest)[name],row)
                compiled=root/(arm+'-compiled')
                opts={**args,'execution_budgets':m.remap_task_keys(args['execution_budgets'],identity),
                      'artifact_collections':m.remap_task_keys(args['artifact_collections'],identity)}
                compile_package(dest,destination=compiled,**opts)
                task=read_json(compiled/task_id/'task.json')
                self.assertEqual(task['paper_id'],'private-paper-Q9X')
                release=root/(arm+'-release')
                export_task(task,compiled/task_id,release,audience='development_executor')
                scan=m.scan_release(release,identity)
                self.assertEqual(scan['status'],'no_known_identity_match')
                view=read_json(release/'task.json')
                self.assertEqual(view['task_id'],task_id)
                self.assertNotIn('paper_id',view)
                self.assertFalse(any('map.json' in str(p) for p in release.rglob('*')))
            self.assertEqual(m._tree(source),original)

    def test_only_task_id_json_paths_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=self.fixture(root)
            identity=m.allocate_map(source,root/'map.json')
            m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
            before=read_json(source/'package.json');after=read_json(root/'new/package.json')
            after['tasks'][0]['task_id']=before['tasks'][0]['task_id']
            self.assertEqual(before,after)

    def test_map_tamper_and_no_reallocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=self.fixture(root)
            identity=m.allocate_map(source,root/'map.json')
            with self.assertRaises(ProtocolError):m.allocate_map(source,root/'map.json')
            data=read_json(root/'map.json');data['task_ids']['private-task-Q9X']='task-'+'0'*32
            write_json(root/'map.json',data)
            with self.assertRaises(ProtocolError):m.validate_map(identity)

    def test_private_map_receipt_outside_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=self.fixture(root)
            with self.assertRaises(ProtocolError):m.allocate_map(source,source/'map.json')
            identity=m.allocate_map(source,root/'map.json')
            with self.assertRaises(ProtocolError):m.project_candidate(source,root/'new',identity,receipt_path=root/'new/receipt.json')
            m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
            with self.assertRaises(ProtocolError):m.project_candidate(source,root/'new',identity,receipt_path=root/'other.json')
            with self.assertRaises(ProtocolError):m.project_candidate(source,root/'other',identity,receipt_path=root/'receipt.json')

    def test_budget_key_set_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=self.fixture(root);identity=m.allocate_map(source,root/'map.json')
            for values in ({},{'extra':1},{'private-task-Q9X':1,'extra':2}):
                with self.assertRaises(ProtocolError):m.remap_task_keys(values,identity)

    def test_known_identity_fact_id_contract_keys_values_and_alias_rejected(self):
        for where in ('fact_id','statement','contractkey','contractvalue','assetpath','assetbytes','alias'):
            with self.subTest(where=where),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source,_=self.fixture(root);p=read_json(source/'package.json')
                if where=='fact_id':
                    p['facts'][0]['fact_id']='private-paper-Q9X';p['tasks'][0]['input_fact_ids']=['private-paper-Q9X']
                if where=='statement':p['facts'][0]['statement']='private-paper-Q9X'
                if where=='contractkey':p['tasks'][0]['output_contract']['private-task-Q9X']='value'
                if where=='contractvalue':p['tasks'][0]['output_contract']['note']='PRIVATE-PAPER-Q9X'
                if where=='alias':p['tasks'][0]['input_contract']['note']='Distinctive Method X'
                if where=='assetbytes':
                    (source/'assets/start.txt').write_text('private-paper-Q9X')
                    p['tasks'][0]['assets'][0]['sha256']=file_hash(source/'assets/start.txt')
                if where=='assetpath':
                    (source/'assets/start.txt').rename(source/'assets/private-task-Q9X.txt')
                    p['tasks'][0]['assets'][0]['path']='assets/private-task-Q9X.txt'
                write_json(source/'package.json',p)
                identity=m.allocate_map(source,root/'map.json',aliases=['Distinctive Method X'])
                with self.assertRaises(ProtocolError):m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
                self.assertFalse((root/'receipt.json').exists())

    def test_binary_unknown_not_clear_and_known_binary_needle_rejected(self):
        for known in (False,True):
            with self.subTest(known=known),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source,_=self.fixture(root)
                (source/'assets/start.txt').write_bytes(b'\x89PNG\x00'+(b'private-paper-Q9X' if known else b'\xff\x00'))
                p=read_json(source/'package.json');p['tasks'][0]['assets'][0]['sha256']=file_hash(source/'assets/start.txt')
                write_json(source/'package.json',p);identity=m.allocate_map(source,root/'map.json')
                if known:
                    with self.assertRaises(ProtocolError):m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
                else:
                    r=m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
                    self.assertEqual(r['scan']['status'],'unknown_binary_requires_independent_review')
                    self.assertFalse(r['scan']['scientific_acceptance'])

    def test_release_scans_new_controller_fields_and_unlisted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,args=self.fixture(root);identity=m.allocate_map(source,root/'map.json')
            m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
            tid=m.validate_map(identity)['task_ids']['private-task-Q9X']
            args.update(execution_budgets=m.remap_task_keys(args['execution_budgets'],identity),
                        artifact_collections=m.remap_task_keys(args['artifact_collections'],identity))
            compile_package(root/'new',destination=root/'compiled',**args)
            task=read_json(root/'compiled'/tid/'task.json')
            export_task(task,root/'compiled'/tid,root/'release',audience='development_executor')
            view=read_json(root/'release/task.json');view['resources']['controller_note']='private-paper-Q9X'
            write_json(root/'release/task.json',view)
            with self.assertRaises(ProtocolError):m.scan_release(root/'release',identity)
            del view['resources']['controller_note'];write_json(root/'release/task.json',view)
            write_json(root/'release/private-map.json',{})
            with self.assertRaises(ProtocolError):m.scan_release(root/'release',identity)

    def test_hardlink_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=self.fixture(root);identity=m.allocate_map(source,root/'map.json')
            os.link(source/'assets/start.txt',source/'assets/hardlink.txt')
            with self.assertRaises(ProtocolError):m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=self.fixture(root)
            try:os.symlink(source,root/'link',target_is_directory=True)
            except OSError:self.skipTest('Host symlink privilege unavailable; hardlink negative already checked')
            with self.assertRaises(ProtocolError):m.allocate_map(root/'link',root/'map.json')

    def test_json_escaped_keys_and_values_scanned_regardless_of_extension(self):
        contents=[r'{"identity":"\u0070rivate-paper-Q9X"}',
                  r'{"\u0070rivate-paper-Q9X":"neutral"}',
                  r'["\u0070rivate-paper-Q9X"]',
                  r'{"same":"\u0070rivate-paper-Q9X","same":"neutral"}']
        for content in contents:
            with self.subTest(content=content),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source,_=self.fixture(root)
                (source/'assets/start.txt').write_text(content,encoding='utf8')
                p=read_json(source/'package.json');p['tasks'][0]['assets'][0]['sha256']=file_hash(source/'assets/start.txt')
                write_json(source/'package.json',p);identity=m.allocate_map(source,root/'map.json')
                with self.assertRaises(ProtocolError):
                    m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')

    def test_safe_json_and_non_json_coverage_are_distinct(self):
        for content,checked in [(' {"neutral":["allowed",2]} ',True),('Plain non-JSON text',False),
                                ('{"neutral":NaN}',False)]:
            with self.subTest(content=content),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source,_=self.fixture(root)
                (source/'assets/start.txt').write_text(content,encoding='utf8')
                p=read_json(source/'package.json');p['tasks'][0]['assets'][0]['sha256']=file_hash(source/'assets/start.txt')
                write_json(source/'package.json',p);identity=m.allocate_map(source,root/'map.json')
                result=m.project_candidate(source,root/'new',identity,receipt_path=root/'receipt.json')
                self.assertEqual(result['scan']['assets'][0]['strict_json_keys_values_scanned'],checked)
                self.assertFalse(result['scan']['semantic_anonymity_verified'])

if __name__=='__main__':unittest.main()
