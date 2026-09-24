import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
try:
    import tomllib
except ImportError:
    import tomli as tomllib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.context_policy import build_policy,validate_policy,config_setting,catalog_snapshot
from mrhbench.io import ProtocolError,digest


def render(rows=None, roots=None):
    roots=roots if roots is not None else ['- `r0` = `C:/Users/example/skills`']
    rows=rows if rows is not None else ['- test: Description only. (file: r0/test/SKILL.md)']
    text='<skills_instructions>\n## Skills\n### Skill roots\n'+'\n'.join(roots)+'\n### Available skills\n'+'\n'.join(rows)+'\n</skills_instructions>'
    return [{'type':'message','role':'developer','content':[{'type':'input_text','text':text}]}]


class ContextPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.binary=Path(self.tmp.name)/'fake-codex.exe';self.binary.write_bytes(b'synthetic-binary-not-executed')

    def test_exact_paths_toml_roundtrip_without_skill_reads(self):
        with patch.object(Path,'read_text',side_effect=AssertionError('No skill/config content reads')):
            p=build_policy(render(),self.binary)
            validate_policy(p,self.binary);setting=config_setting(p,self.binary)
        self.assertEqual(tomllib.loads(setting)['skills']['config'],[{'path':'C:/Users/example/skills/test/SKILL.md','enabled':False}])
        self.assertIn('binary_sha256',p);self.assertIn('source_prompt_sha256',p)

    def test_quote_unicode_in_path_are_literal_not_config_injection(self):
        p=build_policy(render(roots=['- `r0` = `/home/文献/skills"quotes`']),self.binary)
        parsed=tomllib.loads(config_setting(p,self.binary))
        self.assertEqual(parsed['skills']['config'][0]['path'],'/home/文献/skills"quotes/test/SKILL.md')
        self.assertEqual(set(parsed),{'skills'})

    def test_absent_and_empty_are_not_isolation_policy(self):
        absent=[{'type':'message','role':'developer','content':[{'type':'input_text','text':'Other context persists.'}]}]
        self.assertEqual(catalog_snapshot(absent)['status'],'not_present_in_render')
        self.assertEqual(catalog_snapshot(render(rows=[]))['status'],'empty_visible_catalogue')
        for obj in (absent,render(rows=[])):
            with self.assertRaises(ProtocolError):build_policy(obj,self.binary)

    def test_user_embedded_catalogue_is_not_host_catalogue(self):
        obj=render();obj[0]['role']='user'
        with self.assertRaises(ProtocolError):build_policy(obj,self.binary)

    def test_unknown_roots_and_non_skill_paths_fail_closed(self):
        for path in ['r9/foo/SKILL.md','r0/foo','r0/foo/README.md','r0/foo/skill.md','r0/SKILL.md',
                     'r0/foo/../SKILL.md','r0/./foo/SKILL.md','r0/foo//SKILL.md','r0/foo\\bar/SKILL.md',
                     'r0/foo:stream/SKILL.md','r0/foo /SKILL.md','r0/foo*/SKILL.md']:
            with self.subTest(path=path),self.assertRaises(ProtocolError):
                build_policy(render(rows=['- test: description. (file: '+path+')']),self.binary)

    def test_root_forms_rejected_without_filesystem_enumeration(self):
        for root in ['relative/skills','C:relative/skills','//server/share','C:/','/','C:/a/../b','C:/a//b']:
            with self.subTest(root=root),self.assertRaises(ProtocolError):
                build_policy(render(roots=['- `r0` = `'+root+'`']),self.binary)
        with self.assertRaises(ProtocolError):build_policy(render(roots=[]),self.binary)

    def test_duplicates_truncation_and_unknown_catalogue_fail(self):
        objs=[render(rows=['- a: d (file: r0/a/SKILL.md)','- b: d (file: r0/A/SKILL.md)']),
              render(roots=['- `r0` = `C:/a`','- `r0` = `C:/b`']),render()+render()]
        broken=render();broken[0]['content'][0]['text']=broken[0]['content'][0]['text'].replace('</skills_instructions>','');objs.append(broken)
        broken=render();broken[0]['content'][0]['text']=broken[0]['content'][0]['text'].replace('### Skill roots','### Roots');objs.append(broken)
        objs+=[[],{},[{'type':'message','role':'developer','content':'not a content list'}]]
        for obj in objs:
            with self.subTest(obj=obj),self.assertRaises(ProtocolError):build_policy(obj,self.binary)

    def test_policy_binary_and_catalogue_hash_binding(self):
        p=build_policy(render(),self.binary)
        for mutation in ('hash','enable','absolute','profile','extra','limits'):
            wrong=copy.deepcopy(p)
            if mutation=='hash':wrong['catalogue_sha256']='0'*64
            if mutation=='enable':wrong['disabled_skills'][0]['enabled']=True
            if mutation=='absolute':wrong['disabled_skills'][0]['path']='C:/outside/SKILL.md'
            if mutation=='profile':wrong['profile_version']='future'
            if mutation=='extra':wrong['extra']=True
            if mutation=='limits':wrong['limitations']=[]
            with self.subTest(mutation=mutation),self.assertRaises(ProtocolError):validate_policy(wrong,self.binary)
        self.binary.write_bytes(b'new binary')
        with self.assertRaises(ProtocolError):config_setting(p,self.binary)

    def test_order_is_deterministic_and_input_unmodified(self):
        obj=render(rows=['- z: d (file: r0/z/SKILL.md)','- a: d (file: r0/a/SKILL.md)']);before=copy.deepcopy(obj)
        p=build_policy(obj,self.binary)
        self.assertEqual(obj,before);self.assertTrue(p['disabled_skills'][0]['path'].endswith('/a/SKILL.md'))
        self.assertEqual(p['source_prompt_sha256'],digest(obj))


if __name__=='__main__':unittest.main()
