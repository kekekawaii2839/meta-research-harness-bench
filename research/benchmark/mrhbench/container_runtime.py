"""Controller-owned, CPU-only Docker sessions with per-package limits.

Not a complete model broker or a claim of protection against kernel exploits.
Only controller-selected input files enter /inputs; no host directory is exposed
as solver-writable. Docker access and audit data stay outside the container.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import uuid
from pathlib import Path

from .docker_pilot import resource_args
from .io import ProtocolError, contained, file_hash, relative_path, utc_now, write_json

OWNER_LABEL = "mrhbench.session-owner"


class ArtifactHashError(ProtocolError):
    """Safe controller error code; no file content or private host paths."""
    def __init__(self, code):
        self.code = code
        super().__init__('Artifact hash operation ['+code+']: '+code.replace('_',' '))


def safe_artifact_extract(archive, destination, *, max_bytes, max_files):
    """Validate the ENTIRE tar before writing. Never use extract/extractall.

    Links, special files, sparse entries, traversal, Windows aliases, duplicate
    names, oversized metadata/file inventories and oversized contents fail closed.
    Destination must not already exist. Caller owns and bounds the tar byte stream.
    """
    if max_bytes < 1 or max_files < 1:
        raise ProtocolError("Explicit positive artifact limits required")
    destination = Path(destination)
    if destination.exists():
        raise ProtocolError("Artifact destination must be new")
    with tarfile.open(fileobj=archive if hasattr(archive, "read") else None,
                      name=None if hasattr(archive, "read") else str(archive), mode="r:") as tf:
        members = []; names = set(); total = 0
        for item in tf:
            if item.name in (".", "./") and item.isdir():
                continue
            name = item.name[2:] if item.name.startswith("./") else item.name
            name = name.rstrip("/") if item.isdir() else name
            relative_path(name)
            if not (item.isfile() or item.isdir()) or item.issparse():
                raise ProtocolError("Artifact links/special/sparse entries forbidden")
            key = name.casefold()
            if key in names:
                raise ProtocolError("Duplicate/case-aliased artifact path")
            names.add(key)
            if len(names) > max_files:
                raise ProtocolError("Artifact entry quota exceeded")
            total += item.size
            if item.size < 0 or total > max_bytes:
                raise ProtocolError("Artifact byte quota exceeded")
            members.append((name, item))
        file_names = {name.casefold() for name, item in members if item.isfile()}
        for name, item in members:
            if any(str(p).casefold() in file_names for p in relative_path(name).parents if str(p) != "."):
                raise ProtocolError("Artifact file/directory collision")
        destination.mkdir(parents=True, exist_ok=False)
        inventory = []
        try:
            for name, item in members:
                output = contained(destination, name)
                if item.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                source = tf.extractfile(item)
                remaining = item.size
                h = hashlib.sha256()
                with output.open("xb") as f:
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            raise ProtocolError("Truncated artifact")
                        remaining -= len(chunk); f.write(chunk); h.update(chunk)
                inventory.append({"path": name, "bytes": item.size, "sha256": h.hexdigest()})
        except Exception:
            # Caller receives a failure, never a success manifest for partial artifacts.
            raise
    return {"bytes": total, "files": inventory, "entries": len(members)}


# Controller helper uses isolated stdlib and descriptor-relative no-follow access;
# solver-created symlinks and concurrent renames cannot redirect host collection.
FILE_HELPER = r'''
import base64,json,os,stat,sys,hashlib,errno
q=json.load(sys.stdin); path=q['path']; pieces=path.split('/')
if pieces[0]!='' or len(pieces)<2 or pieces[1] not in ('work','inputs') or any(x in ('','.','..') for x in pieces[2:]): raise ValueError('bad path')
if q['op']=='hash_file':
 def hash_file():
  parent=None;f=None
  try:
   if len(pieces)<3:return {'ok':False,'error':'unsafe_path'}
   parent=os.open('/'+pieces[1],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
   for component in pieces[2:-1]:
    child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
    os.close(parent);parent=child
   f=os.open(pieces[-1],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=parent)
   before=os.fstat(f)
   if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1:return {'ok':False,'error':'unsafe_file_type_or_link'}
   if before.st_size>q['limit']:return {'ok':False,'error':'byte_limit_exceeded'}
   h=hashlib.sha256();size=0
   while True:
    chunk=os.read(f,min(65536,q['limit']-size+1))
    if not chunk:break
    size+=len(chunk)
    if size>q['limit']:return {'ok':False,'error':'byte_limit_exceeded'}
    h.update(chunk)
   after=os.fstat(f);named=os.stat(pieces[-1],dir_fd=parent,follow_symlinks=False)
   def signature(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink,s.st_mode)
   if size!=before.st_size or signature(before)!=signature(after) or signature(after)!=signature(named):return {'ok':False,'error':'file_changed_during_hash'}
   return {'ok':True,'bytes':size,'sha256':h.hexdigest(),'stable_during_read':True}
  except FileNotFoundError:return {'ok':False,'error':'not_found'}
  except PermissionError:return {'ok':False,'error':'access_denied'}
  except OSError as e:return {'ok':False,'error':'unsafe_path' if e.errno in (errno.ELOOP,errno.ENOTDIR) else 'hash_io_error'}
  finally:
   if f is not None:os.close(f)
   if parent is not None:os.close(parent)
 print(json.dumps(hash_file()));sys.exit(0)
if q['op']=='write' and pieces[1]!='work': raise ValueError('read-only inputs')
fd=os.open('/'+pieces[1],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:
 for x in pieces[2:-1]:
  if q['op']=='write':
   try: os.mkdir(x,mode=0o700,dir_fd=fd)
   except FileExistsError: pass
  nxt=os.open(x,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd); os.close(fd);fd=nxt
 if q['op']=='list':
  if len(pieces)>2:
   nxt=os.open(pieces[-1],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
  result=[]
  for name in os.listdir(fd):
   st=os.stat(name,dir_fd=fd,follow_symlinks=False)
   if len(result)>=q['limit']: raise ValueError('entry limit')
   result.append({'name':name,'bytes':st.st_size,'kind':'file' if stat.S_ISREG(st.st_mode) else 'directory' if stat.S_ISDIR(st.st_mode) else 'link_or_special'})
  print(json.dumps(sorted(result,key=lambda a:a['name'])))
 else:
  if len(pieces)<3: raise ValueError('file required')
  if q['op']=='write':
   data=base64.b64decode(q['data'],validate=True)
   try:
    st=os.stat(pieces[-1],dir_fd=fd,follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise ValueError('existing target must be regular single-link file')
   except FileNotFoundError:pass
   temp='.controller-tmp-'+os.urandom(16).hex()
   f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
   try:
    with os.fdopen(f,'wb') as out:out.write(data);out.flush()
    os.rename(temp,pieces[-1],src_dir_fd=fd,dst_dir_fd=fd)
   finally:
    try:os.unlink(temp,dir_fd=fd)
    except FileNotFoundError:pass
   print(json.dumps({'bytes':len(data),'atomic_replace':True}))
  else:
   f=os.open(pieces[-1],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=fd)
   try:
    st=os.fstat(f)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise ValueError('regular single-link file required')
    if st.st_size>q['limit']:raise ValueError('read byte limit')
    with os.fdopen(os.dup(f),'rb') as inp:data=inp.read(q['limit']+1)
    if len(data)>q['limit']:raise ValueError('read grew beyond limit')
    if q['op']=='read_raw':sys.stdout.buffer.write(data)
    else:print(json.dumps({'data':base64.b64encode(data).decode()}))
   finally:os.close(f)
finally:os.close(fd)
'''


EXPORT_HELPER = r'''import json,os,stat,sys,tarfile
q=json.loads(sys.argv[1]);count=0;size=0
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tf:
 def walk(fd,prefix):
  global count,size
  for name in sorted(os.listdir(fd)):
   if q.get('exclude_internal') and not prefix and (name=='.broker' or name.startswith('.process-')):continue
   count+=1
   if count>q['max_files']:raise ValueError('entry quota')
   path=prefix+name;st=os.stat(name,dir_fd=fd,follow_symlinks=False)
   if stat.S_ISDIR(st.st_mode):
    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
    try:
     info=tarfile.TarInfo(path+'/');info.type=tarfile.DIRTYPE;tf.addfile(info);walk(child,path+'/')
    finally:os.close(child)
   elif stat.S_ISREG(st.st_mode):
    child=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    try:
     current=os.fstat(child)
     if not stat.S_ISREG(current.st_mode) or current.st_nlink!=1:raise ValueError('not regular single-link file')
     size+=current.st_size
     if size>q['max_bytes']:raise ValueError('byte quota')
     info=tarfile.TarInfo(path);info.size=current.st_size
     with os.fdopen(os.dup(child),'rb') as inp:tf.addfile(info,inp)
    finally:os.close(child)
   else:raise ValueError('link or special file forbidden')
 root=os.open('/work',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:walk(root,'')
 finally:os.close(root)
'''


PROCESS_WRAPPER = r'''import base64,json,os,pathlib,signal,subprocess,sys,time
q=json.loads(base64.b64decode(sys.argv[1]));root=pathlib.Path(q['root']);root.mkdir(parents=True,exist_ok=False)
start=time.monotonic();limited=False;count=0
try:
 p=subprocess.Popen(q['argv'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
 with (root/'output.log').open('xb') as out:
  while True:
   chunk=p.stdout.read(65536)
   if not chunk:break
   allowed=max(0,q['cap']-count);count+=len(chunk);out.write(chunk[:allowed]);out.flush()
   if len(chunk)>allowed:
    limited=True;os.killpg(p.pid,signal.SIGKILL);break
 p.wait()
 status={'returncode':p.returncode,'output_limited':limited,'stdout_bytes':count,'wall_seconds':time.monotonic()-start}
except Exception as e:status={'error':str(e),'returncode':None}
temp=root/'status.tmp';temp.write_text(json.dumps(status));os.replace(temp,root/'status.json')
'''


class ContainerSession:
    """One session = one task attempt. No resume of a previous task's container.

    resources: cpus, memory_mb, disk_mb, pids_limit, wall_seconds; all mandatory.
    disk_mb is total tmpfs allowance, 80% /work and 20% /tmp, memory-charged.
    Model waiting counts toward the wall deadline. Per-command timeout or output
    overflow terminates the entire session to avoid orphan descendants.
    Control-plane operations/cleanup have separate bounded timeouts and are logged.
    """
    def __init__(self, *, image_id, resources, input_files, audit_dir,
                 input_hashes=None, max_log_bytes=1024*1024, max_input_bytes=64*1024*1024,
                 deadline_monotonic=None):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ProtocolError("Frozen local image ID required")
        resource_args(resources)
        if not 1024 <= max_log_bytes <= 16*1024*1024:
            raise ProtocolError("Invalid controller output bound")
        self.image_id = image_id; self.resources = dict(resources)
        self.input_files = dict(input_files); self.input_hashes = input_hashes
        self.audit_dir = Path(audit_dir).absolute()
        self.max_input_bytes = max_input_bytes; self.max_log_bytes = max_log_bytes
        self.owner = uuid.uuid4().hex; self.name = 'mrh-session-' + self.owner
        if deadline_monotonic is not None:
            if isinstance(deadline_monotonic,bool) or not isinstance(deadline_monotonic,(int,float)) or not math.isfinite(deadline_monotonic):
                raise ProtocolError('Absolute controller deadline must be finite monotonic time')
            if deadline_monotonic > time.monotonic()+resources['wall_seconds']:
                raise ProtocolError('Absolute deadline extends published wall allowance')
        self.cid = None; self.deadline = deadline_monotonic; self.started = False; self.closed = False
        self.expired = threading.Event(); self._stop = threading.Event()
        self._lock = threading.RLock(); self._io_lock = threading.RLock()
        self._seq = 0; self._watchdog = None

    def _record(self, label, result):
        with self._lock:
            self._seq += 1
            write_json(self.audit_dir / f'{self._seq:04d}-{label}.json', result, exclusive=True)

    def _command(self, argv, *, timeout, stdin=None, output_path=None,
                 output_limit=None, kill_session_on_limit=False):
        """Streaming bounded pipes, including a separately bounded raw tar export."""
        cap = output_limit if output_limit is not None else self.max_log_bytes
        begin = time.monotonic(); overflow = threading.Event()
        output = [bytearray(), bytearray()]; counts = [0, 0]
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        sink = open(output_path, 'xb') if output_path else None
        def drain(pipe, index):
            try:
                while True:
                    chunk = pipe.read(65536)
                    if not chunk: break
                    allowed = max(0, (cap if index == 0 else self.max_log_bytes) - counts[index])
                    counts[index] += len(chunk)
                    if index == 0 and sink: sink.write(chunk[:allowed])
                    else: output[index].extend(chunk[:allowed])
                    if len(chunk) > allowed: overflow.set()
            finally: pipe.close()
        def feed():
            try: proc.stdin.write(stdin); proc.stdin.close()
            except (BrokenPipeError, OSError): pass
        threads = [threading.Thread(target=drain, args=(proc.stdout,0), daemon=True),
                   threading.Thread(target=drain, args=(proc.stderr,1), daemon=True)]
        for t in threads:t.start()
        if stdin is not None:
            writer = threading.Thread(target=feed,daemon=True); writer.start()
        timed_out = False
        while proc.poll() is None:
            if time.monotonic()-begin >= timeout or overflow.is_set():
                timed_out = not overflow.is_set()
                proc.kill(); break
            time.sleep(.02)
        proc.wait(timeout=10)
        for t in threads:t.join(timeout=5)
        if sink: sink.close()
        if kill_session_on_limit and (timed_out or overflow.is_set()):
            self.expired.set(); self._stop.set()
            self._kill_owned()
        result = {"argv": argv, "returncode": proc.returncode,
                  "stdout": bytes(output[0]).decode('utf8',errors='replace'),
                  "stderr": bytes(output[1]).decode('utf8',errors='replace'),
                  "stdout_bytes": counts[0], "stderr_bytes": counts[1],
                  "timed_out": timed_out, "output_limited": overflow.is_set(),
                  "wall_seconds": time.monotonic()-begin}
        return result

    def _control(self, args, label, timeout=30):
        r = self._command(['docker', *args], timeout=timeout)
        self._record(label, r)
        if r['returncode'] != 0 or r['timed_out'] or r['output_limited']:
            raise ProtocolError('Container control failed: '+label)
        return r['stdout'].strip()

    def _assert_owned(self):
        if not self.cid or not re.fullmatch(r'[0-9a-f]{64}', self.cid):
            raise ProtocolError('No exact owned container ID')
        raw = self._command(['docker','inspect','--format','{{json .Config.Labels}}',self.cid],timeout=15)
        if raw['returncode'] != 0 or json.loads(raw['stdout']).get(OWNER_LABEL) != self.owner:
            raise ProtocolError('Container owner mismatch; refusing destructive control')

    def _kill_owned(self):
        with self._lock:
            if not self.cid or self.closed:return
            try:
                self._assert_owned()
                r = self._command(['docker','kill',self.cid], timeout=15)
                self._record('kill_owned',r)
            except Exception as e:
                self._record('kill_failed',{'error':str(e)})

    def _watch(self):
        if not self._stop.wait(max(0,self.deadline-time.monotonic())):
            self.expired.set(); self._kill_owned()

    def start(self):
        if self.started or self.closed:raise ProtocolError('Session cannot restart')
        if self.deadline is not None and self.remaining_seconds<=0:
            raise ProtocolError('Controller deadline exhausted before session preparation')
        self.audit_dir.mkdir(parents=True, exist_ok=False)
        release = self.audit_dir / 'release'; release.mkdir()
        total = 0; inventory=[]; seen=set()
        for name, src in self.input_files.items():
            relative_path(name)
            if name.casefold() in seen:raise ProtocolError('Case-aliased input name')
            seen.add(name.casefold())
            src=Path(src)
            if src.is_symlink() or (hasattr(src,'is_junction') and src.is_junction()) or not src.is_file():
                raise ProtocolError('Input must be a regular, nonlinked controller-selected file')
            # Check ancestors too; .resolve alone would hide a junction/symlink.
            if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in src.parents):
                raise ProtocolError('Linked input ancestor')
            if total + src.stat().st_size > self.max_input_bytes:raise ProtocolError('Input release quota exceeded')
            dest=contained(release,name);dest.parent.mkdir(parents=True,exist_ok=True)
            with src.open('rb') as inp, dest.open('xb') as out:
                while True:
                    chunk=inp.read(65536)
                    if not chunk:break
                    total += len(chunk)
                    if total > self.max_input_bytes:raise ProtocolError('Growing input exceeds release quota')
                    out.write(chunk)
            h=file_hash(dest)
            if self.input_hashes is not None and self.input_hashes.get(name) != h:
                raise ProtocolError('Released input hash mismatch')
            inventory.append({'path':name,'bytes':dest.stat().st_size,'sha256':h})
        release=release.resolve()
        if any(c in str(release) for c in ',\n\r'):raise ProtocolError('Invalid mount path')
        threads = str(max(1,math.floor(self.resources['cpus'])))
        args=['create','--name',self.name,'--label',OWNER_LABEL+'='+self.owner,
              '--platform','linux/amd64','--pull','never','--network','none','--read-only',
              '--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges=true',
              '--ipc','none','--log-driver','local','--log-opt','max-size=1m','--log-opt','max-file=2',
              *resource_args(self.resources),'--mount',f'type=bind,src={release},dst=/inputs,readonly',
              '--workdir','/work','--env','HOME=/work','--env','TMPDIR=/tmp','--env','MPLBACKEND=Agg',
              '--env','MPLCONFIGDIR=/tmp/matplotlib','--env','PYTHONDONTWRITEBYTECODE=1',
              '--env','OMP_NUM_THREADS='+threads,'--env','OPENBLAS_NUM_THREADS='+threads,
              '--entrypoint','python',self.image_id,'-I','-S','-c','import time; time.sleep(2147483647)']
        self._record('manifest',{'created':utc_now(),'owner':self.owner,'image_id':self.image_id,
                                'resources':self.resources,'inputs':inventory,
                                'disk_semantics':'sum of /work and /tmp tmpfs ceilings, memory-charged',
                                'formal_isolation_accepted':False,
                                'controller_deadline_monotonic':self.deadline})
        try:
            if self.deadline is not None and self.remaining_seconds<=0:
                raise ProtocolError('Controller deadline exhausted while staging inputs')
            self.cid=self._control(args,'create')
            if not re.fullmatch(r'[0-9a-f]{64}',self.cid):
                self.cid=None;raise ProtocolError('Invalid container ID')
            self._assert_owned()
            # Start deadline before daemon start, not after arbitrary first tool call.
            if self.deadline is None:
                self.deadline=time.monotonic()+self.resources['wall_seconds']
            if self.remaining_seconds<=0:
                raise ProtocolError('Controller deadline exhausted before container start')
            self._control(['start',self.cid],'start',timeout=min(30,self.remaining_seconds))
            self.started=True
            self._watchdog=threading.Thread(target=self._watch,daemon=True);self._watchdog.start()
            self._record('inspect_start',json.loads(self._control(['inspect',self.cid],'inspect'))[0])
        except Exception:
            self.close();raise
        return self

    @property
    def remaining_seconds(self):
        return max(0.,self.deadline-time.monotonic()) if self.deadline else 0.

    def _live(self):
        if not self.started or self.closed or self.expired.is_set() or self.remaining_seconds <= 0:
            raise ProtocolError('Container session unavailable or deadline exhausted')

    def exec(self, argv, timeout=None, *, _stdin=None):
        if not isinstance(argv,(list,tuple)) or not argv or any(not isinstance(x,str) or '\x00' in x for x in argv):
            raise ProtocolError('exec requires a nonempty argv of strings')
        if timeout is not None and (not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not math.isfinite(timeout) or timeout<=0):
            raise ProtocolError('Invalid command timeout')
        with self._io_lock:
            self._live()
            allowance=min(self.remaining_seconds,timeout if timeout is not None else self.remaining_seconds)
            result=self._command(['docker','exec',*(['-i'] if _stdin is not None else []),self.cid,*argv],
                                 timeout=allowance,stdin=_stdin,kill_session_on_limit=True)
            if self.expired.is_set():result['session_expired']=True
            self._record('exec',result)
            return result

    def exec_python_snapshot(self, script_path, argv=None, timeout=None):
        """Execute immutable entry bytes; imported dependencies remain mutable.

        The private host audit stores exact entrypoint bytes/hash. A solver can
        still run arbitrary computation in its worker; this receipt covers only
        this controller-dispatched entrypoint, not all task CPU activity.
        """
        if not isinstance(script_path,str) or not script_path.startswith('/work/') or not script_path.endswith('.py'):
            raise ProtocolError('Snapshot entrypoint must be a /work Python file')
        relative_path(script_path[len('/work/'):])
        argv=[] if argv is None else argv
        if not isinstance(argv,(list,tuple)) or any(not isinstance(x,str) or '\x00' in x for x in argv):
            raise ProtocolError('Snapshot argv must contain strings')
        with self._io_lock:
            source=self.read(script_path,max_bytes=2*1024*1024)
            sha=hashlib.sha256(source).hexdigest()
            folder=self.audit_dir/'executed-entrypoints';folder.mkdir(exist_ok=True)
            snapshot=folder/(sha+'.py')
            if not snapshot.exists():
                with snapshot.open('xb') as out:out.write(source)
            if file_hash(snapshot)!=sha:raise ProtocolError('Private entry snapshot changed')
            receipt={'execution_id':uuid.uuid4().hex,'entrypoint':script_path,'entrypoint_sha256':sha,
                     'entrypoint_bytes':len(source),'snapshot_path':'executed-entrypoints/'+snapshot.name,
                     'argv':list(argv),'cwd':'/work','scope':'entrypoint_snapshot_only',
                     'dependencies_frozen':False,'container_id':self.cid}
            self._record('python_snapshot_requested',receipt)
            payload=json.dumps({'source':base64.b64encode(source).decode(),'path':script_path,'argv':list(argv)}).encode()
            wrapper=("import base64,json,sys,os; q=json.load(sys.stdin); "
                     "source=base64.b64decode(q['source'],validate=True); "
                     "sys.argv=[q['path'],*q['argv']]; "
                     "sys.path.insert(0,'/work');sys.path.insert(0,os.path.dirname(q['path'])); "
                     "exec(compile(source,q['path'],'exec'),{'__name__':'__main__','__file__':q['path'],'__package__':None,'__cached__':None})")
            result=self.exec(['python','-I','-c',wrapper],timeout=timeout,_stdin=payload)
            result['execution_receipt']=receipt
            self._record('python_snapshot_completed',{'execution_id':receipt['execution_id'],
                         'entrypoint_sha256':sha,'returncode':result['returncode'],
                         'timed_out':result['timed_out'],'output_limited':result['output_limited'],
                         'stdout_sha256':hashlib.sha256(result['stdout'].encode()).hexdigest(),
                         'stderr_sha256':hashlib.sha256(result['stderr'].encode()).hexdigest()})
            return result

    def start_process(self, argv):
        """Detached worker. Status/log files are solver-writable, NOT trusted telemetry.

        Controller deadlines and resource limits are independent of these files.
        A process output overflow kills that process group; the session remains.
        """
        if not isinstance(argv,(list,tuple)) or not argv or any(not isinstance(x,str) or '\x00' in x for x in argv):
            raise ProtocolError('start_process requires argv strings')
        root='/work/.process-'+uuid.uuid4().hex
        spec={'root':root,'argv':list(argv),'cap':self.max_log_bytes}
        encoded=base64.b64encode(json.dumps(spec).encode()).decode()
        if len(encoded)>12000:raise ProtocolError('Detached command too long; write a script first')
        with self._io_lock:
            self._live()
            self._control(['exec','-d',self.cid,'python','-I','-S','-c',PROCESS_WRAPPER,encoded],
                          'start_process',timeout=min(30,self.remaining_seconds))
        return {'session_owner':self.owner,'root':root,'status_trust':'solver_writable_report_only'}

    def poll_process(self, handle):
        if handle.get('session_owner')!=self.owner or not re.fullmatch(r'/work/\.process-[a-f0-9]{32}',handle.get('root','')):
            raise ProtocolError('Process handle belongs to another session')
        root=handle['root']
        # Initial mkdir may not yet have happened; absence is pending, not failure.
        names={x['name'] for x in self.list('/work')}
        if root.rsplit('/',1)[-1] not in names:
            return {'status':'pending','trusted':False}
        names={x['name'] for x in self.list(root)}
        if 'status.json' not in names:return {'status':'running','trusted':False}
        status=json.loads(self.read(root+'/status.json',max_bytes=16384))
        return {'status':'reported_complete','trusted':False,'reported':status}

    def _file(self, payload):
        result=self.exec(['python','-I','-S','-c',FILE_HELPER],_stdin=json.dumps(payload).encode())
        if result['returncode'] != 0 or result['timed_out'] or result['output_limited']:
            raise ProtocolError('Container file operation failed; see audit')
        return json.loads(result['stdout'])

    def hash_file(self,path,*,max_bytes):
        """Stream hash in-container, never transfer file bytes to stdout/host.

        Explicit cap must fit package disk; zero allows only an empty file.
        Metadata stability detects common concurrent changes, not a cross-file
        atomic snapshot. Collection must still recheck the captured file hash.
        """
        if not isinstance(path,str) or '\x00' in path or '\\' in path:
            raise ArtifactHashError('unsafe_path')
        pieces=path.split('/')
        if len(pieces)<3 or pieces[0]!='' or pieces[1] not in ('work','inputs') or any(x in ('','.','..') for x in pieces[2:]):
            raise ArtifactHashError('unsafe_path')
        if isinstance(max_bytes,bool) or not isinstance(max_bytes,int) or not 0<=max_bytes<=self.resources['disk_mb']*1024*1024:
            raise ArtifactHashError('invalid_or_unpublished_limit')
        with self._io_lock:
            self._live()
            result=self._file({'op':'hash_file','path':path,'limit':max_bytes})
            self._record('hash_file_receipt',{'path':path,'limit_bytes':max_bytes,**result})
            if not result.get('ok'):
                raise ArtifactHashError(result.get('error','hash_operation_failed'))
            if (type(result.get('bytes')) is not int or not 0<=result['bytes']<=max_bytes or
                    not re.fullmatch('[0-9a-f]{64}',result.get('sha256',''))):
                raise ArtifactHashError('invalid_hash_receipt')
            return {'path':path,'bytes':result['bytes'],'sha256':result['sha256'],
                    'limit_bytes':max_bytes,'stable_during_read':True,
                    'snapshot_scope':'single_descriptor_not_atomic_with_collection'}

    def read(self,path,max_bytes=256*1024):
        """Bounded binary read (up to 64 MiB), never logs pixel/base64 content."""
        if not isinstance(max_bytes,int) or isinstance(max_bytes,bool) or not 0<max_bytes<=64*1024*1024:
            raise ProtocolError('Read quota must be 1..64MiB')
        with self._io_lock:
            self._live()
            dest=self.audit_dir/('.binary-read-'+uuid.uuid4().hex)
            payload=json.dumps({'op':'read_raw','path':path,'limit':max_bytes}).encode()
            try:
                result=self._command(['docker','exec','-i',self.cid,'python','-I','-S','-c',FILE_HELPER],
                                     timeout=self.remaining_seconds,stdin=payload,output_path=dest,
                                     output_limit=max_bytes,kill_session_on_limit=True)
                result['path']=path
                if result['returncode']!=0 or result['timed_out'] or result['output_limited']:
                    self._record('read_failed',result)
                    raise ProtocolError('Container binary read failed; see audit')
                data=dest.read_bytes()
                result['sha256']=hashlib.sha256(data).hexdigest();result['bytes']=len(data)
                self._record('read_binary_receipt',result)
                return data
            finally:
                if dest.exists():dest.unlink()

    def write(self,path,data):
        if not isinstance(data,bytes) or len(data)>self.max_log_bytes:raise ProtocolError('Bounded bytes required')
        return self._file({'op':'write','path':path,'data':base64.b64encode(data).decode()})

    def list(self,path='/work',max_files=1000):
        if not 0<max_files<=10000:raise ProtocolError('Invalid listing quota')
        return self._file({'op':'list','path':path,'limit':max_files})

    def artifacts(self,destination,*,max_bytes,max_files=10000,exclude_internal=False):
        if not isinstance(exclude_internal,bool):raise ProtocolError('Artifact exclusion flag must be boolean')
        if not isinstance(max_bytes,int) or isinstance(max_bytes,bool) or not 0<max_bytes<=self.resources['disk_mb']*1024*1024:
            raise ProtocolError('Artifact bytes must be within package writable allowance')
        if not isinstance(max_files,int) or isinstance(max_files,bool) or not 0<max_files<=100000:
            raise ProtocolError('Artifact entry bound invalid')
        with self._io_lock:
            self._live(); self._assert_owned()
            archive=self.audit_dir/('artifact-'+uuid.uuid4().hex+'.tar')
            try:
                # docker cp ignores this Docker backend's tmpfs contents. Export
                # via descriptor-relative no-follow reads inside the running
                # namespace instead. The capture is NOT an atomic FS snapshot;
                # callers should finish solver work before collecting.
                spec=json.dumps({'max_bytes':max_bytes,'max_files':max_files,'exclude_internal':exclude_internal})
                result=self._command(['docker','exec',self.cid,'python','-I','-S','-c',EXPORT_HELPER,spec],
                                     timeout=self.remaining_seconds, output_path=archive,
                                     output_limit=max_bytes+max_files*2048+1024*1024,
                                     kill_session_on_limit=True)
                self._record('artifact_export',result)
                if result['returncode'] != 0 or result['timed_out'] or result['output_limited']:
                    raise ProtocolError('Artifact export failed')
                receipt=safe_artifact_extract(archive,destination,max_bytes=max_bytes,max_files=max_files)
                receipt['atomic_snapshot']=False
                receipt['excluded_top_level_rules']=['.broker','.process-*'] if exclude_internal else []
                self._record('artifact_receipt',receipt)
                return receipt
            finally:
                if archive.exists():archive.unlink()

    def close(self):
        self._stop.set()
        with self._lock:
            if self.closed:return
            if self.cid:
                self._assert_owned()
                self._control(['rm','-f',self.cid],'remove_owned')
            self.closed=True
        if self._watchdog and threading.current_thread() is not self._watchdog:
            self._watchdog.join(timeout=20)

    def __enter__(self):return self.start()
    def __exit__(self,*exc):self.close()
