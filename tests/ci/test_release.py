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
import tomllib

import pytest
import yaml

from ci import CLEAN_DIFF_SHA256, sha256_file, state_identity
from ci.build_image import inspect_oci

ROOT = Path(__file__).resolve().parents[2]
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
    return project, directory, commit


def test_accept_exact_clean_evidence(evidence):
    project, directory, commit = evidence
    result = product().verify(directory, commit, project=project)
    assert set(result["platforms"]) == {"amd64", "arm64"}
    assert result["gitCommit"] == commit
    assert result["testScope"] == "startup-smoke-v1"


def test_current_release_versions_are_consistent(evidence):
    project, directory, commit = evidence
    result = product().verify(directory, commit, project=project)
    lock = json.loads((ROOT / "versions.lock.json").read_text())
    chart = yaml.safe_load((ROOT / "charts/oscar/Chart.yaml").read_text())
    values = yaml.safe_load((ROOT / "charts/oscar/values.yaml").read_text())
    project_metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert {
        "project": project_metadata["project"]["version"],
        "chart": chart["version"],
        "app": chart["appVersion"],
        "oscar": lock["oscar"]["version"],
        "locked_image": lock["imageVersion"],
        "default_image": values["image"]["tag"],
        "release_image": result["imageTag"],
        "release_oscar": result["oscarVersion"],
    } == {
        "project": "1.0.2", "chart": "1.0.2", "app": "2.1.1",
        "oscar": "2.1.1", "locked_image": "2.1.1-r7",
        "default_image": "2.1.1-r7", "release_image": "2.1.1-r7",
        "release_oscar": "2.1.1",
    }


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
    "chart/helm-3.19.0/chart.json", "sources/origin.json"])
def test_missing_gate_is_not_skipped(evidence, missing):
    project, directory, commit = evidence
    (directory / missing).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        product().verify(directory, commit, project=project)


@pytest.mark.parametrize("change", ["archive", "source", "chart", "alpha"])
def test_tampered_artifacts_rejected(evidence, change):
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
        "DOCKERHUB_TOKEN": "synthetic-dockerhub-token",
    }.items():
        monkeypatch.setenv(key, value)
    commands, events = [], []
    identity = {a: inspect_oci(directory / f"native/{a}/image-{a}.oci.tar", a)
                for a in ("amd64", "arm64")}
    index = json.dumps({"schemaVersion": 2, "manifests": [
        {"platform": {"architecture": a, "os": "linux"}, "digest": p["manifestDigest"]}
        for a, p in identity.items()]}).encode()
    chart_raw = b'{"schemaVersion":2,"artifactType":"application/vnd.cncf.helm.config.v1+json"}'
    state = {"index": index, "chart": chart_raw, "tag": index, "dockerhub": index}
    original_run = release.run
    def server_run(command, **kwargs):
        argv = [str(c) for c in command]
        if argv[0] == "git":
            return original_run(argv, **kwargs)
        assert argv[:3] == ["skopeo", "inspect", "--raw"], argv
        ref = argv[-1]
        if ref.startswith(("docker://docker.io/frisbeecz24/docker-oscar:",
                           "docker://docker.io/frisbeecz24/frisbeecz:")):
            raw = state["dockerhub"]
        elif "/charts/oscar:" in ref:
            raw = state["chart"]
        elif ref.endswith(":2.1.1-r7"):
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
        if argv[:3] == ["skopeo", "inspect", "--raw"]:
            return server_run(command, **kwargs).stdout.decode()
        raise AssertionError(argv)
    def server_mutate(command, **kwargs):
        argv = [str(c) for c in command]
        commands.append(argv)
        events.append(" ".join(argv[:3]))
        if argv[:2] == ["docker", "--config"]:
            config = Path(argv[2]) / "config.json"
            assert config.is_file(), "isolated auth config lost the pinned Buildx plugin directory"
            assert json.loads(config.read_text())["cliPluginsExtraDirs"] == [
                str(project / ".venv/docker/cli-plugins")]
        if argv[:2] == ["helm", "pull"]:
            shutil.copyfile(directory / "chart/helm-4.3.2/oscar-0.1.0.tgz",
                            Path(argv[argv.index("--destination") + 1]) / "oscar-0.1.0.tgz")
        return subprocess.CompletedProcess(argv, 0)
    def public_fetch(url, *, timeout):
        events.append("anonymous source read")
        return io.BytesIO((directory / "sources" / url.rsplit("/", 1)[-1]).read_bytes())
    monkeypatch.setattr(release, "run", server_run)
    monkeypatch.setattr(release, "output", server_output)
    monkeypatch.setattr(release, "mutate", server_mutate)
    monkeypatch.setattr(release, "urlopen", public_fetch)
    def metadata(**kwargs):
        assert kwargs == {"token": "synthetic-dockerhub-token", "project": project}
        events.append("Docker Hub metadata")
    monkeypatch.setattr(release, "update_dockerhub_metadata", metadata, raising=False)
    # Protocol and native Helm compatibility are exercised in test_chart_registry.
    monkeypatch.setattr(release, "publish_chart",
                        lambda *args, **kwargs: "sha256:" + hashlib.sha256(state["chart"]).hexdigest())
    return release, project, directory, commit, commands, events, state


