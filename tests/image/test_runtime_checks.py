"""Exercise child-script checks directly and the real Docker-exec transport boundary."""
import ast
import importlib
import json
import os
from pathlib import Path
import subprocess

import pytest


def module():
    return importlib.import_module("ci.runtime_checks")


def embedded(*names):
    tree = ast.parse(module().CHECK)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    namespace = {"json": json, "os": os, "Path": Path}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<actual-runtime-checks>", "exec"), namespace)
    return namespace


def test_mountinfo_recognizes_same_filesystem_bind_mounts():
    parse = embedded("mount_options")["mount_options"]
    text = ("10 1 0:42 / /config rw - ext4 /dev/test rw\n"
            "11 10 0:42 /data /config/Documents/OSCAR20_Data rw,nosuid - ext4 /dev/test rw\n"
            "12 10 0:42 /sd /config/SDCARD ro - ext4 /dev/test rw\n")
    assert parse("/config/Documents/OSCAR20_Data", text) == {"rw", "nosuid"}
    assert parse("/config/SDCARD", text) == {"ro"}
    assert parse("/config/missing", text) is None


@pytest.mark.parametrize("case", ["present", "missing", "denied"])
def test_storage_diagnostics_are_printed_even_if_stat_fails(tmp_path, monkeypatch, capsys, case):
    data = tmp_path / "data"
    if case != "missing":
        data.mkdir()
    if case == "denied":
        original = Path.stat
        def stat(path, *args, **kwargs):
            if path == data:
                raise PermissionError(13, "synthetic inaccessible directory")
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, "stat", stat)
    check = embedded("mount_options", "storage_diagnostics")
    check["storage_diagnostics"](data, "")
    result = json.loads(capsys.readouterr().out)["storageDiagnostics"]
    assert result["uid"] == os.getuid() and result["gid"] == os.getgid()
    assert "mounts" in result and "writable" in result
    if case == "present":
        assert result["dataUid"] == os.getuid() and result["dataGid"] == os.getgid()
    else:
        assert result["dataStatErrno"] == (2 if case == "missing" else 13)


@pytest.mark.parametrize("wrong", ["marker", "upload", None])
def test_restart_requires_preexisting_exact_synthetic_bytes(tmp_path, wrong):
    marker, uploaded = tmp_path / "marker", tmp_path / "uploaded"
    for path in (marker, uploaded):
        path.write_bytes(b"synthetic")
    if wrong:
        (marker if wrong == "marker" else uploaded).write_bytes(b"changed")
    check = embedded("check_retained")["check_retained"]
    if wrong:
        with pytest.raises(AssertionError):
            check(marker, uploaded, b"synthetic")
    else:
        check(marker, uploaded, b"synthetic")


@pytest.mark.parametrize("uid,gid", [(0, 2345), (1234, 0), (1000, 1000), (1234, 2345)])
def test_unprivileged_identity_is_exact(uid, gid):
    check = embedded("check_identity")["check_identity"]
    if (uid, gid) == (1234, 2345):
        check(uid, gid, 1234, 2345)
    else:
        with pytest.raises(AssertionError):
            check(uid, gid, 1234, 2345)


@pytest.mark.parametrize("failure", [None, "transport", "receipt", "foreign"])
def test_exec_retains_diagnostics_and_requires_owned_container(tmp_path, monkeypatch, failure):
    checks = module()
    container = "oscar-ci-test-1234567890-desktop"
    monkeypatch.setattr(checks, "output", lambda command: json.dumps([{
        "Config": {"Labels": {"io.docker-oscar.ci-owner": "foreign" if failure == "foreign" else container}}}]))
    calls = []
    def invoke(command, **kwargs):
        calls.append(command)
        assert command[:4] == ["docker", "exec", "--user", "1234:2345"]
        assert command[4:8] == ["-i", container, "/lsiopy/bin/python3", "-"]
        assert command[8:12] == ["initial", "test", "1234", "2345"]
        assert json.loads(command[12]) == {"msgpack": "1.2.4"}
        assert kwargs["input"] == checks.CHECK
        result = {"unprivileged": True, "uploadRoundTrip": True, "watchdogRestart": True,
                  "sdcardReadOnly": False if failure == "receipt" else True}
        return subprocess.CompletedProcess(command, 1 if failure == "transport" else 0,
                                           stdout='{"storageDiagnostics":{"uid":1234}}\n' + json.dumps(result) + "\n")
    monkeypatch.setattr(checks.subprocess, "run", invoke)
    invoke_args = dict(phase="initial", uid=1234, gid=2345, expected_python={"msgpack": "1.2.4"},
                       run_id="test", artifacts=tmp_path)
    if failure:
        with pytest.raises((ValueError, subprocess.CalledProcessError)):
            checks.exercise(container, **invoke_args)
    else:
        result = checks.exercise(container, **invoke_args)
        assert result["uploadRoundTrip"] is True
    if failure == "foreign":
        assert calls == []
    else:
        assert '"storageDiagnostics"' in (tmp_path / "runtime-initial.log").read_text()
