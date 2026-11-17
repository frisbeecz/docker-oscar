"""Local contracts for the disposable experiment, not production acceptance."""
import json
from pathlib import Path

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