def test_publish_sources_first_preserves_digests_and_never_rebuilds(publication):
    release, project, directory, commit, commands, events, _ = publication
    result = release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert events[0] == "gh release create"
    assert events.index("anonymous source read") < events.index("skopeo login --authfile")
    copies = [c for c in commands if c[:2] == ["skopeo", "copy"]]
    archives = [c for c in copies if c[-2].startswith("oci-archive:")]
    assert len(archives) == 2 and all("--preserve-digests" in c for c in copies)
    assert not any("build" in c or "package" in c for c in commands)
    assert commands[-1][:3] == ["gh", "release", "edit"]
    assert result["imageIndexDigest"].startswith("sha256:")
    assert result["chartDigest"].startswith("sha256:")
    assert result["testScope"] == "startup-smoke-v1"
    assert json.loads((directory / "release-manifest.json").read_text())["gitCommit"] == commit
    assert all("synthetic-not-a-token" not in " ".join(c) for c in commands)
    assert all("synthetic-dockerhub-token" not in " ".join(c) for c in commands)


def test_dockerhub_mirror_copies_complete_tested_index_by_digest(publication, monkeypatch):
    """Dropping --all or using a mutable GHCR tag must not silently mirror one platform."""
    release, project, directory, commit, commands, events, state = publication
    original = release.mutate
    logins = []
    def boundary(command, **kwargs):
        argv = list(map(str, command))
        if argv[:2] == ["skopeo", "login"] and argv[-1] == "docker.io":
            assert argv[argv.index("--username") + 1] == "frisbeecz24"
            assert "--password-stdin" in argv
            assert kwargs.get("input") == "synthetic-dockerhub-token"
            auth = Path(argv[argv.index("--authfile") + 1])
            assert auth.parent.parent == directory
            assert auth.parent.stat().st_mode & 0o777 == 0o700
            logins.append(auth)
        return original(command, **kwargs)
    monkeypatch.setattr(release, "mutate", boundary)
    result = release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    index_digest = "sha256:" + hashlib.sha256(state["index"]).hexdigest()
    mirrors = [c for c in commands if c[:2] == ["skopeo", "copy"]
               and c[-1] == "docker://docker.io/frisbeecz24/docker-oscar:2.1.1-r7"]
    assert len(mirrors) == 1 and len(logins) == 1
    assert "--all" in mirrors[0] and "--preserve-digests" in mirrors[0]
    assert mirrors[0][-2] == "docker://ghcr.io/frisbeecz/docker-oscar@" + index_digest
    assert Path(mirrors[0][mirrors[0].index("--authfile") + 1]) == logins[0]
    assert not logins[0].parent.exists(), "temporary registry credentials were not cleaned up"
    assert result["dockerHubRepository"] == "docker.io/frisbeecz24/docker-oscar"
    saved = json.loads((directory / "release-manifest.json").read_text())
    assert saved["dockerHubRepository"] == result["dockerHubRepository"]
    assert saved["imageIndexDigest"] == index_digest
    assert events.count("Docker Hub metadata") == 1


def test_missing_dockerhub_token_stops_before_external_writes(publication, monkeypatch):
    release, project, directory, commit, commands, _, _ = publication
    monkeypatch.delenv("DOCKERHUB_TOKEN")
    with pytest.raises(ValueError, match="DOCKERHUB_TOKEN"):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert commands == []


@pytest.mark.parametrize("failure", ["login", "copy", "readback"])
def test_dockerhub_failure_does_not_retry_or_finalize(publication, monkeypatch, failure):
    release, project, directory, commit, commands, _, state = publication
    original = release.mutate
    failures = []
    def boundary(command, **kwargs):
        argv = list(map(str, command))
        result = original(command, **kwargs)
        if ((failure == "login" and argv[:2] == ["skopeo", "login"] and argv[-1] == "docker.io")
                or (failure == "copy" and argv[:2] == ["skopeo", "copy"]
                    and argv[-1].startswith("docker://docker.io/"))):
            failures.append(argv)
            raise subprocess.CalledProcessError(1, argv, stderr="synthetic registry failure")
        return result
    monkeypatch.setattr(release, "mutate", boundary)
    if failure == "readback":
        state["dockerhub"] = b'{"schemaVersion":2,"manifests":[]}'
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert len(failures) == (0 if failure == "readback" else 1)
    assert not any(c[:3] == ["gh", "release", "edit"] for c in commands)


def test_verify_saved_ghcr_only_manifest_remains_supported(publication):
    release, project, directory, commit, _, _, state = publication
    release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    path = directory / "release-manifest.json"
    data = json.loads(path.read_text())
    data.pop("dockerHubRepository")
    dump(path, data)
    state["dockerhub"] = b"must not be read for a pre-mirror manifest"
    assert release.verify_published(path)["imageRepository"] == "ghcr.io/frisbeecz/docker-oscar"


