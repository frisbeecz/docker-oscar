"""The real scan/receipt orchestration; only native Docker, downloads and Trivy are doubled."""
import copy
import importlib
import json
from pathlib import Path
import subprocess

import pytest

from ci import sha256_file


def security():
    return importlib.import_module("ci.security")


def report(*findings):
    return {
        "Metadata": {"ImageID": "sha256:" + "d" * 64, "OS": {"Family": "alpine", "Name": "3.24.4"},
                     "ImageConfig": {"architecture": "amd64", "os": "linux"}},
        "Results": [{"Target": "synthetic Alpine packages", "Class": "os-pkgs", "Type": "alpine"},
                    {"Target": "Python", "Class": "lang-pkgs", "Type": "python-pkg", "Vulnerabilities": [
             {"VulnerabilityID": identity, "Severity": severity} for identity, severity in findings]}],
    }


def test_known_high_remains_visible_not_ignored():
    data = report(("CVE-2026-114613", "HIGH"), ("CVE-other-medium", "MEDIUM"))
    original = copy.deepcopy(data)
    result = security().validate_report(data, {"CVE-2026-114613"})
    assert result["findings"] == {"HIGH": 1, "MEDIUM": 1}
    assert result["acceptedHigh"] == ["CVE-2026-114613"]
    assert data == original


@pytest.mark.parametrize("identity", [
    "CVE-2026-114613", "GHSA-6v7p-g79w-8964", "CVE-2025-47273",
    "CVE-2026-97687", "CVE-2026-97689",
])
def test_former_vendored_high_findings_no_longer_have_runtime_exceptions(identity):
    with pytest.raises(ValueError):
        security().validate_report(report((identity, "HIGH")), security().ACCEPTED_HIGH)


def test_all_eight_accepted_findings_remain_visible():
    data = report(
        ("CVE-2026-114613", "HIGH"), ("GHSA-6v7p-g79w-8964", "HIGH"),
        ("CVE-2025-47273", "HIGH"), ("CVE-2026-59890", "MEDIUM"),
        ("GHSA-xmj3-9gf7-h52w", "LOW"), ("CVE-2026-97687", "HIGH"),
        ("CVE-2026-97689", "HIGH"), ("CVE-2026-97688", "MEDIUM"),
    )
    original = copy.deepcopy(data)
    legacy_high = {"CVE-2026-114613", "GHSA-6v7p-g79w-8964", "CVE-2025-47273",
                   "CVE-2026-97687", "CVE-2026-97689"}
    result = security().validate_report(data, legacy_high)
    assert result == {"findings": {"HIGH": 5, "MEDIUM": 2, "LOW": 1},
                      "acceptedHigh": sorted(legacy_high)}
    assert data == original


@pytest.mark.parametrize("empty", ["omitted", None, []])
def test_complete_zero_vulnerability_results_are_valid(empty):
    data = report()
    for result in data["Results"]:
        if empty == "omitted":
            result.pop("Vulnerabilities", None)
        else:
            result["Vulnerabilities"] = empty
    assert security().validate_report(data, security().ACCEPTED_HIGH) == {
        "findings": {}, "acceptedHigh": []}


@pytest.mark.parametrize("mutation", [
    "empty-result", "no-os", "no-python", "target", "class", "type",
    "vulnerabilities-object", "vulnerability-id", "severity",
])
def test_incomplete_package_scan_cannot_pass(mutation):
    data = report(("CVE-2026-114613", "HIGH"))
    if mutation == "empty-result":
        data["Results"] = [{}]
    elif mutation == "no-os":
        data["Results"].pop(0)
    elif mutation == "no-python":
        data["Results"].pop(1)
    elif mutation in {"target", "class", "type"}:
        data["Results"][1].pop(mutation.title())
    elif mutation == "vulnerabilities-object":
        data["Results"][1]["Vulnerabilities"] = {}
    else:
        field = "VulnerabilityID" if mutation == "vulnerability-id" else "Severity"
        data["Results"][1]["Vulnerabilities"][0][field] = ""
    with pytest.raises(ValueError):
        security().validate_report(data, security().ACCEPTED_HIGH)


@pytest.mark.parametrize("identity,severity", [("CVE-new", "HIGH"), ("CVE-2026-114613", "CRITICAL")])
def test_new_high_or_any_critical_blocks(identity, severity):
    with pytest.raises(ValueError):
        security().validate_report(report((identity, severity)), {"CVE-2026-114613"})


