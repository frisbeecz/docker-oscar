"""Exercise actual release gate on synthetic, explicitly non-release evidence."""
import gzip
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import shutil
import tarfile

import pytest

from ci import CLEAN_DIFF_SHA256, sha256_file, state_identity
from ci.build_image import inspect_oci

ROOT = Path(__file__).resolve().parents[2]
GATES = ["static", "helm-3.19.0", "helm-4.3.2", "native-amd64", "native-arm64"]
RUNTIME = {"containerRunning", "httpReady", "oscarStable"}
PROCESS = {"pid": 42, "start": "12345", "uid": 1234, "gid": 2345, "exe": "/usr/bin/OSCAR20",
           "args": ["OSCAR20", "--legacy", "--datadir", "/config/Documents/OSCAR20_Data"]}


def product():
    assert (ROOT / "ci/release.py").is_file(), "release gate missing"
    return importlib.import_module("ci.release")


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def archive(path, arch):
    blobs = {}
    def blob(data):
        digest = hashlib.sha256(data).hexdigest()
        blobs["blobs/sha256/" + digest] = data
        return {"digest": "sha256:" + digest, "size": len(data)}
    raw = b"unit-test synthetic layer"
    config = blob(json.dumps({"os": "linux", "architecture": arch, "rootfs": {
        "diff_ids": ["sha256:" + hashlib.sha256(raw).hexdigest()]}}).encode())
    manifest = blob(json.dumps({"schemaVersion": 2, "config": config, "layers": [{
        **blob(gzip.compress(raw)), "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip"}]}).encode())
    blobs["index.json"] = json.dumps({"schemaVersion": 2, "manifests": [manifest]}).encode()
    with tarfile.open(path, "w") as tar:
        for name, data in blobs.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))


