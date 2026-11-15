"""Contract fixtures; no desktop, daemon or private data."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def lock():
    path = ROOT / "versions.lock.json"
    assert path.is_file(), "immutable input lock is missing"
    return json.loads(path.read_text())


def captured_launcher_args(tmp_path):
    launcher = ROOT / "root/usr/local/bin/oscar-start"
    assert launcher.is_file(), "launcher missing"
    fake = tmp_path / "OSCAR20"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$CAPTURE\"\nenv > \"$ENV_CAPTURE\"\n")
    fake.chmod(0o755)
    capture = tmp_path / "argv"
    subprocess.run(["sh", str(launcher)], check=True, env={
        **os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CAPTURE": str(capture), "ENV_CAPTURE": str(tmp_path / "env"),
        "HOME": "/incorrect", "XDG_CONFIG_HOME": "/incorrect",
    })
    return capture.read_text().splitlines()


def valid_immutable_digests_and_checksums(lock):
    digest = re.compile(r"sha256:[a-f0-9]{64}$")
    return (
        bool(digest.fullmatch(lock["base"]["digest"]))
        and all(digest.fullmatch(v) for v in lock["base"]["manifests"].values())
        and bool(re.fullmatch(r"[a-f0-9]{64}", lock["oscar"]["sha256"]))
        and lock["oscar"]["commit"] in lock["oscar"]["url"]
    )


def no_legacy_copy_import_or_conversion_in_startup():
    paths = [ROOT / "root/usr/local/bin/oscar-start", ROOT / "root/defaults/autostart_wayland"]
    for path in paths:
        assert path.is_file(), f"{path.name} missing"
        text = "\n".join(l for l in path.read_text().splitlines() if not l.startswith("#"))
        if re.search(r"\b(cp|rsync|sqlite3|import|convert|mv)\b", text):
            return False
    return True
