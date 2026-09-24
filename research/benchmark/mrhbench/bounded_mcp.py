"""Controller-selected stdio MCP evidence and container tools; never a host shell.

Manifest is trusted configuration, not model arguments. The server is private to
one fresh Codex process. Evidence is immutable data; arbitrary code executes only
inside a controller-created credential-free ContainerSession.
"""
from __future__ import annotations
import argparse, base64, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError, read_json, write_json
from mrhbench.judging import EvidenceSession


def tool(name, description, properties, required):
    return {'name':name,'description':description,'inputSchema':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}

STR={'type':'string'}
EVIDENCE_TOOLS=[
    tool('evidence_inventory','List all frozen evidence identifiers, roles, visibility, hashes and line counts.',{},[]),
    tool('evidence_read','Read at most 6000 characters of frozen evidence, follow next_char until needed coverage. Offsets address original text. Return exact receipt_id for citations. Images delivered as image, not base64 text.',{'evidence_id':STR,'start_char':{'type':'integer','minimum':0},'max_chars':{'type':'integer','minimum':1,'maximum':6000}},['evidence_id'])]
CONTAINER_TOOLS=[
    tool('container_exec','Execute argv only inside this credential-free, offline CPU container. No host shell.',{'argv':{'type':'array','items':STR,'minItems':1},'timeout':{'type':'number','exclusiveMinimum':0}},['argv']),
    tool('container_read','Read a regular file only under /inputs or /work.',{'path':STR,'max_bytes':{'type':'integer','minimum':1,'maximum':262144}},['path']),
    tool('container_write','Write UTF-8 text only under /work. Input is immutable.',{'path':STR,'text':STR},['path','text']),
    tool('container_list','List this container workspace or inputs.',{'path':STR},['path'])]


