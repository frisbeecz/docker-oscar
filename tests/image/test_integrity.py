"""Fail closed on corrupt images, incomplete evidence, and unintended writes."""
import gzip
import hashlib
import importlib
import io
import json
from pathlib import Path
import tarfile
import shutil
import subprocess

import pytest

from conftest import ROOT


def product(name):
    assert (ROOT / (name.replace(".", "/") + ".py")).is_file(), f"{name} missing"
    return importlib.import_module(name)


def oci_archive(path, *, arch="amd64", corrupt=False, multiple=False):
    layer = b"synthetic uncompressed layer"
    compressed = gzip.compress(layer, mtime=0)
    blobs = {}
    def blob(data):
        digest = hashlib.sha256(data).hexdigest()
        blobs[f"blobs/sha256/{digest}"] = data
        return {"digest": f"sha256:{digest}", "size": len(data)}
    config = blob(json.dumps({"os": "linux", "architecture": arch,
                              "rootfs": {"type": "layers", "diff_ids": [
                                  "sha256:" + hashlib.sha256(layer).hexdigest()]}}).encode())
    manifest = blob(json.dumps({"schemaVersion": 2, "config": config, "layers": [
        {**blob(compressed), "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip"}]}).encode())
    index = {"schemaVersion": 2, "manifests": [manifest] * (2 if multiple else 1)}
    blobs["index.json"] = json.dumps(index).encode()
    blobs["oci-layout"] = b'{"imageLayoutVersion":"1.0.0"}'
    if corrupt:
        blobs[next(k for k in blobs if k.endswith(config["digest"][7:]))] = b"corrupt"
    with tarfile.open(path, "w") as tar:
        for name, data in blobs.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return config["digest"]


def test_oci_verifies_platform_config_and_layers(tmp_path):
    build = product("ci.build_image")
    path = tmp_path / "image.tar"
    config = oci_archive(path)
    result = build.inspect_oci(path, "amd64")
    assert result["configDigest"] == config
    assert len(result["layerDigests"]) == 1
    assert len(result["diffIds"]) == 1
    with pytest.raises(ValueError, match="platform"):
        build.inspect_oci(path, "arm64")


@pytest.mark.parametrize("option,match", [("corrupt", "digest"), ("multiple", "one")])
def test_oci_rejects_corruption_and_indexes(tmp_path, option, match):
    build = product("ci.build_image")
    path = tmp_path / "bad.tar"
    oci_archive(path, **{option: True})
    with pytest.raises(ValueError, match=match):
        build.inspect_oci(path, "amd64")


def test_import_identity_rejects_changed_config_or_layers():
    build = product("ci.build_image")
    oci = {"configDigest": "sha256:one", "diffIds": ["sha256:layer"]}
    build.verify_import(oci, {"Id": "sha256:one", "Os": "linux",
                             "Architecture": "amd64", "RootFS": {"Layers": ["sha256:layer"]}}, "amd64")
    for image in [
        {"Id": "sha256:other", "Os": "linux", "Architecture": "amd64", "RootFS": {"Layers": ["sha256:layer"]}},
        {"Id": "sha256:one", "Os": "linux", "Architecture": "amd64", "RootFS": {"Layers": ["sha256:other"]}},
    ]:
        with pytest.raises(ValueError, match="identity"):
            build.verify_import(oci, image, "amd64")


def test_privileged_builder_requires_ephemeral_runner(monkeypatch):
    build = product("ci.build_image")
    for key in ["GITHUB_ACTIONS", "RUNNER_ENVIRONMENT"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="runner"):
        build.require_disposable_runner()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    with pytest.raises(ValueError, match="runner"):
        build.require_disposable_runner()
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    build.require_disposable_runner()


def test_gui_ocr_uses_words_with_coordinates():
    gui = product("ci.gui")
    text = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t20\t30\t40\t10\t95\tNew\n"
            "5\t1\t1\t1\t1\t2\t65\t30\t70\t10\t94\tProfile\n")
    words = gui.parse_tsv(text)
    assert gui.locate(words, "New Profile") == (77.5, 35.0)
    with pytest.raises(LookupError):
        gui.locate(words, "OSCAR")


def test_native_mounts_and_loopback_only():
    runtime = product("ci.runtime")
    cmd = runtime.container_command("image:tag", "oscar-ci-run-1", {
        "config": "volume-config", "data": "volume-data", "sdcard": "volume-sd",
    })
    joined = " ".join(cmd)
    assert "127.0.0.1::3000" in cmd
    assert "PUID=1234" in cmd and "PGID=2345" in cmd
    assert "no-new-privileges=true" in cmd
    assert "type=volume,src=volume-sd,dst=/config/SDCARD,readonly" in cmd
    for forbidden in ["--privileged", "docker.sock", "type=bind", "--gpus", "--network=host"]:
        assert forbidden not in joined