@pytest.fixture
def evidence(tmp_path):
    project = tmp_path / "checkout"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".gitignore").write_text("artifacts/\n")
    lock = json.loads((ROOT / "versions.lock.json").read_text())
    lock["oscar"]["sha256"] = hashlib.sha256(b"synthetic upstream").hexdigest()
    dump(project / "versions.lock.json", lock)
    (project / "charts/oscar").mkdir(parents=True)
    (project / "charts/oscar/Chart.yaml").write_text("version: 0.1.0\nappVersion: 2.1.1\n")
    subprocess.run(["git", "add", ".gitignore", "versions.lock.json", "charts/oscar/Chart.yaml"],
                   cwd=project, check=True)
    subprocess.run(["git", "-c", "user.name=CI synthetic", "-c", "user.email=ci@example.org",
                    "commit", "-qm", "synthetic evidence fixture"], cwd=project, check=True)
    commit = state_identity(project)["gitCommit"]
    directory = project / "artifacts"
    base = {"schemaVersion": 1, "gitCommit": commit, "dirtyDiffSha256": CLEAN_DIFF_SHA256,
            "command": ["python3", "-m", "ci.synthetic"], "cwd": str(project),
            "exitCode": 0, "platform": {"system": "Linux", "machine": "x86_64", "python": "3.14.10"},
            "checks": {"synthetic": True}}
    for arch, machine in [("amd64", "x86_64"), ("arm64", "aarch64")]:
        folder = directory / "native" / arch
        folder.mkdir(parents=True)
        image = folder / f"image-{arch}.oci.tar"
        archive(image, arch)
        identity = inspect_oci(image, arch)
        common = {**base, "arch": arch, "platform": {**base["platform"], "machine": machine},
                  **identity, "archiveSha256": sha256_file(image)}
        common["image"] = f"oscar-under-test:{arch}"
        build = {**common, "archive": str(image), "sources": lock, "checks": {
            "nativeHost": True, "nativeDaemon": True, "singleManifest": True, "configAndLayerIdentity": True}}
        dump(folder / f"build-{arch}.json", build)
        dump(folder / f"runtime-{arch}.json", {**common, "checks": dict.fromkeys(RUNTIME, True),
             "testScope": "startup-smoke-v1", "durationSeconds": 10.0, "process": PROCESS})
    dump(directory / "static/check.json", {**base, "checks": dict.fromkeys(
        ["actionlint", "yamllint", "hadolint", "shellcheck", "pythonLint", "pytest"], True)})
    for version in ("3.19.0", "4.3.2"):
        folder = directory / "chart" / f"helm-{version}"
        folder.mkdir(parents=True)
        package = folder / "oscar-0.1.0.tgz"
        package.write_bytes(b"synthetic chart")
        dump(folder / "chart.json", {**base, "helmVersion": "v" + version,
             "checks": dict.fromkeys(["pytest", "lint", "render", "strictSchemas", "routeMatrix"], True),
             "matrix": {name: {"valid": 1, "invalid": 0, "errors": 0, "skipped": 0} for name in (
                 "routes-0-0", "routes-1-0", "routes-0-1", "routes-1-1", "existing-claims",
                 "digest", "empty-storage-class", "extra-pvc")}})
        dump(folder / "package.json", {**base, "chartVersion": "0.1.0",
             "archiveSha256": sha256_file(package), "checks": {"packagedChartTested": True}})
    source = directory / "sources"
    source.mkdir()
    (source / "upstream.tar.gz").write_bytes(b"synthetic upstream")
    (source / "packaging.tar.gz").write_bytes(b"synthetic packaging")
    with (source / "project-source.tar.gz").open("wb") as f:
        subprocess.run(["git", "archive", "--format=tar.gz", commit], cwd=project, check=True, stdout=f)
    dump(source / "origin.json", {**base, "oscar": lock["oscar"], "checks": dict.fromkeys(
        ["sourceChecksum", "upstreamLicense", "patchList", "packagingInputs"], True),
        "sourceArchive": {"path": "upstream.tar.gz", "sha256": sha256_file(source / "upstream.tar.gz")},
        "packaging": {"path": "packaging.tar.gz", "sha256": sha256_file(source / "packaging.tar.gz")}})
    dump(source / "project.json", {**base, "archiveSha256": sha256_file(source / "project-source.tar.gz"),
                                  "checks": {"gitArchive": True}})
    for arch in ("amd64", "arm64"):
        shutil.copytree(source, directory / "native" / arch / "sources")
    run = {"id": 123, "run_attempt": 1, "head_sha": commit, "event": "push", "head_branch": "main",
           "html_url": "https://github.com/frisbeecz/docker-oscar/actions/runs/123",
           "repository": {"full_name": "frisbeecz/docker-oscar"}}
    jobs = [{"id": i, "name": name, "status": "completed", "conclusion": "success",
             "head_sha": commit, "run_id": 123, "run_attempt": 1,
             "html_url": f"https://github.com/frisbeecz/docker-oscar/actions/runs/123/job/{i}"}
            for i, name in enumerate(GATES, 1)]
    dump(directory / "evidence/run.json", run)
    dump(directory / "evidence/jobs.json", jobs)
    return project, directory, commit


def test_accept_exact_clean_evidence(evidence):
    project, directory, commit = evidence
    result = product().verify(directory, commit, project=project)
    assert set(result["platforms"]) == {"amd64", "arm64"}
    assert result["gitCommit"] == commit
    assert result["runUrl"].endswith("/123")
    assert result["testScope"] == "startup-smoke-v1"


@pytest.mark.parametrize("field,value", [
    ("gitCommit", "f" * 40), ("dirtyDiffSha256", "f" * 64), ("arch", "arm64"),
    ("exitCode", 1), ("checks", {}), ("manifestDigest", "sha256:" + "f" * 64),
    ("configDigest", "sha256:" + "f" * 64), ("layerDigests", []),
    ("archiveSha256", "f" * 64), ("image", "unrelated:latest"),
    ("platform", {"system": "Darwin", "machine": "x86_64"})])
def test_reject_mismatched_receipt(evidence, field, value):
    project, directory, commit = evidence
    path = directory / "native/amd64/runtime-amd64.json"
    data = json.loads(path.read_text())
    data[field] = value
    dump(path, data)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


@pytest.mark.parametrize("missing", [
    "native/arm64/runtime-arm64.json", "native/amd64/build-amd64.json",
    "chart/helm-3.19.0/chart.json", "sources/origin.json", "evidence/jobs.json",
    "native/arm64/sources/origin.json"])
def test_missing_gate_is_not_skipped(evidence, missing):
    project, directory, commit = evidence
    (directory / missing).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        product().verify(directory, commit, project=project)


