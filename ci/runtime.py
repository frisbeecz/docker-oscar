"""Native functional gate; only synthetic data in owned disposable volumes.

SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

from ci import ROOT, canonical_json, load_lock, output, receipt, run, sha256_file
from ci.build_image import require_native, require_native_daemon, verify_import

OWNER_LABEL = "io.docker-oscar.ci-owner"
DATADIR = "/config/Documents/OSCAR20_Data"
PROFILE = "ci-synthetic"
TEST_SCOPE = "container-functional-v1"
REQUIRED_CHECKS = {"containerRunning", "httpReady", "oscarStable", "unprivileged",
                   "uploadRoundTrip", "watchdogRestart", "dataRetained", "sdcardReadOnly"}

# Read-only application inspection. No SQL INSERT/UPDATE, PRAGMA writes,
# config edits, or manufactured profile files are permitted here.
AUDIT_SCRIPT = r'''
import configparser, hashlib, json, os, pathlib, sqlite3
home=pathlib.Path("/config")
data=home/"Documents/OSCAR20_Data"
result={"profiles": [], "language": "", "data": [], "dataFiles": [], "qtConfig": [], "outsideDatabases": []}
for p in sorted(data.rglob("*")):
    if not p.is_file() or p.is_symlink(): continue
    s=p.stat()
    result["dataFiles"].append({"path":str(p.relative_to(home)), "uid":s.st_uid, "gid":s.st_gid})
    if p.suffix not in (".db", ".sqlite", ".sqlite3"): continue
    if p.open("rb").read(16) != b"SQLite format 3\x00": continue
    s=p.stat()
    con=sqlite3.connect(p.as_uri()+"?mode=ro", uri=True)
    try:
        integrity=con.execute("PRAGMA quick_check").fetchall()
        if integrity != [("ok",)]: raise ValueError("SQLite integrity failure: "+str(p))
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "profiles" in tables:
            result["profiles"].extend(r[0] for r in con.execute("SELECT username FROM profiles ORDER BY username"))
    finally: con.close()
    result["data"].append({"path":str(p.relative_to(home)), "uid":s.st_uid, "gid":s.st_gid,
                           "integrity":"ok", "sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
for p in sorted((home/".config").rglob("*.conf")):
    if p.is_symlink(): continue
    parser=configparser.ConfigParser(interpolation=None, strict=False)
    try: parser.read(p)
    except (configparser.Error, UnicodeError): continue
    language=parser.get("Settings","Language",fallback="")
    if language:
        s=p.stat()
        result["language"]=language
        result["qtConfig"].append({"path":str(p.relative_to(home)), "uid":s.st_uid, "gid":s.st_gid,
                                   "sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
for root in ["/config","/tmp","/home","/root","/opt/oscar"]:
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:]=[d for d in dirs if not pathlib.Path(directory,d).is_symlink()]
        for name in files:
            p=pathlib.Path(directory,name)
            if p.is_symlink() or data in p.parents: continue
            if p.suffix in (".db",".sqlite",".sqlite3"):
                with p.open("rb") as f: header=f.read(16)
                if header == b"SQLite format 3\x00": result["outsideDatabases"].append(str(p))
print(json.dumps(result))
'''

PROCESS_SCRIPT = r'''
import json, pathlib
found=[]
for p in pathlib.Path("/proc").iterdir():
    if not p.name.isdecimal(): continue
    try:
        if (p/"comm").read_text().strip() != "OSCAR20": continue
        status=dict(line.split(":",1) for line in (p/"status").read_text().splitlines() if ":" in line)
        found.append({"pid":int(p.name),"uid":int(status["Uid"].split()[1]),
                      "gid":int(status["Gid"].split()[1]),"start":(p/"stat").read_text().split()[21],
                      "exe":str((p/"exe").readlink()),
                      "args":(p/"cmdline").read_bytes().decode().rstrip("\x00").split("\x00")})
    except FileNotFoundError: pass
print(json.dumps(found))
'''


def resource_prefix(run_id):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", run_id):
        raise ValueError("run-id must be 1..48 lowercase alphanumeric/hyphen characters")
    return f"oscar-ci-{run_id}-{uuid.uuid4().hex[:10]}"


def container_command(image, name, volumes, *, readonly_data=False):
    command = [
        "docker", "run", "-d", "--pull=never", "--name", name,
        "--label", f"{OWNER_LABEL}={name}",
        "--security-opt", "no-new-privileges=true", "--cap-drop=NET_RAW",
        "--shm-size=512m", "-p", "127.0.0.1::3000",
    ]
    for value in [
        "PUID=1234", "PGID=2345", "TZ=Etc/UTC", "LC_ALL=en_US.UTF-8", "LANG=en_US.UTF-8",
        "PIXELFLUX_WAYLAND=true", "RESTART_APP=true", "HARDEN_DESKTOP=true",
        "START_DOCKER=false", "LIBGL_ALWAYS_SOFTWARE=true", "SELKIES_USE_CPU=true",
        "SELKIES_ENCODER=h264enc", "SELKIES_MANUAL_RESOLUTION=true",
        "SELKIES_MANUAL_WIDTH=1280", "SELKIES_MANUAL_HEIGHT=800",
        "SELKIES_FILE_TRANSFERS=upload,download", "SELKIES_UI_SIDEBAR_SHOW_FILES=true",
        "FILE_MANAGER_PATH=/config/Uploads", "SELKIES_COMMAND_ENABLED=false",
        "SELKIES_UI_SIDEBAR_SHOW_APPS=false", "DISABLE_WINDOW_BUTTONS=true",
        "HARDEN_KEYBINDS=false", "DISABLE_MOUSE_BUTTONS=false",
    ]:
        command += ["-e", value]
    for kind, destination in [("config", "/config"), ("data", DATADIR), ("sdcard", "/config/SDCARD")]:
        mount = f"type=volume,src={volumes[kind]},dst={destination},volume-nocopy"
        if kind == "sdcard" or (kind == "data" and readonly_data):
            mount += ",readonly"
        command += ["--mount", mount]
    return [*command, image]


def is_media_frame(payload):
    # Pinned Selkies2.2.1: typed binary JPEG(3)/video-stripe(4) frames.
    # Audio(1), control(5), and bandwidth padding(7) must never count as media.
    return isinstance(payload, bytes) and len(payload) > 32 and payload[0] in (3, 4)


def validate_checks(checks):
    if (not isinstance(checks, dict) or set(checks) != REQUIRED_CHECKS
            or any(checks[k] is not True for k in REQUIRED_CHECKS)):
        raise ValueError("runtime checks incomplete or failed")


def failure_metadata(error, *, negative=False):
    result = {"exitCode": 1, "error": f"{type(error).__name__}: {error}"}
    if negative:
        from ci import gui
        expected = isinstance(error, gui.GUIFailure)
        result.update(expectedFailure=expected,
                      failureKind="missing-oscar-gui-profile" if expected else "harness-error")
    return result


def validate_audit(audit, profile):
    if (profile not in audit["profiles"] or audit["language"] != "en_US"
            or not audit["data"] or not audit["dataFiles"] or not audit["qtConfig"] or audit["outsideDatabases"]):
        raise ValueError("application profile/language/separate persistence or no-fallback audit failed")
    for item in [*audit["data"], *audit["dataFiles"], *audit["qtConfig"]]:
        if item["uid"] != 1234 or item["gid"] != 2345:
            raise ValueError("application state ownership mismatch")
    if any(item["integrity"] != "ok" or not item["path"].startswith("Documents/OSCAR20_Data/")
           for item in audit["data"]):
        raise ValueError("data path/integrity mismatch")
    if any(not item["path"].startswith(".config/") for item in audit["qtConfig"]):
        raise ValueError("Qt settings are not separately persisted")


class Resources:
    def __init__(self, prefix, artifacts):
        self.prefix, self.artifacts = prefix, artifacts
        self.volumes, self.containers = [], []

    def volume(self, role):
        name = self.prefix + "-" + role
        # UUID names plus explicit existing-name rejection avoid adopting host resources.
        existing = output(["docker", "volume", "ls", "--format", "{{.Name}}"]).splitlines()
        if name in existing:
            raise ValueError("refusing to adopt existing volume")
        run(["docker", "volume", "create", "--label", f"{OWNER_LABEL}={name}", name])
        self.volumes.append(name)
        return name

    def start(self, image, role, volumes, *, readonly_data=False):
        name = self.prefix + "-" + role
        # Register after create, before start: failed init/daemon start must not
        # leave an identified owned container outside cleanup's inventory.
        command = container_command(image, name, volumes, readonly_data=readonly_data)
        run(["docker", "create", *command[3:]])
        self.containers.append(name)
        run(["docker", "start", name])
        return name

    def check_owner(self, kind, name):
        data = json.loads(output(["docker", kind, "inspect", name]))[0]
        labels = data["Config"]["Labels"] if kind == "container" else data["Labels"]
        if labels.get(OWNER_LABEL) != name:
            raise ValueError(f"refusing cleanup of unowned {kind}: {name}")

    def remove_container(self, name):
        self.check_owner("container", name)
        logs = subprocess.run(["docker", "logs", name], capture_output=True, cwd=ROOT)
        (self.artifacts / f"{name}.log").write_bytes(logs.stdout + logs.stderr)
        if logs.returncode != 0:
            raise RuntimeError("cannot collect owned container logs")
        run(["docker", "rm", "-f", name])
        self.containers.remove(name)

    def cleanup(self):
        # No prune, wildcard deletion, host mounts, or cleanup of pre-existing resources.
        for name in list(reversed(self.containers)):
            self.remove_container(name)
        for name in list(reversed(self.volumes)):
            self.check_owner("volume", name)
            run(["docker", "volume", "rm", name])
            self.volumes.remove(name)


def running_container(container):
    data = json.loads(output(["docker", "inspect", container]))[0]
    if data["State"]["Running"] is not True:
        raise ValueError("owned container is not running")
    return data


def wait_http(container):
    data = running_container(container)
    binding = data["NetworkSettings"]["Ports"]["3000/tcp"]
    if len(binding) != 1 or binding[0]["HostIp"] != "127.0.0.1":
        raise ValueError("runtime web binding must be loopback only")
    url = "http://127.0.0.1:" + binding[0]["HostPort"]
    deadline = time.monotonic() + 90
    while True:
        running_container(container)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("owned Selkies HTTP service did not become ready")
        try:
            with urllib.request.urlopen(url, timeout=min(3, remaining)) as response:
                if response.status == 200 and time.monotonic() <= deadline:
                    running_container(container)
                    return url
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            # Service startup polling, not a retry of a failed image/tool acquisition.
            pass
        if time.monotonic() >= deadline:
            raise TimeoutError("owned Selkies HTTP service did not become ready")
        time.sleep(1)


def validate_process(process):
    if (not isinstance(process, dict)
            or type(process.get("pid")) is not int or process["pid"] <= 0
            or not isinstance(process.get("start"), str)
            or not re.fullmatch(r"[0-9]+", process["start"])
            or type(process.get("uid")) is not int or process["uid"] != 1234
            or type(process.get("gid")) is not int or process["gid"] != 2345
            or process.get("exe") != "/usr/bin/OSCAR20"
            or process.get("args") != ["OSCAR20", "--legacy", "--datadir", DATADIR]):
        raise ValueError("unprivileged native OSCAR20 process identity mismatch")


def application_process(container, *, allow_missing=False):
    # /proc/<pid>/exe has ptrace-style UID checks. Inspect as the app user,
    # rather than requiring CAP_SYS_PTRACE on a root docker-exec process.
    processes = json.loads(output(["docker", "exec", "--user", "1234:2345",
                                   container, "python3", "-c", PROCESS_SCRIPT]))
    if allow_missing and processes == []:
        return None
    if not isinstance(processes, list) or len(processes) != 1:
        raise ValueError("exactly one unprivileged native OSCAR20 process required")
    validate_process(processes[0])
    return processes[0]


def observe_startup(container):
    """Allow an initially absent process, never a replacement once observed."""
    deadline = time.monotonic() + 90
    initial, started = None, None
    while True:
        running_container(container)
        process = application_process(container, allow_missing=initial is None)
        running_container(container)
        now = time.monotonic()
        if initial is None:
            if now > deadline:
                raise TimeoutError("OSCAR20 did not start within 90 seconds")
            if process is not None:
                initial, started = process, now
            elif now >= deadline:
                raise TimeoutError("OSCAR20 did not start within 90 seconds")
        elif (process["pid"], process["start"]) != (initial["pid"], initial["start"]):
            raise ValueError("OSCAR20 process changed during startup observation")
        if started is not None and now - started >= 10:
            return initial, now - started
        time.sleep(1)


def audit(container):
    return json.loads(output(["docker", "exec", container, "python3", "-c", AUDIT_SCRIPT]))


def check_sd_readonly(container):
    script = ("import errno,pathlib\n"
              "try: pathlib.Path('/config/SDCARD/.ci-write-probe').write_text('synthetic')\n"
              "except OSError as e:\n"
              " assert e.errno == errno.EROFS, str(e)\n"
              "else: raise AssertionError('SD mount was writable')\n")
    run(["docker", "exec", "--user", "1234:2345", container, "python3", "-c", script])
    mounts = json.loads(output(["docker", "inspect", container]))[0]["Mounts"]
    if not any(m["Destination"] == "/config/SDCARD" and not m["RW"] for m in mounts):
        raise ValueError("SD is not a separate read-only volume")


def preflight_tools():
    tools = load_lock("ci/tools.lock.json")
    if importlib.metadata.version("playwright") != tools["playwright"]["version"]:
        raise ValueError("unsupported Playwright version")
    if output(["tesseract", "--version"]).splitlines()[0].split()[-1] != tools["tesseract"]["version"]:
        raise ValueError("unsupported Tesseract version")
    data = Path(os.environ["TESSDATA_PREFIX"]) / "eng.traineddata"
    if sha256_file(data) != tools["tesseract"]["english"]["sha256"]:
        raise ValueError("Tesseract English data checksum mismatch")


def open_page(context, url, frames):
    page = context.new_page()
    def websocket(socket):
        entry = {"path": urlsplit(socket.url).path, "mediaFrames": 0, "mediaBytes": 0}
        frames.append(entry)
        def received(payload):
            if is_media_frame(payload):
                entry["mediaFrames"] += 1
                entry["mediaBytes"] += len(payload)
        socket.on("framereceived", received)
    page.on("websocket", websocket)
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    if not page.evaluate("window.isSecureContext && typeof VideoDecoder !== 'undefined'"):
        raise ValueError("secure context with WebCodecs required")
    # Dashboard UI may expose Connect; Qt itself is always driven through pixels.
    connect = page.get_by_role("button", name=re.compile(r"^Connect$", re.I))
    if connect.count() == 1 and connect.is_visible():
        connect.click()
    page.evaluate("""() => {
        const message = {type:'setManualResolution',width:1280,height:800};
        window.postMessage(message, location.origin);
        for (const frame of document.querySelectorAll('iframe')) frame.contentWindow.postMessage(message, location.origin);
    }""")
    return page


def execute(args, result, resources):
    if args.negative_base_probe:
        # Historical, explicitly non-gating helper. Normal smoke never imports GUI.
        return execute_legacy_gui(args, result, resources)
    require_native_daemon(args.arch)
    image = json.loads(output(["docker", "image", "inspect", args.image]))[0]
    require_native(args.arch, system="Linux" if image["Os"] == "linux" else image["Os"],
                   machine=image["Architecture"])
    build = json.loads((args.artifacts / f"build-{args.arch}.json").read_text())
    if (type(build["exitCode"]) is not int or build["exitCode"] != 0
            or "cleanupError" in build or build["arch"] != args.arch
            or build["image"] != args.image
            or any(build[k] != result[k] for k in ["gitCommit", "dirtyDiffSha256"])):
        raise ValueError("build receipt must match this exact image and source state")
    if sha256_file(Path(build["archive"])) != build["archiveSha256"]:
        raise ValueError("tested archive checksum mismatch")
    verify_import(build, image, args.arch)
    result.update(arch=args.arch, image=args.image, runId=args.run_id, resourcesPrefix=resources.prefix,
                  **{k: build[k] for k in ("manifestDigest", "configDigest", "layerDigests", "archiveSha256")})
    volumes = {role: resources.volume(role) for role in ["config", "data", "sdcard"]}
    container = resources.start(args.image, "desktop", volumes)
    running_container(container)
    result["checks"]["containerRunning"] = True
    wait_http(container)
    result["checks"]["httpReady"] = True
    process, duration = observe_startup(container)
    result.update(process=process, durationSeconds=duration)
    result["checks"]["oscarStable"] = True
    from ci.runtime_checks import exercise
    arguments = dict(uid=1234, gid=2345, expected_python=load_lock()["pythonPackages"],
                     run_id=args.run_id, artifacts=args.artifacts)
    result["checks"].update(exercise(container, phase="initial", **arguments))
    run(["docker", "restart", "--time", "15", container])
    wait_http(container)
    result["checks"].update(exercise(container, phase="restarted", **arguments))
    validate_checks(result["checks"])


def execute_legacy_gui(args, result, resources):
    """Historical negative-base helper; not CI or release acceptance."""
    from ci import gui
    from playwright.sync_api import sync_playwright
    preflight_tools()
    require_native_daemon(args.arch)
    image = json.loads(output(["docker", "image", "inspect", args.image]))[0]
    require_native(args.arch, system="Linux" if image["Os"] == "linux" else image["Os"],
                   machine=image["Architecture"])
    if args.negative_base_probe:
        locked = load_lock()["base"]
        expected = f"{locked['repository']}:{locked['tag']}@{locked['digest']}"
        if args.image != expected:
            raise ValueError("negative probe requires exactly the locked base reference")
        result.update(probe="negative-base", manifestDigest=locked["manifests"][args.arch],
                      configDigest=image["Id"], expectedFailure=False)
    else:
        build_path = args.artifacts / f"build-{args.arch}.json"
        build = json.loads(build_path.read_text())
        if (build["exitCode"] != 0 or build["arch"] != args.arch
                or any(build[k] != result[k] for k in ["gitCommit", "dirtyDiffSha256"])):
            raise ValueError("build receipt must match this exact source state")
        archive = Path(build["archive"])
        if sha256_file(archive) != build["archiveSha256"]:
            raise ValueError("tested archive checksum mismatch")
        verify_import(build, image, args.arch)
        result.update(manifestDigest=build["manifestDigest"], configDigest=build["configDigest"],
                      layerDigests=build["layerDigests"], archiveSha256=build["archiveSha256"])
    result.update(arch=args.arch, image=args.image, runId=args.run_id, resourcesPrefix=resources.prefix)
    volumes = {role: resources.volume(role) for role in ["config", "data", "sdcard"]}
    container = resources.start(args.image, "desktop", volumes)
    frames = []
    result["websockets"] = frames
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(viewport={"width": 1280, "height": 800},
                                      device_scale_factor=1, locale="en-US")
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        try:
            page = open_page(context, wait_http(container), frames)
            result["create"] = gui.exercise(page, "create", PROFILE, args.artifacts / "create")
            if args.negative_base_probe:
                raise AssertionError("negative base unexpectedly passed the OSCAR GUI/profile checkpoint")
            result["checks"]["gui"] = True
            initial = application_process(container)
            check_sd_readonly(container)
            result["checks"]["sdcardReadOnly"] = True
            result["checks"].update(gui.import_dialog(page, args.artifacts / "import"))
            gui.close_application(page, args.artifacts / "close")
            deadline = time.monotonic() + 60
            while True:
                processes = json.loads(output(["docker", "exec", container, "python3", "-c", PROCESS_SCRIPT]))
                if (len(processes) == 1
                        and (processes[0]["pid"], processes[0]["start"]) != (initial["pid"], initial["start"])):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("base watchdog did not restart the cleanly closed application")
                page.wait_for_timeout(500)
            application_process(container)
            result["watchdogGui"] = gui.exercise(page, "verify", PROFILE, args.artifacts / "watchdog")
            result["checks"]["watchdog"] = True
            first = audit(container)
            validate_audit(first, PROFILE)
            result["beforeRecreation"] = first
            old_id = output(["docker", "inspect", "--format", "{{.Id}}", container])
            page.close()
            resources.remove_container(container)
            container = resources.start(args.image, "recreated", volumes)
            new_id = output(["docker", "inspect", "--format", "{{.Id}}", container])
            if old_id == new_id:
                raise ValueError("container was not recreated")
            page = open_page(context, wait_http(container), frames)
            result["verify"] = gui.exercise(page, "verify", PROFILE, args.artifacts / "verify")
            application_process(container)
            second = audit(container)
            validate_audit(second, PROFILE)
            if (first["profiles"] != second["profiles"] or first["language"] != second["language"]
                    or [d["path"] for d in first["data"]] != [d["path"] for d in second["data"]]
                    or [d["path"] for d in first["qtConfig"]] != [d["path"] for d in second["qtConfig"]]):
                raise ValueError("application-created profile/data or Qt language did not survive recreation")
            result["afterRecreation"] = second
            result["checks"].update(containerRecreated=True, dataPersisted=True,
                                    qtConfigPersisted=True, sqliteIntegrity=True, ownership=True)
            page.close()
            resources.remove_container(container)
            # Same owned volumes, but unusable data: must show a problem instead
            # of silently opening a different ephemeral database.
            container = resources.start(args.image, "readonly-data", volumes, readonly_data=True)
            page = open_page(context, wait_http(container), frames)
            result["readonlyData"] = gui.storage_failure(page, args.artifacts / "readonly-data")
            negative = audit(container)
            if negative["outsideDatabases"]:
                raise ValueError("ephemeral fallback database detected")
            run(["docker", "exec", "--user", "1234:2345", container, "python3", "-c",
                 "import os; assert not os.access('/config/Documents/OSCAR20_Data/oscar.db', os.W_OK)"])
            result["checks"]["noEphemeralFallback"] = True
            result["checks"]["mediaFrames"] = sum(f["mediaFrames"] for f in frames)
            validate_checks(result["checks"])
        finally:
            context.tracing.stop(path=str(args.artifacts / "trace.zip"))
            context.close()
            browser.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--negative-base-probe", action="store_true")
    args = parser.parse_args(argv)
    require_native(args.arch)  # Local macOS cannot prove a native daemon.
    prefix = resource_prefix(args.run_id)
    args.artifacts.mkdir(parents=True, exist_ok=True)
    name = f"{'negative-base-' if args.negative_base_probe else ''}runtime-{args.arch}.json"
    target = args.artifacts / name
    if target.exists() or target.is_symlink():
        raise FileExistsError("refusing to overwrite an existing runtime receipt")
    result = receipt(command=[sys.executable, "-m", "ci.runtime", *(argv or sys.argv[1:])])
    if not args.negative_base_probe:
        result["testScope"] = TEST_SCOPE
    resources = Resources(prefix, args.artifacts)
    try:
        execute(args, result, resources)
        result["exitCode"] = 0
    except Exception as error:
        result.update(failure_metadata(error, negative=args.negative_base_probe))
        raise
    finally:
        try:
            resources.cleanup()
        except Exception as error:
            result.update(failure_metadata(error, negative=args.negative_base_probe), cleanupError=str(error))
            raise
        finally:
            write_runtime_receipt(target, result)


def write_runtime_receipt(target, result):
    """Publish complete JSON atomically and exclusively, even across invocations."""
    with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(canonical_json(result) + b"\n")
            file.close()
            os.link(temporary, target)  # EEXIST includes dangling symlinks; never replace.
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
