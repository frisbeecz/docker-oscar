"""Real startup orchestration, with only Docker, HTTP and time controlled."""
import copy
import builtins
import json
import subprocess

import pytest

from ci import runtime, sha256_file


PROCESS = {"pid": 42, "start": "12345", "uid": 1234, "gid": 2345,
           "exe": "/usr/bin/OSCAR20",
           "args": ["OSCAR20", "--legacy", "--datadir", "/config/Documents/OSCAR20_Data"]}


@pytest.fixture
def host(tmp_path, monkeypatch):
    now, calls = [0.0], []
    state = {"processes": lambda t: [copy.deepcopy(PROCESS)], "running": lambda t: True,
             "cleanupFailure": False, "http": [200]}
    archive = tmp_path / "image.oci.tar"
    archive.write_bytes(b"synthetic archive, never launched")
    build = {"exitCode": 0, "arch": "amd64", "gitCommit": "a" * 40,
             "dirtyDiffSha256": "b" * 64, "archive": str(archive),
             "archiveSha256": sha256_file(archive), "manifestDigest": "sha256:" + "c" * 64,
             "configDigest": "sha256:" + "d" * 64, "layerDigests": ["sha256:" + "e" * 64],
             "diffIds": ["sha256:" + "f" * 64], "image": "oscar-under-test:amd64"}
    (tmp_path / "build-amd64.json").write_text(json.dumps(build))
    image = {"Os": "linux", "Architecture": "amd64", "Id": build["configDigest"],
             "RootFS": {"Layers": build["diffIds"]}}
    def docker_output(command):
        calls.append((now[0], command))
        if command[:3] == ["docker", "image", "inspect"]:
            return json.dumps([image])
        if command[:3] == ["docker", "volume", "ls"]:
            return ""
        if command[:3] == ["docker", "volume", "inspect"]:
            return json.dumps([{"Labels": {runtime.OWNER_LABEL: command[-1]}}])
        if command[:3] == ["docker", "container", "inspect"]:
            return json.dumps([{"Config": {"Labels": {runtime.OWNER_LABEL: command[-1]}}}])
        if command[:2] == ["docker", "inspect"]:
            return json.dumps([{"State": {"Running": state["running"](now[0])},
                                "NetworkSettings": {"Ports": {"3000/tcp": [
                                    {"HostIp": "127.0.0.1", "HostPort": "12345"}]}}}])
        if command[:2] == ["docker", "exec"] and command[-1] == runtime.PROCESS_SCRIPT:
            return json.dumps(state["processes"](now[0]))
        raise AssertionError(command)
    def docker_run(command, **kwargs):
        calls.append((now[0], command))
        assert command[:2] in (["docker", "volume"], ["docker", "create"],
                               ["docker", "start"], ["docker", "rm"])
        if command[:2] == ["docker", "rm"] and state["cleanupFailure"]:
            raise RuntimeError("synthetic cleanup failure")
    def logs(command, **kwargs):
        assert command[:2] == ["docker", "logs"]
        return subprocess.CompletedProcess(command, 0, stdout=b"synthetic log", stderr=b"")
    class Response:
        def __enter__(self):
            status = state["http"].pop(0) if len(state["http"]) > 1 else state["http"][0]
            if isinstance(status, Exception):
                raise status
            self.status = status
            return self
        def __exit__(self, *args):
            return False
    def forbidden(*args, **kwargs):
        raise AssertionError("GUI, audit or functional helper called by startup smoke")
    monkeypatch.setattr(runtime, "output", docker_output)
    monkeypatch.setattr(runtime, "run", docker_run)
    monkeypatch.setattr(runtime.subprocess, "run", logs)
    monkeypatch.setattr(runtime, "require_native", lambda *a, **kw: "amd64")
    monkeypatch.setattr(runtime, "require_native_daemon", lambda arch: None)
    monkeypatch.setattr(runtime, "receipt", lambda **kw: {
        "gitCommit": "a" * 40, "dirtyDiffSha256": "b" * 64, "checks": {}})
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *a, **kw: Response())
    for name in ("preflight_tools", "open_page", "audit", "check_sd_readonly"):
        monkeypatch.setattr(runtime, name, forbidden)
    argv = ["--image", "oscar-under-test:amd64", "--arch", "amd64",
            "--run-id", "smoke-test", "--artifacts", str(tmp_path)]
    return state, now, calls, argv, tmp_path, build, image


