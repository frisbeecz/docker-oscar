"""Small synthetic checks on the caller's owned, disposable container. Apache-2.0."""
import json
from pathlib import Path
import subprocess

from ci import output

CHECK = r'''
import glob,json,os,signal,sys,time,urllib.request
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote
phase,owner,expected_uid,expected_gid,expected_packages=sys.argv[1:]
expected_uid,expected_gid=int(expected_uid),int(expected_gid)

def check_identity(uid,gid,expected_uid,expected_gid):
 assert uid==expected_uid and gid==expected_gid and uid!=0 and gid!=0,"unprivileged identity mismatch"

def mount_options(path,mountinfo):
 for line in mountinfo.splitlines():
  fields=line.split()
  if len(fields)<7: continue
  target=fields[4]
  for escaped,decoded in ((r"\040"," "),(r"\011","\t"),(r"\012","\n"),(r"\134","\\")):
   target=target.replace(escaped,decoded)
  if target==path: return set(fields[5].split(","))
 return None

def storage_diagnostics(data,mountinfo):
 mounts={p:mount_options(p,mountinfo) for p in ("/config",str(data),"/config/SDCARD")}
 diagnostics={"mounts":{p:sorted(v) if v is not None else None for p,v in mounts.items()},
  "uid":os.getuid(),"gid":os.getgid(),"writable":os.access(data,os.W_OK)}
 try:
  state=data.stat()
 except OSError as error:
  diagnostics.update(dataStatError=type(error).__name__,dataStatErrno=error.errno)
 else:
  diagnostics.update(dataUid=state.st_uid,dataGid=state.st_gid,dataMode=oct(state.st_mode & 0o777))
 print(json.dumps({"storageDiagnostics":diagnostics}),flush=True)
 return mounts

def check_retained(marker,uploaded,payload):
 assert marker.read_bytes()==payload and uploaded.read_bytes()==payload,"synthetic data was not retained"

check_identity(os.getuid(),os.getgid(),expected_uid,expected_gid)
packages={name:version(name) for name in json.loads(expected_packages)}
assert packages==json.loads(expected_packages),packages
assert Path("/etc/alpine-release").read_text().startswith("3.24.")
assert os.environ["SELKIES_COMMAND_ENABLED"]=="false"
assert os.environ["SELKIES_UI_SIDEBAR_SHOW_APPS"]=="false"
assert os.environ["FILE_MANAGER_PATH"]=="/config/Uploads"
assert glob.glob("/usr/lib/qt6/plugins/sqldrivers/libqsqlite.so")
data=Path("/config/Documents/OSCAR20_Data")
mounts=storage_diagnostics(data,Path("/proc/self/mountinfo").read_text())
assert mounts["/config"] is not None and "rw" in mounts["/config"],"config mount missing or read-only"
assert mounts[str(data)] is not None and "rw" in mounts[str(data)],"data mount missing or read-only"
assert os.access(data,os.W_OK),"data directory is not writable by the application user"
assert mounts["/config/SDCARD"] is not None and "ro" in mounts["/config/SDCARD"],"SD mount missing or writable"
marker=data/(".oscar-ci-"+owner)
relative=".oscar-ci-"+owner+"/nested/card-copy.txt"
uploaded=Path("/config/Uploads")/relative
payload=b"synthetic OSCAR CI SD-copy fixture\n"

def apps():
 found=[]
 for path in Path("/proc").glob("[0-9]*"):
  try:
   argv=(path/"cmdline").read_bytes().split(b"\0")
   if argv and os.path.basename(argv[0])==b"OSCAR20":
    assert path.stat().st_uid==expected_uid
    found.append(int(path.name))
  except FileNotFoundError: pass
 return found

def wait_app(exclude=None):
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  found=apps()
  assert len(found)<=1,found
  if len(found)==1 and found[0]!=exclude: return found[0]
  time.sleep(1)
 raise RuntimeError("owned OSCAR20 process did not start")

if phase=="initial":
 # The controller already observed this process for ten seconds.
 found=apps()
 assert len(found)==1,found
 pid=found[0]
 with marker.open("xb") as stream: stream.write(payload)
 request=urllib.request.Request("http://127.0.0.1:3000/api/upload",data=payload,
  headers={"Content-Type":"application/octet-stream","X-Upload-Path":quote(relative,safe="")})
 with urllib.request.urlopen(request,timeout=30) as response: assert response.status==200
 assert uploaded.read_bytes()==payload
 with urllib.request.urlopen("http://127.0.0.1:3000/api/file-manager/browse?path="+
  quote(relative.rsplit("/",1)[0],safe=""),timeout=15) as response:
  assert "card-copy.txt" in response.read().decode()
 with urllib.request.urlopen("http://127.0.0.1:3000/api/files/"+quote(relative,safe="/"),timeout=15) as response:
  assert response.read()==payload
 os.kill(pid,signal.SIGTERM)
 replacement=wait_app(exclude=pid)
 time.sleep(5)
 assert apps()==[replacement],"replacement process was not stable"
 result={"unprivileged":True,"uploadRoundTrip":True,"watchdogRestart":True,"sdcardReadOnly":True}
else:
 assert phase=="restarted"
 wait_app()
 # Read before any fixture overwrite; these bytes must survive the restart.
 check_retained(marker,uploaded,payload)
 result={"dataRetained":True}
print(json.dumps(result),flush=True)
'''


def exercise(container, *, phase, uid, gid, expected_python, run_id, artifacts) -> dict:
    from ci.runtime import OWNER_LABEL, resource_prefix
    resource_prefix(run_id)  # Validate the identifier before passing it to the child.
    if phase not in ("initial", "restarted") or not container.startswith(f"oscar-ci-{run_id}-"):
        raise ValueError("functional checks require this run's owned container")
    inventory = json.loads(output(["docker", "container", "inspect", container]))[0]
    if inventory["Config"]["Labels"].get(OWNER_LABEL) != container:
        raise ValueError("refusing checks on an unowned container")
    completed = subprocess.run(
        ["docker", "exec", "--user", f"{uid}:{gid}", "-i", container, "/lsiopy/bin/python3",
         "-", phase, run_id, str(uid), str(gid), json.dumps(expected_python)],
        input=CHECK, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = Path(artifacts) / f"runtime-{phase}.log"
    log.write_text(completed.stdout)
    print(completed.stdout, flush=True)
    completed.check_returncode()
    checks = json.loads(completed.stdout.splitlines()[-1])
    expected = ({"unprivileged", "uploadRoundTrip", "watchdogRestart", "sdcardReadOnly"}
                if phase == "initial" else {"dataRetained"})
    if set(checks) != expected or any(checks[key] is not True for key in expected):
        raise ValueError("functional checks incomplete or failed")
    return checks
