"""Explicit native startup-only suite; not selected by the default local suite."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture(scope="session")
def receipt():
    arch = os.environ.get("OSCAR_NATIVE_ARCH")
    assert arch in {"amd64", "arm64"}, "run only on an explicitly selected native Linux runner"
    out = Path("artifacts/native") / arch
    subprocess.run([sys.executable, "-m", "ci.runtime", "--image", f"oscar-under-test:{arch}",
                    "--arch", arch, "--run-id", f"pytest-{arch}", "--artifacts", str(out)], check=True)
    result = json.loads((out / f"runtime-{arch}.json").read_text())
    assert result["exitCode"] == 0
    return result


def test_startup_smoke(receipt):
    assert receipt["testScope"] == "startup-smoke-v1"
    assert receipt["checks"] == {"containerRunning": True, "httpReady": True, "oscarStable": True}
    assert type(receipt["durationSeconds"]) in (int, float) and receipt["durationSeconds"] >= 10
    process = receipt["process"]
    assert type(process["pid"]) is int and process["pid"] > 0
    assert process["start"].isdecimal()
    assert (process["uid"], process["gid"]) == (1234, 2345)
    assert process["exe"] == "/usr/bin/OSCAR20"
    assert process["args"] == [
        "OSCAR20", "--legacy", "--datadir", "/config/Documents/OSCAR20_Data"]
    assert "cleanupError" not in receipt