def test_normal_cli_waits_for_same_process_without_functional_helpers(host, monkeypatch):
    state, now, calls, argv, folder, build, _ = host
    state["processes"] = lambda t: [] if t < 4 else [copy.deepcopy(PROCESS)]
    state["http"] = [ConnectionResetError("startup reset"), 503, 200]
    original_import = builtins.__import__
    def no_gui_import(name, globals=None, locals=None, fromlist=(), level=0):
        assert not name.startswith(("playwright", "ci.gui", "pytesseract"))
        assert not (name == "ci" and "gui" in (fromlist or ()))
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", no_gui_import)
    runtime.main(argv)
    result = json.loads((folder / "runtime-amd64.json").read_text())
    assert result["exitCode"] == 0
    assert result["testScope"] == "startup-smoke-v1"
    assert result["checks"] == {"containerRunning": True, "httpReady": True, "oscarStable": True}
    assert result["process"] == PROCESS
    assert result["durationSeconds"] == 10
    assert now[0] == 14
    samples = [t for t, cmd in calls if cmd[:2] == ["docker", "exec"]]
    assert samples == list(range(2, 15))
    assert all(cmd[2:4] == ["--user", "1234:2345"]
               for _, cmd in calls if cmd[:2] == ["docker", "exec"])
    assert len([cmd for _, cmd in calls if cmd[:2] == ["docker", "create"]]) == 1
    assert len([cmd for _, cmd in calls if cmd[:2] == ["docker", "rm"]]) == 1
    assert result["archiveSha256"] == build["archiveSha256"]
    assert result["layerDigests"] == build["layerDigests"]


@pytest.mark.parametrize("failure", ["absent", "duplicate", "duplicate-late", "uid-late", "uid", "gid", "exe", "args",
                                     "pid-change", "start-change", "exit", "container-exit",
                                     "http-container-exit", "cleanup"])
def test_smoke_fails_closed_and_retains_receipt_with_owned_cleanup(host, failure):
    state, now, calls, argv, folder, _, _ = host
    if failure == "absent":
        state["processes"] = lambda t: []
    elif failure == "duplicate":
        state["processes"] = lambda t: [PROCESS, PROCESS]
    elif failure == "duplicate-late":
        state["processes"] = lambda t: [PROCESS] if t < 5 else [PROCESS, PROCESS]
    elif failure == "uid-late":
        state["processes"] = lambda t: [{**PROCESS, "uid": 1234 if t < 5 else 0}]
    elif failure in {"uid", "gid", "exe", "args"}:
        bad = {**PROCESS, failure: {"uid": 0, "gid": 0, "exe": "/tmp/OSCAR20", "args": []}[failure]}
        state["processes"] = lambda t: [bad]
    elif failure in {"pid-change", "start-change"}:
        field = failure.split("-")[0]
        state["processes"] = lambda t: [{**PROCESS, field: PROCESS[field] if t < 5 else
                                       (43 if field == "pid" else "999")}]
    elif failure == "exit":
        state["processes"] = lambda t: [PROCESS] if t < 5 else []
    elif failure in {"container-exit", "http-container-exit"}:
        state["running"] = lambda t: t < (5 if failure == "container-exit" else 1)
        if failure == "http-container-exit":
            state["http"] = [503]
    else:
        state["cleanupFailure"] = True
    with pytest.raises((ValueError, TimeoutError, RuntimeError)):
        runtime.main(argv)
    result = json.loads((folder / "runtime-amd64.json").read_text())
    assert result["exitCode"] == 1
    assert result["testScope"] == "startup-smoke-v1"
    assert bool(result.get("cleanupError")) is (failure == "cleanup")
    assert any(cmd[:2] == ["docker", "rm"] for _, cmd in calls)
    assert now[0] == (90 if failure == "absent" else 10 if failure == "cleanup" else
                      5 if failure in {"exit", "pid-change", "start-change", "container-exit",
                                       "duplicate-late", "uid-late"} else
                      1 if failure == "http-container-exit" else 0)


