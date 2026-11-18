"""Disposable native CI probe. Never runs against a workstation or existing data."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.request
import uuid

LABEL = "org.oscar.alpine-spike"
ARCH = sys.argv[1]
assert os.environ.get("GITHUB_ACTIONS") == "true"
assert os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
assert os.environ.get("GITHUB_REPOSITORY") == "frisbeecz/docker-oscar"
assert os.environ.get("GITHUB_REF") == "refs/heads/spike/oscar-alpine"
assert platform.machine() == {"amd64": "x86_64", "arm64": "aarch64"}[ARCH]
OUT = Path("artifacts/alpine") / ARCH
OUT.mkdir(parents=True, exist_ok=True)
OWNER = uuid.uuid4().hex

CHECK = r'''
import glob,json,os,signal,sys,time,urllib.request
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote
phase,owner,expected_packages=sys.argv[1:]
packages={name:version(name) for name in json.loads(expected_packages)}
assert packages==json.loads(expected_packages),packages
assert os.getuid()==1000 and os.getgid()==1000
assert Path("/etc/alpine-release").read_text().startswith("3.24.")
assert os.environ["SELKIES_COMMAND_ENABLED"]=="false"
assert os.environ["SELKIES_UI_SIDEBAR_SHOW_APPS"]=="false"
assert os.environ["FILE_MANAGER_PATH"]=="/config/Uploads"
assert glob.glob("/usr/lib/qt6/plugins/sqldrivers/libqsqlite.so")

def mount_options(path,mountinfo):
 # Linux mountinfo records bind mounts even when parent/child share st_dev.
 for line in mountinfo.splitlines():
  fields=line.split()
  if len(fields)<7: continue
  target=fields[4]
  for escaped,decoded in ((r"\040"," "),(r"\011","\t"),(r"\012","\n"),(r"\134","\\")):
   target=target.replace(escaped,decoded)
  if target==path: return set(fields[5].split(","))
 return None

data=Path("/config/Documents/OSCAR20_Data")
mountinfo=Path("/proc/self/mountinfo").read_text()
mounts={p:mount_options(p,mountinfo) for p in
 ("/config",str(data),"/config/SDCARD")}
diagnostics={"mounts":{p:sorted(v) if v is not None else None
 for p,v in mounts.items()},"uid":os.getuid(),"gid":os.getgid(),
 "writable":os.access(data,os.W_OK),"legacyIsMount":os.path.ismount(data)}
try:
 owner_stat=data.stat()
except OSError as error:
 diagnostics.update(dataStatError=type(error).__name__,dataStatErrno=error.errno)
else:
 diagnostics.update(dataUid=owner_stat.st_uid,dataGid=owner_stat.st_gid,
  dataMode=oct(owner_stat.st_mode & 0o777))
print(json.dumps({"storageDiagnostics":diagnostics}),flush=True)
assert mounts["/config"] is not None and "rw" in mounts["/config"],"config mount missing or read-only"
assert mounts[str(data)] is not None and "rw" in mounts[str(data)],"data mount missing or read-only"
assert os.access(data,os.W_OK),"data directory is not writable by abc"
assert mounts["/config/SDCARD"] is not None and "ro" in mounts["/config/SDCARD"],"SD mount missing or writable"
marker=data/(".alpine-spike-"+owner)
relative=".alpine-spike-"+owner+"/nested/card-copy.txt"
uploaded=Path("/config/Uploads")/relative
payload=b"synthetic Alpine spike SD-copy fixture\n"

def apps():
 result=[]
 for p in Path("/proc").glob("[0-9]*"):
  try:
   argv=(p/"cmdline").read_bytes().split(b"\0")
   if argv and os.path.basename(argv[0])==b"OSCAR20":
    assert p.stat().st_uid==1000
    result.append(int(p.name))
  except FileNotFoundError: pass
 return result

def wait_app(exclude=None):
 deadline=time.monotonic()+120
 while time.monotonic()<deadline:
  found=apps()
  assert len(found)<=1,found
  if len(found)==1 and found[0]!=exclude:
   try:
    with urllib.request.urlopen("http://127.0.0.1:3000/",timeout=5) as r:
     if r.status==200: return found[0]
   except (OSError,urllib.error.URLError): pass
  time.sleep(1)
 raise RuntimeError("desktop application/HTTP startup timeout")

pid=wait_app()
time.sleep(5)
assert apps()==[pid],"OSCAR did not remain stable"
if phase=="initial":
 with marker.open("xb") as f:f.write(payload)
 request=urllib.request.Request("http://127.0.0.1:3000/api/upload",data=payload,
  headers={"Content-Type":"application/octet-stream","X-Upload-Path":quote(relative,safe="")})
 with urllib.request.urlopen(request,timeout=30) as r:assert r.status==200
 assert uploaded.read_bytes()==payload
 with urllib.request.urlopen("http://127.0.0.1:3000/api/file-manager/browse?path="+
  quote(relative.rsplit("/",1)[0],safe=""),timeout=15) as r:
  assert "card-copy.txt" in r.read().decode()
 with urllib.request.urlopen("http://127.0.0.1:3000/api/files/"+quote(relative,safe="/"),timeout=15) as r:
  assert r.read()==payload
 os.kill(pid,signal.SIGTERM)
 replacement=wait_app(exclude=pid)
 time.sleep(5)
 assert apps()==[replacement]
else:
 assert phase=="restarted"
 assert marker.read_bytes()==payload and uploaded.read_bytes()==payload
print(json.dumps({"phase":phase,"uid":os.getuid(),"alpine":Path("/etc/alpine-release").read_text().strip(),
 "pythonPackages":packages,
 "singleApplication":True,"http":True,"nestedUpload":True,
 "watchdog" if phase=="initial" else "retainedData":True}))
'''


def run(*args, **kwargs):
    return subprocess.check_output(list(args), text=True, **kwargs).strip()


volumes = []
container = None
try:
    for role in ("config", "data", "sdcard"):
        name = f"oscar-alpine-{OWNER}-{role}"
        run("docker", "volume", "create", "--label", f"{LABEL}={OWNER}", name)
        volumes.append(name)
    args = ["docker", "create", "--name", "oscar-alpine-" + OWNER,
            "--label", f"{LABEL}={OWNER}", "--publish", "127.0.0.1::3000",
            "--shm-size", "512m", "--security-opt", "no-new-privileges",
            "--cap-drop", "NET_RAW"]
    for name, target, suffix in zip(volumes,
            ("/config", "/config/Documents/OSCAR20_Data", "/config/SDCARD"), ("", "", ",readonly")):
        args += ["--mount", f"type=volume,source={name},target={target},volume-nocopy{suffix}"]
    for key, value in {
        "PUID": "1000", "PGID": "1000", "TZ": "Etc/UTC",
        "SELKIES_FILE_TRANSFERS": "upload,download", "SELKIES_UI_SIDEBAR_SHOW_FILES": "true",
        "FILE_MANAGER_PATH": "/config/Uploads", "SELKIES_COMMAND_ENABLED": "false",
        "SELKIES_UI_SIDEBAR_SHOW_APPS": "false", "DISABLE_WINDOW_BUTTONS": "true",
        "HARDEN_KEYBINDS": "false", "DISABLE_MOUSE_BUTTONS": "false",
    }.items():
        args += ["--env", key + "=" + value]
    container = run(*args, "oscar-alpine-spike:" + ARCH)
    run("docker", "start", container)
    port = run("docker", "inspect", "--format",
               '{{ (index (index .NetworkSettings.Ports "3000/tcp") 0).HostPort }}', container)
    deadline = time.monotonic() + 180
    while True:
        try:
            with urllib.request.urlopen("http://127.0.0.1:" + port + "/", timeout=5) as response:
                assert response.status == 200
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError("container HTTP startup timeout")
            time.sleep(1)
    results = []
    for phase in ("initial", "restarted"):
        if phase == "restarted":
            run("docker", "restart", "--time", "15", container)
        expected = json.loads(Path("spike/alpine/inputs.json").read_text())["pythonPackages"]
        completed = subprocess.run(
            ["docker", "exec", "-i", container, "s6-setuidgid", "abc", "/lsiopy/bin/python3",
             "-", phase, OWNER, json.dumps(expected)], input=CHECK, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = completed.stdout
        (OUT / f"runtime-{phase}.log").write_text(output)
        print(output, flush=True)
        completed.check_returncode()
        results.append([json.loads(line) for line in output.splitlines()])
        (OUT / "runtime.json").write_text(json.dumps(results, indent=2) + "\n")
finally:
    if container:
        label = run("docker", "inspect", "--format", '{{ index .Config.Labels "' + LABEL + '" }}', container)
        assert label == OWNER, "refusing cleanup of foreign container"
        (OUT / "container.log").write_text(run("docker", "logs", container, stderr=subprocess.STDOUT))
        run("docker", "rm", "--force", container)
    for volume in volumes:
        label = run("docker", "volume", "inspect", "--format", '{{ index .Labels "' + LABEL + '" }}', volume)
        assert label == OWNER, "refusing cleanup of foreign volume"
        run("docker", "volume", "rm", volume)
