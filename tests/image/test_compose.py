"""Exercise the shipped local deployment through the real Compose parser."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def render_compose(tmp_path_factory):
    # Config validation does not contact the daemon or create any resources.
    command = ([shutil.which("docker-compose")] if shutil.which("docker-compose")
               else ["docker", "compose"])
    empty_env = tmp_path_factory.mktemp("compose") / "empty.env"
    empty_env.write_text("")

    def render(**overrides):
        assert (ROOT / "compose.yaml").is_file(), "missing Compose Quick Start"
        env = {key: value for key, value in os.environ.items()
               if key not in ("PUID", "PGID", "TZ") and not key.startswith("COMPOSE_")}
        env.update(overrides)
        result = subprocess.run(
            [*command, "--env-file", str(empty_env), "--project-name", "oscar-compose-test",
             "--file", str(ROOT / "compose.yaml"), "config", "--format", "json"],
            cwd=ROOT, env=env, check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    return render


def test_quick_start_exposes_only_loopback_without_host_access(render_compose):
    model = render_compose()
    assert set(model["services"]) == {"oscar"}
    service = model["services"]["oscar"]
    assert service["image"] == (
        "ghcr.io/frisbeecz/docker-oscar:2.1.1-r8@"
        "sha256:bf0524b3ba21744809c2569a8a770f270c77463d92bbdc96774ba95a87cbfa1a"
    )
    assert len(service["ports"]) == 1
    port = service["ports"][0]
    assert (port["host_ip"], port["published"], port["target"], port["protocol"]) == (
        "127.0.0.1", "3000", 3000, "tcp",
    )
    assert service["shm_size"] == "536870912" or service["shm_size"] == 536870912
    assert "no-new-privileges" in service["security_opt"]
    assert "NET_RAW" in service["cap_drop"]
    assert not service.get("cap_add")
    assert not service.get("privileged")
    assert not service.get("devices")
    assert "network_mode" not in service
    assert "pid" not in service
    assert "build" not in service
    assert "platform" not in service  # The published index selects AMD64/ARM64.
    assert "user" not in service  # Base init needs root; desktop uses PUID/PGID.


def test_quick_start_keeps_profile_and_readonly_sd_on_separate_named_volumes(render_compose):
    model = render_compose()
    mounts = model["services"]["oscar"]["volumes"]
    assert len(mounts) == 3
    expected = {
        "/config": ("config", False),
        "/config/Documents/OSCAR20_Data": ("data", False),
        "/config/SDCARD": ("sdcard", True),
    }
    assert {mount["target"] for mount in mounts} == set(expected)
    for mount in mounts:
        source, readonly = expected[mount["target"]]
        assert mount["type"] == "volume"
        assert mount["source"] == source
        assert mount.get("read_only", False) is readonly
        assert mount["volume"]["nocopy"] is True
    assert set(model["volumes"]) == {"config", "data", "sdcard"}
    for volume in model["volumes"].values():
        assert not volume.get("external")
        assert not volume.get("driver_opts")


def test_quick_start_retains_hardening_upload_root_and_window_recovery(render_compose):
    service = render_compose()["services"]["oscar"]
    assert service["restart"] == "unless-stopped"
    env = service["environment"]
    expected = {
        "PUID": "1000", "PGID": "1000", "TZ": "Etc/UTC",
        "PIXELFLUX_WAYLAND": "true", "HARDEN_DESKTOP": "true", "START_DOCKER": "false",
        "RESTART_APP": "true", "DISABLE_WINDOW_BUTTONS": "true",
        "HARDEN_KEYBINDS": "false", "DISABLE_MOUSE_BUTTONS": "false",
        "SELKIES_FILE_TRANSFERS": "upload,download",
        "SELKIES_UI_SIDEBAR_SHOW_FILES": "true", "FILE_MANAGER_PATH": "/config/Uploads",
        "SELKIES_COMMAND_ENABLED": "false", "SELKIES_UI_SIDEBAR_SHOW_APPS": "false",
    }
    for key, value in expected.items():
        assert env[key] == value


def test_local_ownership_and_timezone_overrides_do_not_change_storage(render_compose):
    model = render_compose(PUID="1234", PGID="2345", TZ="Europe/Prague")
    env = model["services"]["oscar"]["environment"]
    assert (env["PUID"], env["PGID"], env["TZ"]) == ("1234", "2345", "Europe/Prague")
    assert env["FILE_MANAGER_PATH"] == "/config/Uploads"
    assert {mount["source"] for mount in model["services"]["oscar"]["volumes"]} == {
        "config", "data", "sdcard",
    }