@pytest.mark.parametrize("change", ["archive", "source", "chart", "alpha",
                                    "job-failed", "job-skipped", "job-missing", "run-sha"])
def test_tamper_and_failed_jobs_rejected(evidence, change):
    project, directory, commit = evidence
    if change in {"archive", "source", "chart"}:
        path = {"archive": "native/amd64/image-amd64.oci.tar", "source": "sources/packaging.tar.gz",
                "chart": "chart/helm-4.3.2/oscar-0.1.0.tgz"}[change]
        with (directory / path).open("ab") as f:
            f.write(b"TAMPER")
    elif change == "alpha":
        path = directory / "native/amd64/build-amd64.json"
        data = json.loads(path.read_text())
        data["sources"]["oscar"]["version"] = "2.2.0-alpha-1"
        dump(path, data)
    elif change == "run-sha":
        path = directory / "evidence/run.json"
        data = json.loads(path.read_text())
        data["head_sha"] = "f" * 40
        dump(path, data)
    else:
        path = directory / "evidence/jobs.json"
        data = json.loads(path.read_text())
        if change == "job-missing":
            data.pop()
        else:
            data[0]["conclusion"] = change.removeprefix("job-")
        dump(path, data)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


def test_refuse_dirty_or_wrong_commit(evidence):
    project, directory, commit = evidence
    with pytest.raises(ValueError):
        product().verify(directory, "f" * 40, project=project)
    (project / "untracked").write_text("dirty")
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


