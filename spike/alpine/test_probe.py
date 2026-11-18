"""Local contracts for the disposable experiment, not production acceptance."""
import ast
import errno
import json
import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_cannot_publish_or_receive_secrets():
    workflow = yaml.safe_load((ROOT / ".github/workflows/alpine-spike.yaml").read_text())
    events = workflow.get("on", workflow.get(True))
    assert events == {"push": {"branches": ["spike/oscar-alpine"]}}
    assert workflow["permissions"] == {"contents": "read"}
    assert "secrets." not in str(workflow)
    assert not any(word in str(workflow) for word in
                   ("packages: write", "docker login", "ci.release", "--push"))
    job = workflow["jobs"]["native"]
    assert {(v["arch"], v["runner"]) for v in job["strategy"]["matrix"]["include"]} == {
        ("amd64", "ubuntu-24.04"), ("arm64", "ubuntu-24.04-arm")}
    assert not job.get("continue-on-error")


def test_probe_keeps_exact_source_and_scanner_identity():
    inputs = json.loads((ROOT / "spike/alpine/inputs.json").read_text())
    original = json.loads((ROOT / "versions.lock.json").read_text())
    assert inputs["source"] == {k: original["oscar"][k] for k in ("url", "sha256", "commit")}
    assert inputs["base"].endswith(
        "@sha256:f2820b8df78eb020785850492c2b6547de2c762fcfcd644b11d4f7e211f5a987")
    assert set(inputs["trivy"]["sha256"]) == {"amd64", "arm64"}
    assert inputs["trivy"]["version"] == "0.76.2"


def test_dockerfile_builds_source_and_does_not_reuse_debian_binary():
    dockerfile = (ROOT / "spike/alpine/Dockerfile").read_text()
    inputs = json.loads((ROOT / "spike/alpine/inputs.json").read_text())
    assert dockerfile.count("FROM " + inputs["base"]) == 2
    assert inputs["source"]["url"] in dockerfile
    assert inputs["source"]["sha256"] in dockerfile
    assert ".deb" not in dockerfile and "apt-get" not in dockerfile
    assert "AS build" in dockerfile
    assert "sha256sum -c -" in dockerfile
    assert "qmake6" in dockerfile
    assert "COPY --from=build" in dockerfile
    assert "START_DOCKER=false" in dockerfile


def test_candidate_scan_precedes_runtime_so_compatibility_failure_keeps_comparison():
    workflow = yaml.safe_load((ROOT / ".github/workflows/alpine-spike.yaml").read_text())
    steps = workflow["jobs"]["native"]["steps"]
    build = next(i for i, s in enumerate(steps) if "docker build " in s.get("run", ""))
    scan = next(i for i, s in enumerate(steps)
                if 'scan.py "$ARCH" candidate' in s.get("run", ""))
    runtime = next(i for i, s in enumerate(steps) if "check-runtime.py" in s.get("run", ""))
    assert build < scan < runtime
    assert not steps[scan].get("if") and not steps[scan].get("continue-on-error")


def runtime_mount_parser():
    module = ast.parse((ROOT / "spike/alpine/check-runtime.py").read_text())
    check = next(ast.literal_eval(n.value) for n in module.body
                 if isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id == "CHECK" for t in n.targets))
    functions = [n for n in ast.parse(check).body
                 if isinstance(n, ast.FunctionDef) and n.name == "mount_options"]
    assert functions, "runtime probe needs bind-mount-aware detection"
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<mount-parser>", "exec"), namespace)
    return namespace["mount_options"]


@pytest.mark.parametrize("path,flags", [
    ("/config", {"rw", "relatime"}),
    ("/config/Documents/OSCAR20_Data", {"rw", "relatime"}),
    ("/config/SDCARD", {"ro", "relatime"}),
    ("/config/Card copy", {"rw", "relatime"}),
])
def test_named_volumes_on_same_device_are_detected_without_stat_heuristics(path, flags):
    mountinfo = (
        "100 90 8:1 /docker/config /config rw,relatime - ext4 /dev/sda1 rw\n"
        "101 100 8:1 /docker/data /config/Documents/OSCAR20_Data rw,relatime - ext4 /dev/sda1 rw\n"
        "102 100 8:1 /docker/sdcard /config/SDCARD ro,relatime - ext4 /dev/sda1 rw\n"
        "103 100 8:1 /docker/card /config/Card\\040copy rw,relatime - ext4 /dev/sda1 rw\n"
    )
    assert runtime_mount_parser()(path, mountinfo) == flags


def test_mount_detection_does_not_accept_unmounted_child_directory():
    assert runtime_mount_parser()("/config/Documents/OSCAR20_Data",
                                  "100 90 8:1 /docker/config /config rw - ext4 /dev/sda1 rw\n") is None


@pytest.mark.parametrize("state", ["present", "missing", "denied"])
def test_storage_diagnostics_survive_missing_or_inaccessible_data(tmp_path, capsys, state):
    module = ast.parse((ROOT / "spike/alpine/check-runtime.py").read_text())
    check = next(ast.literal_eval(n.value) for n in module.body
                 if isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id == "CHECK" for t in n.targets))
    body = ast.parse(check).body
    start = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "mounts" for t in n.targets))
    end = next(i for i in range(start + 1, len(body)) if isinstance(body[i], ast.Assert))
    data = tmp_path if state == "present" else tmp_path / "missing"
    if state == "denied":
        class DeniedPath(type(tmp_path)):
            def stat(self, *args, **kwargs):
                raise PermissionError(errno.EACCES, "synthetic stat denial")
        data = DeniedPath(tmp_path)
    mounts = {"/config": {"rw"}, str(data): {"rw"}, "/config/SDCARD": {"ro"}}
    # Execute the actual diagnostics statements, stopping before acceptance assertions.
    exec(compile(ast.Module(body=body[start + 1:end], type_ignores=[]),
                 "<actual-storage-diagnostics>", "exec"),
         {"data": data, "mounts": mounts, "os": os, "json": json})
    result = json.loads(capsys.readouterr().out)["storageDiagnostics"]
    assert (result["uid"], result["gid"]) == (os.getuid(), os.getgid())
    assert result["mounts"] == {p: sorted(flags) for p, flags in mounts.items()}
    if state == "present":
        assert result["dataUid"] == tmp_path.stat().st_uid
        assert "dataStatError" not in result
    else:
        assert result["dataStatError"] == (
            "FileNotFoundError" if state == "missing" else "PermissionError")
        assert result["dataStatErrno"] == (errno.ENOENT if state == "missing" else errno.EACCES)


def test_security_refresh_has_exact_hashed_wheels_and_no_unbounded_upgrade():
    requirements = ROOT / "spike/alpine/python-requirements.txt"
    assert requirements.is_file(), "missing reviewed Python security refresh"
    text = requirements.read_text()
    expected = json.loads((ROOT / "spike/alpine/inputs.json").read_text())["pythonPackages"]
    for package, version in expected.items():
        line = next(line for line in text.splitlines() if line.startswith(package + "=="))
        assert line.startswith(package + "==" + version + " --hash=sha256:")
    dockerfile = (ROOT / "spike/alpine/Dockerfile").read_text()
    assert "/lsiopy/bin/python3 -m pip install" in dockerfile
    assert "--require-hashes" in dockerfile and "--only-binary=:all:" in dockerfile
    assert "/lsiopy/bin/python3 -m pip check" in dockerfile