def test_verify_saved_original_dockerhub_repository_remains_supported(publication):
    release, project, directory, commit, _, _, _ = publication
    release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    path = directory / "release-manifest.json"
    data = json.loads(path.read_text())
    data["dockerHubRepository"] = "docker.io/frisbeecz24/frisbeecz"
    dump(path, data)
    assert release.verify_published(path)["dockerHubRepository"] == data["dockerHubRepository"]


def test_metadata_failure_stops_publication_without_finalizing(publication, monkeypatch):
    release, project, directory, commit, commands, _, _ = publication
    def denied(**kwargs):
        raise ValueError("Docker Hub PATCH: HTTP 403")
    monkeypatch.setattr(release, "update_dockerhub_metadata", denied)
    with pytest.raises(ValueError, match="HTTP 403"):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert not any(c[:3] == ["gh", "release", "edit"] for c in commands)
    assert not any(c[:2] == ["skopeo", "copy"] and c[-1].startswith("docker://docker.io/")
                   for c in commands)


def test_unapproved_mirror_repository_is_rejected_before_external_reads(publication, monkeypatch):
    release, project, directory, commit, _, _, _ = publication
    release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    path = directory / "release-manifest.json"
    data = json.loads(path.read_text())
    data["dockerHubRepository"] = "docker.io/unapproved/repository"
    dump(path, data)
    def forbidden(*args, **kwargs):
        raise AssertionError("external access before repository validation")
    monkeypatch.setattr(release, "run", forbidden)
    with pytest.raises(ValueError, match="repository"):
        release.verify_published(path)


def test_publish_uses_workflow_gate_without_separate_job_evidence(publication):
    release, project, directory, commit, commands, _, _ = publication
    result = release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert result["runUrl"] == "https://github.com/frisbeecz/docker-oscar/actions/runs/123"
    assert result["runId"] == 123 and result["runAttempt"] == 1
    assert result["jobUrls"] == {}
    assert len([c for c in commands if c[:2] == ["helm", "pull"]]) == 1
    assert not any(c[:3] == ["gh", "release", "download"] for c in commands)


@pytest.mark.parametrize("failure", ["helm", "package", "chart-manifest"])
def test_final_chart_verification_failure_does_not_finalize(publication, monkeypatch, failure):
    release, project, directory, commit, commands, _, state = publication
    original = release.mutate
    def consumer(command, **kwargs):
        argv = list(map(str, command))
        if argv[:2] == ["helm", "pull"]:
            if failure == "helm":
                raise subprocess.CalledProcessError(1, argv, stderr="download failed")
            result = original(command, **kwargs)
            if failure == "package":
                (Path(argv[argv.index("--destination") + 1]) / "oscar-0.1.0.tgz").write_bytes(b"changed")
            if failure == "chart-manifest":
                state["chart"] = b'{"schemaVersion":2,"changed":true}'
            return result
        return original(command, **kwargs)
    monkeypatch.setattr(release, "mutate", consumer)
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert not any(c[:3] == ["gh", "release", "edit"] for c in commands)


def test_publication_network_failure_stops_without_retry_or_finalization(publication, monkeypatch):
    release, project, directory, commit, commands, events, _ = publication
    def unavailable(*args, **kwargs):
        raise OSError("synthetic network denial")
    monkeypatch.setattr(release, "urlopen", unavailable)
    with pytest.raises(OSError):
        release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert len(commands) == 1 and commands[0][:3] == ["gh", "release", "create"]


def test_publish_avoids_registry_read_of_untagged_chart(publication, monkeypatch):
    """Reintroducing Helm ExtendedCopy would fail on a registry hiding untagged manifests."""
    release, project, directory, commit, _, _, state = publication
    original = release.mutate

    def registry_boundary(command, **kwargs):
        if list(map(str, command))[:2] == ["helm", "push"]:
            raise subprocess.CalledProcessError(1, command, stderr='failed to perform "Tag": not found')
        return original(command, **kwargs)

    def direct_publish(path, *, sha256, version, username, token):
        assert Path(path).read_bytes() == b"synthetic chart"
        assert sha256 == hashlib.sha256(b"synthetic chart").hexdigest()
        assert (version, username, token) == ("0.1.0", "frisbeecz", "synthetic-not-a-token")
        return "sha256:" + hashlib.sha256(state["chart"]).hexdigest()

    monkeypatch.setattr(release, "mutate", registry_boundary)
    monkeypatch.setattr(release, "publish_chart", direct_publish, raising=False)
    result = release.publish(directory, commit, "ghcr.io/frisbeecz", project=project)
    assert result["chartReference"] == "ghcr.io/frisbeecz/charts/oscar:0.1.0"
    assert result["chartDigest"] == "sha256:" + hashlib.sha256(state["chart"]).hexdigest()


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