def test_receipt_cannot_claim_unexecuted_native_gate():
    runtime = product("ci.runtime")
    with pytest.raises(ValueError, match="checks"):
        runtime.validate_checks({"gui": True})


def test_runtime_profile_audit_requires_separate_state():
    runtime = product("ci.runtime")
    good = {"profiles": ["ci-synthetic"], "language": "en_US",
            "data": [{"path": "Documents/OSCAR20_Data/oscar.db", "uid": 1234, "gid": 2345, "integrity": "ok"}],
            "dataFiles": [{"path": "Documents/OSCAR20_Data/profile/app-created", "uid": 1234, "gid": 2345}],
            "qtConfig": [{"path": ".config/OSCAR/OSCAR 2.0.conf", "uid": 1234, "gid": 2345}],
            "outsideDatabases": []}
    runtime.validate_audit(good, "ci-synthetic")
    for key, value in [("profiles", []), ("language", ""), ("qtConfig", []),
                       ("outsideDatabases", ["/tmp/fallback.db"]),
                       ("dataFiles", [{"path": "Documents/OSCAR20_Data/profile/app-created", "uid": 0, "gid": 0}])]:
        bad = {**good, key: value}
        with pytest.raises(ValueError):
            runtime.validate_audit(bad, "ci-synthetic")


def test_source_bundle_from_fresh_checkout_without_artifacts(tmp_path):
    source = product("ci.source_bundle")
    project = tmp_path / "checkout"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    for name in source.SOURCE_FILES:
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    archive = tmp_path / "upstream.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("upstream/COPYING")
        text = b"Synthetic unit-test upstream COPYING, not a release source."
        info.size = len(text)
        tar.addfile(info, io.BytesIO(text))
    lock = json.loads((project / "versions.lock.json").read_text())
    lock["oscar"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    (project / "versions.lock.json").write_text(json.dumps(lock))
    destination = project / "artifacts/sources"
    command = ["python3", "-m", "ci.source_bundle", "--out-dir", str(destination),
               "--source-archive", str(archive)]
    manifest = source.build_bundle(destination, project=project, source_archive=archive, command=command)
    assert manifest["patches"] == []
    assert manifest["license"] == "Apache-2.0"
    assert manifest["oscar"]["binaries"] == lock["oscar"]["binaries"]
    assert manifest["binaryProvenance"] == {
        "packages": lock["oscar"]["binaries"],
        "sourceTag": "v2.1.1",
        "sourceCommit": lock["oscar"]["commit"],
        "correspondence": "version-aligned; not independently proven",
    }
    assert (destination / "OSCAR-COPYING").read_bytes() == text
    with tarfile.open(destination / "packaging.tar.gz") as tar:
        assert "docker-oscar/Dockerfile" in tar.getnames()
        assert tar.extractfile("docker-oscar/LICENSE").read() == (ROOT / "LICENSE").read_bytes()
        assert b"Version 2.0, January 2004" in tar.extractfile("docker-oscar/LICENSE").read()
        assert all(".git/" not in name and "WORKLOG" not in name for name in tar.getnames())
    assert json.loads((destination / "origin.json").read_text())["sourceArchive"]["sha256"] == lock["oscar"]["sha256"]
    assert manifest["exitCode"] == 0
    assert manifest["checks"] == {"sourceChecksum": True, "upstreamLicense": True,
                                  "patchList": True, "packagingInputs": True,
                                  "binaryProvenance": True}
    assert manifest["cwd"] == str(project.resolve())
    assert manifest["command"] == command


def test_runtime_tracks_created_container_when_start_fails(tmp_path, monkeypatch):
    runtime = product("ci.runtime")
    def engine(command, **kwargs):
        if command[:2] == ["docker", "start"]:
            raise subprocess.CalledProcessError(125, command)
        assert command[:2] == ["docker", "create"], "container must be registered between create and start"
    monkeypatch.setattr(runtime, "run", engine)
    resources = runtime.Resources("oscar-ci-synthetic", tmp_path)
    with pytest.raises(subprocess.CalledProcessError):
        resources.start("image:test", "desktop", {"config": "c", "data": "d", "sdcard": "s"})
    assert resources.containers == ["oscar-ci-synthetic-desktop"]


def test_negative_probe_never_accepts_infrastructure_or_cleanup_failure():
    runtime = product("ci.runtime")
    gui = product("ci.gui")
    assert runtime.failure_metadata(gui.GUIFailure("OSCAR absent"), negative=True)["expectedFailure"] is True
    for error in [RuntimeError("browser disconnected"), TimeoutError("service unavailable"),
                  subprocess.CalledProcessError(125, ["docker", "rm"])]:
        result = runtime.failure_metadata(error, negative=True)
        assert result["exitCode"] == 1
        assert result["expectedFailure"] is False
        assert result["failureKind"] != "missing-oscar-gui-profile"