class BoundedTools:
    def __init__(self, manifest):
        self.manifest=manifest
        self.session=EvidenceSession(manifest.get('records',[]),max_text_chars=manifest.get('max_text_chars',180000))
        self.container=None
        self.owns_container=False
        self.events=[]
        self.image_returns=set()
        self.max_calls=manifest.get('max_tool_calls',80)
        if isinstance(self.max_calls,bool) or not isinstance(self.max_calls,int) or not 1<=self.max_calls<=500:
            raise ProtocolError('Invalid tool call cap')
        self.calls=0
        # Reject invalid capability configuration BEFORE starting any resource.
        self.definitions=EVIDENCE_TOOLS+(CONTAINER_TOOLS if manifest.get('container') else [])
        allowed=manifest.get('allowed_tools')
        if allowed is not None:
            known={t['name'] for t in self.definitions}
            if (not isinstance(allowed,list) or not allowed or any(not isinstance(x,str) for x in allowed)
                    or len(set(allowed))!=len(allowed) or not set(allowed)<=known):
                raise ProtocolError('Explicit server tool allowlist invalid')
            self.definitions=[t for t in self.definitions if t['name'] in allowed]
        try:
            if manifest.get('container'):
                from mrhbench.container_runtime import ContainerSession
                c=manifest['container']
                self.container=ContainerSession(image_id=c['image_id'],resources=c['resources'],input_files={k:Path(v) for k,v in c['input_files'].items()},audit_dir=Path(c['audit_dir']),input_hashes=c.get('input_hashes'))
                attached=c.get('attached_session')
                if attached:
                    # Parent owns watchdog/export/cleanup for attached sessions.
                    self.container.audit_dir.mkdir(parents=True,exist_ok=False)
                    self.container.cid=attached['cid'];self.container.owner=attached['owner']
                    self.container.deadline=attached['deadline_monotonic'];self.container.started=True
                    self.container._assert_owned();self.container._live()
                else:
                    self.owns_container=True;self.container.start()
            self.save()
        except Exception:
            # A constructor that fails never reaches serve's finally. Reclaim
            # only resources this server owns; keep the original error intact.
            if self.container and self.owns_container:
                try:self.container.close()
                except Exception:pass
            raise

    def save(self):
        identity=None
        if self.container and getattr(self.container,'cid',None):
            remaining=max(0,self.container.deadline-time.monotonic())
            identity={'cid':self.container.cid,'owner':self.container.owner,'audit_dir':str(self.container.audit_dir),
                      'deadline_monotonic':self.container.deadline,'expires_at_utc':datetime.fromtimestamp(time.time()+remaining,timezone.utc).isoformat(),
                      'lifecycle_owner':'mcp_process_development_only_unreliable_on_forced_exit' if self.owns_container else 'external_controller'}
        write_json(Path(self.manifest['state_path']),{'receipts':self.session.receipts,'events':self.session.events,'tool_events':self.events,'image_results_returned':sorted(self.image_returns),'image_model_delivery_verified':False,'tool_calls':self.calls,'max_text_chars':self.session.max_text_chars,'returned_text_chars_with_repeats':self.session.text_chars,'container_identity':identity})

    def call(self,name,args):
        definitions={x['name']:x for x in self.definitions}
        if name not in definitions or not isinstance(args,dict):raise ProtocolError('Tool not available')
        schema=definitions[name]['inputSchema']
        if not set(args)<=set(schema['properties']) or not set(schema['required'])<=set(args):raise ProtocolError('Unexpected tool arguments')
        if self.calls>=self.max_calls:raise ProtocolError('Tool call allowance exhausted')
        self.calls+=1
        if name=='evidence_inventory':result=self.session.inventory()
        elif name=='evidence_read':
            result=self.session.read_chars(**args)
            if result['media_type'].startswith('image/'):
                content=result.pop('content')
                self.image_returns.add(result['receipt_id'])
                self.events.append({'name':name,'arguments':args,'receipt_id':result['receipt_id'],'image_returned_as_mcp_content':True})
                self.save()
                return {'content':[{'type':'text','text':json.dumps(result)},{'type':'image','mimeType':result['media_type'],'data':content}]}
        elif name=='container_exec':result=self.container.exec(**args)
        elif name=='container_read':
            if isinstance(args.get('max_bytes'),bool) or not 1<=args.get('max_bytes',262144)<=262144:raise ProtocolError('Read allowance invalid')
            result={'path':args['path'],'text':self.container.read(**args).decode('utf8')}
        elif name=='container_write':
            if not isinstance(args['text'],str) or len(args['text'].encode())>262144:raise ProtocolError('Write too large')
            result=self.container.write(args['path'],args['text'].encode())
        elif name=='container_list':result=self.container.list(**args)
        self.events.append({'name':name,'arguments':args,'receipt_id':result.get('receipt_id') if isinstance(result,dict) else None})
        self.save()
        return {'content':[{'type':'text','text':json.dumps(result,ensure_ascii=False)}]}

    def close(self):
        try:
            export=self.manifest.get('artifact_export')
            if self.container and self.owns_container and export:
                # Controller configuration only. No tool exposes host destinations.
                inventory=self.container.artifacts(Path(export['destination']),
                    max_bytes=export['max_bytes'],max_files=export['max_files'])
                write_json(Path(export['inventory_path']),inventory)
        finally:
            if self.container and self.owns_container:self.container.close()
            self.save()


def serve(manifest,instream=None,outstream=None):
    inp=instream or sys.stdin.buffer;out=outstream or sys.stdout.buffer
    controller=BoundedTools(manifest)
    try:
        while True:
            line=inp.readline(4*1024*1024+1)
            if not line:break
            if len(line)>4*1024*1024:raise ProtocolError('Oversize MCP request')
            req=json.loads(line);id=req.get('id');method=req.get('method')
            if id is None:continue
            try:
                if method=='initialize':result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'mrhbench-bounded','version':'0.1.0'}}
                elif method=='ping':result={}
                elif method=='tools/list':result={'tools':controller.definitions}
                elif method=='tools/call':result=controller.call(req['params']['name'],req['params'].get('arguments',{}))
                else:raise ProtocolError('Unsupported MCP method')
                response={'jsonrpc':'2.0','id':id,'result':result}
            except Exception as e:
                if method=='tools/call':response={'jsonrpc':'2.0','id':id,'result':{'content':[{'type':'text','text':type(e).__name__+': '+str(e)}],'isError':True}}
                else:response={'jsonrpc':'2.0','id':id,'error':{'code':-32602,'message':str(e)}}
            out.write((json.dumps(response,ensure_ascii=False)+'\n').encode());out.flush()
    finally:controller.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);a=p.parse_args();serve(read_json(Path(a.manifest)))
