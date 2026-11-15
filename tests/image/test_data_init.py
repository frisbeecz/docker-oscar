"""Exercise real directories without root, mounts, medical data or chown privilege."""
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from conftest import ROOT


HOOK = ROOT / "root/etc/s6-overlay/s6-rc.d/init-oscar-data/run"


@pytest.fixture
def hook():
    assert HOOK.is_file(), "ordered data init hook missing"
    # Compile the real hook without importing bytecode into Docker's root/ context.
    module = ModuleType("oscar_data_init")
    exec(compile(HOOK.read_bytes(), str(HOOK), "exec"), module.__dict__)
    return module


@pytest.fixture
def filesystem(tmp_path, hook, monkeypatch):
    config = tmp_path / "config"
    data = config / "Documents/OSCAR20_Data"
    data.mkdir(parents=True)
    changes = []
    original_stat = os.fstat
    root_inode = data.stat().st_ino

    def stat(fd):
        value = original_stat(fd)
        # Model Docker's fresh volume root: root:root, without privileged chown.
        if value.st_ino == root_inode:
            fields = list(value)
            fields[4:6] = [0, 0]
            return os.stat_result(fields)
        return value

    monkeypatch.setattr(hook.os, "fstat", stat)
    monkeypatch.setattr(hook.os, "fchown", lambda fd, uid, gid: changes.append(
        (original_stat(fd).st_ino, uid, gid)))
    return config, data, changes


def test_empty_root_owned_data_only_is_initialized(hook, filesystem):
    config, data, changes = filesystem
    before = data.stat().st_mode
    hook.initialize(config, 1234, 2345)
    assert changes == [(data.stat().st_ino, 1234, 2345)]
    assert data.stat().st_mode == before
    assert list(data.iterdir()) == []


@pytest.mark.parametrize("entry", ["oscar.db", ".hidden", "lost+found"])
def test_nonempty_data_is_completely_untouched(hook, filesystem, entry):
    config, data, changes = filesystem
    child = data / entry
    if entry == "lost+found":
        child.mkdir()
    else:
        child.write_bytes(b"synthetic existing data")
    before = (data.stat(), child.stat())
    hook.initialize(config, 1234, 2345)
    assert changes == []
    assert (data.stat(), child.stat()) == before
    if entry == "lost+found":
        assert child.is_dir() and list(child.iterdir()) == []
    else:
        assert child.read_bytes() == b"synthetic existing data"


@pytest.mark.parametrize("owner", [(4321, 5432), (0, 5432), (1234, 2345)])
def test_empty_data_with_existing_custom_owner_is_not_reassigned(hook, filesystem, monkeypatch, owner):
    config, data, changes = filesystem
    original_stat = os.fstat
    def custom_owner(fd):
        fields = list(original_stat(fd))
        fields[4:6] = owner
        return os.stat_result(fields)
    monkeypatch.setattr(hook.os, "fstat", custom_owner)
    hook.initialize(config, 1234, 2345)
    assert changes == []


def test_readonly_empty_mount_is_not_mutated(hook, filesystem, monkeypatch):
    config, data, changes = filesystem
    monkeypatch.setattr(hook.os, "fstatvfs", lambda _: SimpleNamespace(f_flag=os.ST_RDONLY))
    hook.initialize(config, 1234, 2345)
    assert changes == []


@pytest.mark.parametrize("component", ["config", "Documents", "OSCAR20_Data"])
def test_symlink_at_any_managed_component_is_rejected(hook, tmp_path, component, monkeypatch):
    config = tmp_path / "config"
    external = tmp_path / "outside"
    external.mkdir()
    target = {"config": config, "Documents": config / "Documents",
              "OSCAR20_Data": config / "Documents/OSCAR20_Data"}[component]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(external, target_is_directory=True)
    calls = []
    monkeypatch.setattr(hook.os, "fchown", lambda *args: calls.append(args))
    with pytest.raises(OSError):
        hook.initialize(config, 1234, 2345)
    assert calls == []
    assert list(external.iterdir()) == []


def test_missing_managed_directories_are_created_without_world_write(hook, tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    changes = []
    monkeypatch.setattr(hook.os, "fchown", lambda fd, uid, gid: changes.append((uid, gid)))
    hook.initialize(config, 1234, 2345)
    assert changes == [(1234, 2345), (1234, 2345)]
    assert (config / "Documents/OSCAR20_Data").is_dir()
    assert (config / "Documents").stat().st_mode & 0o002 == 0


def test_ownership_failure_is_not_swallowed(hook, filesystem, monkeypatch):
    config, data, changes = filesystem
    def fail(*args):
        raise PermissionError("synthetic chown failure")
    monkeypatch.setattr(hook.os, "fchown", fail)
    with pytest.raises(PermissionError, match="synthetic"):
        hook.initialize(config, 1234, 2345)


def test_init_is_ordered_after_uid_setup_and_before_services():
    root = ROOT / "root/etc/s6-overlay/s6-rc.d"
    assert (root / "init-oscar-data/dependencies.d/init-custom-files").is_file()
    assert (root / "init-services/dependencies.d/init-oscar-data").is_file()
    assert (root / "init-oscar-data/type").read_text().strip() == "oneshot"
    assert (root / "init-oscar-data/up").read_text().strip() == "/" + str(HOOK.relative_to(ROOT / "root"))
    assert HOOK.stat().st_mode & 0o111
