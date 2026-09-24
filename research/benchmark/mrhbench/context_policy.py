"""Frozen opt-in denylist for skills visible in a Codex debug prompt-input.

Only parses the rendered catalogue; never opens skills, traverses directories,
edits global configuration, changes permissions or accesses credentials. This is
NOT a general context-isolation policy: newly installed/unobserved skills and all
other injected context remain outside the denylist.
"""
from pathlib import Path
import json
import re

from .io import ProtocolError, canonical, digest, file_hash

PROFILE = 'codex-visible-skill-denylist-v1'
LIMITATIONS = [
    'Only exact SKILL.md paths visible in the frozen developer catalogue are disabled.',
    'Newly added, moved, omitted or otherwise unobserved skills are not covered.',
    'An empty visible catalogue does not establish absence of other injected context.',
    'This changes neither filesystem permissions nor tools, plugins, memory, instructions, credentials or model context generally.',
    'Re-render the effective prompt with this binary/profile before claiming catalogue suppression; no automatic acceptance is implied.',
]
ROOT_LINE = re.compile(r'^- `(r[0-9]+)` = `([^`]+)`$')
SKILL_LINE = re.compile(r'^- .+ \(file: (r[0-9]+)/([^\r\n]+)\)$')
HEX = re.compile(r'^[0-9a-f]{64}$')


def _string(value, label):
    if not isinstance(value,str) or not value or len(value)>4096:
        raise ProtocolError(label+' must be a bounded nonempty string')
    if any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in value):
        raise ProtocolError(label+' contains controls or invalid Unicode')
    return value


def _segments(value, label):
    parts=value.split('/')
    if any(not p or p in ('.','..') or p[-1] in (' ','.') for p in parts):
        raise ProtocolError(label+' contains empty, dot, traversal or trailing-alias components')
    if any(any(c in p for c in ':*?<>|') for p in parts):
        raise ProtocolError(label+' contains non-path or Windows stream/wildcard syntax')
    return parts


def _root(value):
    value=_string(value,'Skill root').replace('\\','/')
    if value.endswith('/') and value!='/':
        value=value[:-1]
    if re.match(r'^[A-Za-z]:/',value):
        prefix=value[:3];rest=value[3:]
    elif value.startswith('/') and not value.startswith('//'):
        prefix='/';rest=value[1:]
    else:raise ProtocolError('Skill root must be absolute local drive or POSIX path; UNC/device/relative paths unsupported')
    if rest:_segments(rest,'Skill root')
    if not rest:raise ProtocolError('Filesystem root alone is not an accepted skill root')
    return prefix+rest


def _entry(alias, relative, roots):
    if not isinstance(alias,str) or re.fullmatch(r'r[0-9]+',alias) is None:
        raise ProtocolError('Invalid skill root alias')
    if alias not in roots:raise ProtocolError('Skill references missing root alias')
    relative=_string(relative,'Relative skill path')
    if '\\' in relative:raise ProtocolError('Relative catalogue paths must use forward slashes')
    parts=_segments(relative,'Relative skill path')
    if len(parts)<2 or parts[-1]!='SKILL.md':
        raise ProtocolError('Exact SKILL.md file, not skill folder or other filename, required')
    return {'root_alias':alias,'relative_path':relative,'path':roots[alias]+'/'+relative,'enabled':False}


def catalog_snapshot(prompt_input):
    """Observe a known JSON render shape; absence is an observation, not a policy.

    A missing skills block produces status=not_present_in_render with zero rows;
    malformed/ambiguous blocks fail closed rather than silently losing entries.
    """
    if not isinstance(prompt_input,list) or not prompt_input or len(prompt_input)>10000:
        raise ProtocolError('Expected nonempty bounded prompt-input JSON message array')
    if len(canonical(prompt_input))>10*1024*1024:
        raise ProtocolError('Prompt render exceeds parser bound')
    blocks=[]
    for message in prompt_input:
        if not isinstance(message,dict) or message.get('type')!='message' or message.get('role') not in {'developer','system','user','assistant'} or not isinstance(message.get('content'),list):
            raise ProtocolError('Unsupported initial prompt-input message shape')
        for item in message['content']:
            if not isinstance(item,dict):raise ProtocolError('Malformed prompt content')
            if item.get('type')!='input_text':continue
            text=item.get('text')
            if not isinstance(text,str):raise ProtocolError('Malformed prompt text')
            if message['role']!='developer':continue
            count=text.count('<skills_instructions>');end=text.count('</skills_instructions>')
            if count!=end or count>1:raise ProtocolError('Ambiguous or truncated skills block')
            if count:
                start=text.index('<skills_instructions>');stop=text.index('</skills_instructions>')
                if stop<start:raise ProtocolError('Malformed skills block order')
                blocks.append(text[start+len('<skills_instructions>'):stop])
    if not blocks:return {'status':'not_present_in_render','roots':{},'skills':[], 'scope':'No visible skills block in this render; other context not assessed.'}
    if len(blocks)!=1:raise ProtocolError('Multiple developer skills catalogues are unsupported')
    block=blocks[0]
    if block.count('### Skill roots')!=1 or block.count('### Available skills')!=1:
        raise ProtocolError('Unknown skills catalogue schema')
    head,body=block.split('### Skill roots',1)
    roottext,skilltext=body.split('### Available skills',1)
    roots={}
    for line in roottext.strip().splitlines():
        match=ROOT_LINE.fullmatch(line.strip())
        if not match:raise ProtocolError('Malformed skill root row')
        alias,value=match.groups()
        if alias in roots:raise ProtocolError('Duplicate skill root alias')
        roots[alias]=_root(value)
    if not roots:raise ProtocolError('Catalogue roots are missing')
    rows=[];seen=set()
    for line in skilltext.strip().splitlines():
        match=SKILL_LINE.fullmatch(line.strip())
        if not match:raise ProtocolError('Malformed skill row; cannot safely build partial denylist')
        entry=_entry(*match.groups(),roots)
        key=entry['path'].casefold()
        if key in seen:raise ProtocolError('Duplicate or case-alias skill path')
        seen.add(key);rows.append(entry)
    if len(roots)>500 or len(rows)>1000:raise ProtocolError('Catalogue too large for this profile')
    rows.sort(key=lambda r:r['path'])
    return {'status':'visible_catalogue' if rows else 'empty_visible_catalogue','roots':dict(sorted(roots.items())),
            'skills':rows,'scope':'Rendered catalogue only; no skill content or other context assessed.'}