@pytest.fixture
def scanner(tmp_path, monkeypatch):
    module = security()
    calls = []
    build = {"exitCode": 0, "arch": "amd64", "image": "oscar-under-test:amd64",
             "gitCommit": "a" * 40, "dirtyDiffSha256": "b" * 64,
             "manifestDigest": "sha256:" + "c" * 64, "configDigest": "sha256:" + "d" * 64,
             "layerDigests": ["sha256:" + "e" * 64], "diffIds": ["sha256:" + "f" * 64]}
    archive = tmp_path / "image.oci.tar"
    archive.write_bytes(b"synthetic tested archive")
    build.update(archive=str(archive), archiveSha256=sha256_file(archive))
    (tmp_path / "build-amd64.json").write_text(json.dumps(build))
    state = {"report": report(), "fail": None}
    pin = {"version": "0.76.2", "artifacts": {"amd64": {"url": "https://example.test/trivy",
                                                       "sha256": "0" * 64}}}
    monkeypatch.setattr(module, "load_lock", lambda *args: {"trivy": pin})
    monkeypatch.setattr(module, "require_native", lambda arch: arch)
    monkeypatch.setattr(module, "require_disposable_runner", lambda: None)
    monkeypatch.setattr(module, "require_native_daemon", lambda arch: None)
    monkeypatch.setattr(module, "receipt", lambda **kw: {
        "gitCommit": build["gitCommit"], "dirtyDiffSha256": build["dirtyDiffSha256"], "checks": {}})
    image = {"Os": "linux", "Architecture": "amd64", "Id": build["configDigest"],
             "RootFS": {"Layers": build["diffIds"]}}
    def output(command):
        calls.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            return json.dumps([image])
        assert command[-1] == "--version"
        return "Version: 0.76.2"
    monkeypatch.setattr(module, "output", output)
    monkeypatch.setattr(module, "download", lambda p: tmp_path / "synthetic-tool.tar.gz")
    def install(archive, name, target):
        assert name == "trivy"
        Path(target).write_bytes(b"external binary boundary")
    monkeypatch.setattr(module, "install_binary", install)
    def run(command, **kwargs):
        command = [str(v) for v in command]
        calls.append(command)
        if state["fail"]:
            raise subprocess.CalledProcessError(1, command)
        if "--download-db-only" in command:
            cache = Path(command[command.index("--cache-dir") + 1])
            (cache / "db").mkdir(parents=True)
            (cache / "db/metadata.json").write_text('{"UpdatedAt":"synthetic-test-db"}')
        else:
            assert "--skip-db-update" in command and "--ignore-unfixed" not in command
            Path(command[command.index("--output") + 1]).write_text(json.dumps(state["report"]))
    monkeypatch.setattr(module, "run", run)
    return module, tmp_path, build, calls, state, image


def test_one_complete_candidate_scan_bound_to_tested_image(scanner):
    module, folder, build, calls, state, _ = scanner
    state["report"] = report(("CVE-other-medium", "MEDIUM"))
    value = module.scan(build["image"], "amd64", folder)
    assert value["exitCode"] == 0 and value["checks"] == {"noCritical": True, "acceptedHigh": True}
    assert all(value[k] == build[k] for k in ("image", "arch", "configDigest", "manifestDigest",
                                            "archiveSha256"))
    assert value["reportSha256"] == sha256_file(folder / "security-report.json")
    assert value["findings"] == {"MEDIUM": 1} and value["database"]["UpdatedAt"] == "synthetic-test-db"
    assert sum("--download-db-only" in c for c in calls) == 1
    scans = [c for c in calls if "--scanners" in c]
    assert len(scans) == 1 and scans[0][-1] == build["image"]
    assert "--image-src" in scans[0] and scans[0][scans[0].index("--image-src") + 1] == "docker"
    assert not (folder / "trivy").exists()
    assert not (folder / "trivy-cache").exists()
    assert not Path(scans[0][scans[0].index("--cache-dir") + 1]).exists()


@pytest.mark.parametrize("failure", ["image", "arch", "config", "report-image", "report-arch",
                                     "critical", "new-high", "tool"])
def test_scan_failure_preserves_evidence_and_never_passes(scanner, failure):
    module, folder, build, calls, state, image = scanner
    requested = build["image"]
    if failure == "image":
        requested = "unrelated:latest"
    elif failure == "arch":
        build["arch"] = "arm64"
    elif failure == "config":
        image["Id"] = "sha256:" + "0" * 64
    elif failure == "report-image":
        state["report"]["Metadata"]["ImageID"] = "sha256:" + "0" * 64
    elif failure == "report-arch":
        state["report"]["Metadata"]["ImageConfig"]["architecture"] = "arm64"
    elif failure in {"critical", "new-high"}:
        state["report"] = report(("CVE-unapproved", "CRITICAL" if failure == "critical" else "HIGH"))
    else:
        state["fail"] = True
    (folder / "build-amd64.json").write_text(json.dumps(build))
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        module.scan(requested, "amd64", folder)
    result = json.loads((folder / "security-amd64.json").read_text())
    assert result["exitCode"] == 1
    if failure.startswith("report") or failure in {"critical", "new-high"}:
        assert (folder / "security-report.json").is_file()
    if failure in {"image", "arch", "config"}:
        assert not any("--download-db-only" in c for c in calls)