def test_publish_rejects_before_first_mutation(evidence, monkeypatch):
    project, directory, commit = evidence
    release = product()
    writes = []
    def forbidden(*args, **kwargs):
        writes.append(args)
        raise AssertionError("external mutation before validation")
    monkeypatch.setattr(release, "mutate", forbidden)
    (directory / "native/arm64/runtime-arm64.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert writes == []


def test_unsafe_tag_is_data_not_shell():
    release = product()
    for tag in ["v0.1.0; touch /tmp/pwn", "v2.2.0-alpha-1", "$(id)", "../release", "main"]:
        with pytest.raises(ValueError):
            release.validate_tag(tag, "0.1.0")
    assert release.validate_tag("v0.1.0", "0.1.0") == "v0.1.0"


def test_artifact_symlink_rejected(evidence, tmp_path):
    project, directory, commit = evidence
    folder = directory / "native/amd64"
    moved = tmp_path / "outside"
    folder.rename(moved)
    folder.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


def test_sources_are_public_and_hash_verified_before_binary_publish(monkeypatch):
    release = product()
    seen = []
    def fetch(url, *, timeout):
        seen.append(url)
        return io.BytesIO(b"source bytes")
    monkeypatch.setattr(release, "urlopen", fetch, raising=False)
    manifest = {"sources": {"source.tar.gz": hashlib.sha256(b"source bytes").hexdigest()}}
    assert hasattr(release, "verify_source_assets"), "public source-first verification missing"
    release.verify_source_assets(manifest, "v0.1.0")
    assert seen == ["https://github.com/frisbeecz/docker-oscar/releases/download/v0.1.0/source.tar.gz"]
    manifest["sources"]["source.tar.gz"] = "f" * 64
    with pytest.raises(ValueError):
        release.verify_source_assets(manifest, "v0.1.0")


@pytest.mark.parametrize("check", ["containerRunning", "httpReady", "oscarStable"])
@pytest.mark.parametrize("value", ["false", -1, 0, 1, None, False])
def test_runtime_receipt_checks_are_typed(evidence, check, value):
    project, directory, commit = evidence
    path = directory / "native/amd64/runtime-amd64.json"
    data = json.loads(path.read_text())
    data["checks"][check] = value
    dump(path, data)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


@pytest.mark.parametrize("field,value", [
    ("testScope", None), ("testScope", "legacy-gui"), ("durationSeconds", True),
    ("durationSeconds", "10"), ("durationSeconds", None), ("durationSeconds", 9.999),
    ("durationSeconds", float("nan")), ("durationSeconds", float("inf")),
    ("cleanupError", "owned cleanup failed"), ("cleanupError", ""),
    ("error", "smoke failed"), ("exitCode", False), ("process", {}),
    ("checks", {"gui": True, "mediaFrames": 12}),
    ("checks", {"containerRunning": True, "httpReady": True, "oscarStable": True, "dataPersisted": True}),
])
def test_runtime_scope_duration_and_failures_rejected(evidence, field, value):
    project, directory, commit = evidence
    path = directory / "native/amd64/runtime-amd64.json"
    data = json.loads(path.read_text())
    data[field] = value
    dump(path, data)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


@pytest.mark.parametrize("field,value", [
    ("pid", True), ("pid", 0), ("start", ""), ("start", 123),
    ("uid", 0), ("gid", 0), ("exe", "/tmp/OSCAR20"), ("args", []),
])
def test_runtime_process_identity_rejected(evidence, field, value):
    project, directory, commit = evidence
    path = directory / "native/arm64/runtime-arm64.json"
    data = json.loads(path.read_text())
    data["process"][field] = value
    dump(path, data)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


def test_chart_matrix_cannot_substitute_unrelated_cases(evidence):
    project, directory, commit = evidence
    path = directory / "chart/helm-3.19.0/chart.json"
    data = json.loads(path.read_text())
    data["matrix"]["unrelated"] = data["matrix"].pop("routes-1-1")
    dump(path, data)
    with pytest.raises(ValueError):
        product().verify(directory, commit, project=project)


@pytest.fixture
def publication(evidence, monkeypatch):
    """Only third-party boundaries are doubled; the entire local gate stays real."""
    project, directory, commit = evidence
    release = product()
    data = json.loads((directory / "evidence/run.json").read_text())
    data["head_branch"] = "v0.1.0"
    dump(directory / "evidence/run.json", data)
    # Tool lock is read using project-relative ci/tools.lock.json; keep the
    # synthetic checkout clean without adding another source-state mutation.
    original_lock = release.load_lock
    monkeypatch.setattr(release, "load_lock", lambda name="versions.lock.json", **kw:
                        original_lock("ci/tools.lock.json") if name == "ci/tools.lock.json"
                        else original_lock(name, **kw))
    for key, value in {
        "GITHUB_REF_NAME": "v0.1.0", "GITHUB_REF_TYPE": "tag", "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": "frisbeecz/docker-oscar", "GITHUB_SHA": commit,
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "frisbeecz", "GH_TOKEN": "synthetic-not-a-token",
    }.items():
        monkeypatch.setenv(key, value)
    commands, events = [], []
    identity = {a: inspect_oci(directory / f"native/{a}/image-{a}.oci.tar", a)
                for a in ("amd64", "arm64")}
    index = json.dumps({"schemaVersion": 2, "manifests": [
        {"platform": {"architecture": a, "os": "linux"}, "digest": p["manifestDigest"]}
        for a, p in identity.items()]}).encode()
    chart_raw = b'{"schemaVersion":2,"artifactType":"application/vnd.cncf.helm.config.v1+json"}'
    state = {"index": index, "chart": chart_raw, "tag": index}
    original_run = release.run
    def server_run(command, **kwargs):
        argv = [str(c) for c in command]
        if argv[0] == "git":
            return original_run(argv, **kwargs)
        assert argv[:3] == ["skopeo", "inspect", "--raw"], argv
        ref = argv[-1]
        if "/charts/oscar:" in ref:
            raw = state["chart"]
        elif ref.endswith(":2.1.1-r1"):
            raw = state["tag"]
        elif any(ref.endswith(p["manifestDigest"]) for p in identity.values()):
            arch = next(a for a, p in identity.items() if ref.endswith(p["manifestDigest"]))
            with tarfile.open(directory / f"native/{arch}/image-{arch}.oci.tar") as tar:
                raw = tar.extractfile("blobs/sha256/" + identity[arch]["manifestDigest"][7:]).read()
        else:
            raw = state["index"]
        return subprocess.CompletedProcess(argv, 0, stdout=raw)
    def server_output(command, **kwargs):
        argv = [str(c) for c in command]
        if argv == ["skopeo", "--version"]:
            return "skopeo version 1.25.1"
        if argv[0] == "docker" and argv[-2:] == ["buildx", "version"]:
            return "github.com/docker/buildx v0.39.0"
        if argv[:2] == ["skopeo", "inspect"] and "--raw" not in argv:
            arch = argv[-1].rsplit("-", 1)[-1]
            return json.dumps({"Digest": identity[arch]["manifestDigest"]})
        if argv[:3] == ["skopeo", "inspect", "--raw"]:
            return server_run(command, **kwargs).stdout.decode()
        raise AssertionError(argv)
    def server_evidence(path):
        for name in ("run.json", "jobs.json"):
            shutil.copyfile(directory / "evidence" / name, Path(path) / name)
    def server_mutate(command, **kwargs):
        argv = [str(c) for c in command]
        commands.append(argv)
        events.append(" ".join(argv[:3]))
        if argv[:2] == ["docker", "--config"]:
            config = Path(argv[2]) / "config.json"
            assert config.is_file(), "isolated auth config lost the pinned Buildx plugin directory"
            assert json.loads(config.read_text())["cliPluginsExtraDirs"] == [
                str(project / ".venv/docker/cli-plugins")]
        if argv[:3] == ["gh", "release", "download"]:
            destination = Path(argv[argv.index("--dir") + 1])
            for file in (directory / "sources").iterdir():
                shutil.copyfile(file, destination / file.name)
        if argv[:2] == ["helm", "pull"]:
            shutil.copyfile(directory / "chart/helm-4.3.2/oscar-0.1.0.tgz",
                            Path(argv[argv.index("--destination") + 1]) / "oscar-0.1.0.tgz")
        return subprocess.CompletedProcess(argv, 0)
    def public_fetch(url, *, timeout):
        events.append("anonymous source read")
        return io.BytesIO((directory / "sources" / url.rsplit("/", 1)[-1]).read_bytes())
    monkeypatch.setattr(release, "run", server_run)
    monkeypatch.setattr(release, "output", server_output)
    monkeypatch.setattr(release, "github_evidence", server_evidence)
    monkeypatch.setattr(release, "mutate", server_mutate)
    monkeypatch.setattr(release, "urlopen", public_fetch)
    return release, project, directory, commit, commands, events, state


def test_publish_sources_first_preserves_digests_and_never_rebuilds(publication):
    release, project, directory, commit, commands, events, _ = publication
    result = release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert events[0] == "gh release create"
    assert events.index("anonymous source read") < events.index("skopeo login --authfile")
    copies = [c for c in commands if c[:2] == ["skopeo", "copy"]]
    assert len(copies) == 2 and all("--preserve-digests" in c for c in copies)
    assert not any("build" in c or "package" in c for c in commands)
    assert commands[-1][:3] == ["gh", "release", "edit"]
    assert result["imageIndexDigest"].startswith("sha256:")
    assert result["chartDigest"].startswith("sha256:")
    assert result["testScope"] == "startup-smoke-v1"
    assert json.loads((directory / "release-manifest.json").read_text())["gitCommit"] == commit
    assert all("synthetic-not-a-token" not in " ".join(c) for c in commands)


def test_publication_network_failure_stops_without_retry_or_finalization(publication, monkeypatch):
    release, project, directory, commit, commands, events, _ = publication
    def unavailable(*args, **kwargs):
        raise OSError("synthetic network denial")
    monkeypatch.setattr(release, "urlopen", unavailable)
    with pytest.raises(OSError):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert len(commands) == 1 and commands[0][:3] == ["gh", "release", "create"]


def test_verify_published_rejects_tag_pointing_elsewhere(publication):
    release, project, directory, commit, _, _, state = publication
    release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    state["tag"] = b'{"schemaVersion":2,"manifests":[]}'
    with pytest.raises(ValueError):
        release.verify_published(directory / "release-manifest.json")


def test_verify_published_requires_current_scope_before_external_reads(publication, monkeypatch):
    release, project, directory, commit, _, _, _ = publication
    release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    path = directory / "release-manifest.json"
    data = json.loads(path.read_text())
    data.pop("testScope")
    dump(path, data)
    def forbidden(*args, **kwargs):
        raise AssertionError("external access before scope validation")
    monkeypatch.setattr(release, "run", forbidden)
    monkeypatch.setattr(release, "mutate", forbidden)
    with pytest.raises(ValueError, match="scope"):
        release.verify_published(path)