def build_policy(prompt_input, binary):
    snapshot=catalog_snapshot(prompt_input)
    if snapshot['status']!='visible_catalogue':
        raise ProtocolError('Cannot freeze denylist from absent/empty visible catalogue; absence does not establish context isolation')
    binary=Path(binary).resolve(strict=True)
    policy={'schema_version':1,'profile_version':PROFILE,'binary_sha256':file_hash(binary),
        'source_prompt_sha256':digest(prompt_input),'catalogue_sha256':digest({'roots':snapshot['roots'],'skills':snapshot['skills']}),
        'roots':snapshot['roots'],'disabled_skills':snapshot['skills'],'limitations':list(LIMITATIONS)}
    validate_policy(policy,binary)
    return policy


def validate_policy(policy, binary):
    fields={'schema_version','profile_version','binary_sha256','source_prompt_sha256','catalogue_sha256','roots','disabled_skills','limitations'}
    if not isinstance(policy,dict) or set(policy)!=fields or type(policy['schema_version']) is not int or policy['schema_version']!=1 or policy['profile_version']!=PROFILE:
        raise ProtocolError('Unsupported frozen context-policy schema/profile')
    if policy['limitations']!=LIMITATIONS:raise ProtocolError('Context policy scope/limitations cannot be removed or broadened')
    for name in ('binary_sha256','source_prompt_sha256','catalogue_sha256'):
        if not isinstance(policy[name],str) or not HEX.fullmatch(policy[name]):raise ProtocolError('Invalid context binding hash')
    if file_hash(Path(binary).resolve(strict=True))!=policy['binary_sha256']:
        raise ProtocolError('Context policy binary hash mismatch; re-audit changed binary')
    roots=policy['roots']; rows=policy['disabled_skills']
    if not isinstance(roots,dict) or not 1<=len(roots)<=500 or not isinstance(rows,list) or not 1<=len(rows)<=1000:
        raise ProtocolError('Nonempty bounded frozen roots/skills required')
    for alias,path in roots.items():
        if not isinstance(alias,str) or re.fullmatch(r'r[0-9]+',alias) is None or _root(path)!=path:
            raise ProtocolError('Invalid or noncanonical skill root')
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'root_alias','relative_path','path','enabled'} or row['enabled'] is not False:
            raise ProtocolError('Policy supports only exact disabled skill entries')
        if row!=_entry(row['root_alias'],row['relative_path'],roots):raise ProtocolError('Absolute skill path disagrees with its root/relative path')
        key=row['path'].casefold()
        if key in seen:raise ProtocolError('Duplicate frozen skill path')
        seen.add(key)
    if rows!=sorted(rows,key=lambda r:r['path']):raise ProtocolError('Frozen skill entries must have canonical order')
    if digest({'roots':roots,'skills':rows})!=policy['catalogue_sha256']:
        raise ProtocolError('Frozen catalogue hash mismatch')


def config_setting(policy, binary):
    """Return ONE literal TOML -c value; no shell or global config operations."""
    validate_policy(policy,binary)
    # JSON Unicode string escaping is a TOML basic-string subset for our bounded
    # strings (controls/surrogates rejected). Table syntax is fixed, not input.
    entries=['{path = '+json.dumps(r['path'],ensure_ascii=False)+', enabled = false}' for r in policy['disabled_skills']]
    return 'skills.config=['+','.join(entries)+']'