@pytest.mark.parametrize("failure", ["source", "archive", "config", "layers", "image"])
def test_wrong_build_identity_fails_before_resource_creation(host, failure):
    _, _, calls, argv, folder, build, image = host
    if failure == "source":
        build["gitCommit"] = "0" * 40
    elif failure == "archive":
        build["archiveSha256"] = "0" * 64
    elif failure == "config":
        image["Id"] = "sha256:" + "0" * 64
    elif failure == "layers":
        image["RootFS"]["Layers"] = []
    else:
        build["image"] = "unrelated:latest"
    (folder / "build-amd64.json").write_text(json.dumps(build))
    with pytest.raises(ValueError):
        runtime.main(argv)
    assert not any(cmd[:2] in (["docker", "create"], ["docker", "volume"]) for _, cmd in calls)


def test_existing_receipt_is_not_overwritten_or_resources_touched(host):
    _, _, calls, argv, folder, _, _ = host
    target = folder / "runtime-amd64.json"
    target.write_text("previous evidence")
    with pytest.raises(FileExistsError):
        runtime.main(argv)
    assert target.read_text() == "previous evidence"
    assert calls == []


def test_receipt_created_by_concurrent_invocation_is_never_replaced(host):
    state, _, _, argv, folder, _, _ = host
    target = folder / "runtime-amd64.json"
    def processes(t):
        if t == 5:
            target.write_text("other invocation evidence")
        return [copy.deepcopy(PROCESS)]
    state["processes"] = processes
    with pytest.raises(FileExistsError):
        runtime.main(argv)
    assert target.read_text() == "other invocation evidence"


def test_dangling_receipt_symlink_is_not_replaced(host):
    _, _, calls, argv, folder, _, _ = host
    target = folder / "runtime-amd64.json"
    target.symlink_to(folder / "missing")
    with pytest.raises(FileExistsError):
        runtime.main(argv)
    assert target.is_symlink()
    assert calls == []


def test_late_initial_process_gets_full_observation_without_reset(host):
    state, now, _, argv, folder, _, _ = host
    state["processes"] = lambda t: [] if t < 89 else [copy.deepcopy(PROCESS)]
    runtime.main(argv)
    result = json.loads((folder / "runtime-amd64.json").read_text())
    assert now[0] == 99
    assert result["durationSeconds"] == 10


def test_initial_process_observed_after_startup_deadline_is_rejected(host):
    state, now, _, argv, folder, _, _ = host
    def slow_inventory(t):
        if t == 0:
            now[0] = 91
        return [copy.deepcopy(PROCESS)]
    state["processes"] = slow_inventory
    with pytest.raises(TimeoutError):
        runtime.main(argv)
    result = json.loads((folder / "runtime-amd64.json").read_text())
    assert result["exitCode"] == 1


@pytest.mark.parametrize("kind", ["container", "volume"])
def test_cleanup_refuses_foreign_owner_before_logs_or_removal(tmp_path, monkeypatch, kind):
    resource = runtime.Resources("oscar-ci-test", tmp_path)
    name = "oscar-ci-test-owned"
    if kind == "container":
        resource.containers.append(name)
        inventory = {"Config": {"Labels": {runtime.OWNER_LABEL: "foreign"}}}
    else:
        resource.volumes.append(name)
        inventory = {"Labels": {runtime.OWNER_LABEL: "foreign"}}
    monkeypatch.setattr(runtime, "output", lambda cmd: json.dumps([inventory]))
    def forbidden(*args, **kwargs):
        raise AssertionError("foreign resource touched")
    monkeypatch.setattr(runtime, "run", forbidden)
    monkeypatch.setattr(runtime.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="unowned"):
        resource.cleanup()
