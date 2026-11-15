import importlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import subprocess
import sys

import pytest

from conftest import (
    ROOT, captured_launcher_args, no_legacy_copy_import_or_conversion_in_startup,
    valid_immutable_digests_and_checksums,
)


def module(name):
    assert (ROOT / (name.replace(".", "/") + ".py")).is_file(), f"{name} missing"
    return importlib.import_module(name)


def test_locked_inputs(lock):
    assert lock["oscar"]["version"] == "2.1.1"
    assert lock["oscar"]["commit"] == "4f14624616d62c6986788417bc5c519c807a7ade"
    assert set(lock["platforms"]) == {"linux/amd64", "linux/arm64"}
    assert lock["base"]["tag"] == "debiantrixie"
    assert valid_immutable_digests_and_checksums(lock)


def test_launcher_contract(tmp_path):
    assert captured_launcher_args(tmp_path) == [
        "--legacy", "--datadir", "/config/Documents/OSCAR20_Data",
    ]
    env = (tmp_path / "env").read_text().splitlines()
    assert "HOME=/config" in env
    assert "XDG_CONFIG_HOME=/config/.config" in env
    assert no_legacy_copy_import_or_conversion_in_startup()


def test_default_hardening(lock):
    path = ROOT / "Dockerfile"
    assert path.is_file(), "Dockerfile missing"
    text = path.read_text()
    for setting in ["PIXELFLUX_WAYLAND=true", "RESTART_APP=true", "HARDEN_DESKTOP=true"]:
        assert setting in text
    assert lock["base"]["digest"] in text
    assert "libqt6sql6-sqlite" in text
    assert "qt6-wayland" in text
    assert "qt6-translations-l10n" in text
    assert "ENTRYPOINT" not in text
    assert "VNC" not in text
    autostart = ROOT / "root/defaults/autostart_wayland"
    assert autostart.is_file()
    assert "/usr/local/bin/oscar-start" in autostart.read_text()


def test_license_and_notices():
    path = ROOT / "LICENSE"
    assert path.is_file(), "full license missing"
    text = path.read_text()
    assert "Apache License" in text
    assert "Version 2.0, January 2004" in text
    assert "END OF TERMS AND CONDITIONS" in text
    assert len(text) > 10000
    notice = ROOT / "NOTICE.md"
    assert notice.is_file()
    for attribution in ["OSCAR Team", "SleepyHead", "Selkies", "Qt", "Apache-2.0"]:
        assert attribution in notice.read_text()


@pytest.mark.parametrize("system,machine,arch", [
    ("Darwin", "arm64", "arm64"), ("Linux", "x86_64", "arm64"),
    ("Linux", "aarch64", "amd64"), ("Linux", "unknown", "amd64"),
])
def test_build_rejects_foreign_native_arch(system, machine, arch):
    build = module("ci.build_image")
    with pytest.raises(ValueError, match="native"):
        build.require_native(arch, system=system, machine=machine)


@pytest.mark.parametrize("machine,arch", [("x86_64", "amd64"), ("aarch64", "arm64")])
def test_build_accepts_native_arch(machine, arch):
    assert module("ci.build_image").require_native(arch, system="Linux", machine=machine) == arch


def test_build_cli_rejects_locally_before_daemon(tmp_path):
    module("ci.build_image")
    arch = "arm64" if platform.machine() in {"x86_64", "amd64"} else "amd64"
    env = {**os.environ, "PATH": str(tmp_path)}
    result = subprocess.run([sys.executable, "-m", "ci.build_image", "--arch", arch,
                             "--out-dir", str(tmp_path / "output")],
                            env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert "native" in result.stderr
    assert not (tmp_path / "output").exists()


def test_source_bundle_matches_lock(tmp_path):
    """Wrong upstream bytes must fail closed, not be archived with a success manifest."""
    source = module("ci.source_bundle")
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not the upstream archive")
    with pytest.raises(ValueError, match="checksum"):
        source.build_bundle(tmp_path / "out", project=ROOT, source_archive=bad)
    assert not (tmp_path / "out/origin.json").exists()


def test_receipt_tracks_nonignored_untracked(tmp_path):
    shared = module("ci.__init__")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("private/\n")
    (tmp_path / "private").mkdir()
    (tmp_path / "private/secret").write_text("not included")
    a = shared.state_identity(tmp_path)
    (tmp_path / "new.py").write_text("first")
    b = shared.state_identity(tmp_path)
    (tmp_path / "new.py").write_text("second")
    c = shared.state_identity(tmp_path)
    assert a["gitCommit"] is None
    assert len({a["dirtyDiffSha256"], b["dirtyDiffSha256"], c["dirtyDiffSha256"]}) == 3
    (tmp_path / "private/secret").write_text("changed")
    assert shared.state_identity(tmp_path) == c


def test_receipt_detects_staged_and_deleted_paths(tmp_path):
    shared = module("ci.__init__")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a").write_text("one")
    subprocess.run(["git", "add", "a"], cwd=tmp_path, check=True)
    staged = shared.state_identity(tmp_path)
    (tmp_path / "a").unlink()
    deleted = shared.state_identity(tmp_path)
    assert staged != deleted


def test_runtime_refuses_unsafe_resource_names():
    runtime = module("ci.runtime")
    for value in ["", "../foreign", "foreign;rm", "UPPER", "a" * 70]:
        with pytest.raises(ValueError):
            runtime.resource_prefix(value)
    assert runtime.resource_prefix("image01-arm64").startswith("oscar-ci-image01-arm64-")


def test_gui_rejects_unknown_phase(tmp_path):
    gui = module("ci.gui")
    with pytest.raises(ValueError, match="phase"):
        gui.exercise(None, "fabricate", "ci-synthetic", tmp_path)


def test_runtime_rejects_fake_stream():
    runtime = module("ci.runtime")
    assert not runtime.is_media_frame('{"ping":1}')
    assert not runtime.is_media_frame(b"hello")
    # Selkies2.2.1 websockets_mode.py: typed 0x04 video / 0x03 JPEG,
    # not raw Annex-B on an untyped socket.
    assert runtime.is_media_frame(b"\x04" + b"x" * 4096)


def test_required_tool_pins():
    path = ROOT / "ci/tools.lock.json"
    assert path.is_file(), "shared tools lock missing"
    tools = json.loads(path.read_text())
    assert tools["python"]["version"] == "3.14"
    assert tools["playwright"]["version"] == "1.64.1"
    assert set(tools["helm"]) == {"3.19.0", "4.3.2"}
    assert tools["kind"]["version"] == "0.33.0"
    for group in [*tools["helm"].values(), tools["kind"], tools["kubeconform"]]:
        for artifact in group["artifacts"].values():
            assert len(artifact["sha256"]) == 64
            assert artifact["url"].startswith("https://")
    assert "@sha256:" in tools["kind"]["nodeImage"]
    assert len(tools["schemas"]["kubernetes"]["commit"]) == 40
    assert len(tools["schemas"]["gateway"]["sha256"]) == 64
