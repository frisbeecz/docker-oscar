"""Publish tested CI artifacts, then verify distribution once. Apache-2.0."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import urlopen

import yaml

from ci import (ROOT, CLEAN_DIFF_SHA256, load_lock, output, run, sha256_file,
                state_identity, write_json)
from ci.build_image import inspect_oci
from ci.chart import matrix as chart_matrix
from ci.chart_registry import publish_chart
from ci.dockerhub import update_metadata as update_dockerhub_metadata
from ci.runtime import REQUIRED_CHECKS, TEST_SCOPE, validate_checks, validate_process
from ci.source_bundle import source_provenance
from ci.security import ACCEPTED_HIGH, validate_report

REPO = "frisbeecz/docker-oscar"
REGISTRY = "ghcr.io/frisbeecz"
IMAGE = REGISTRY + "/docker-oscar"
DOCKERHUB_IMAGE = "docker.io/frisbeecz24/docker-oscar"
LEGACY_DOCKERHUB_IMAGE = "docker.io/frisbeecz24/frisbeecz"
DIGEST = r"sha256:[a-f0-9]{64}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"missing or unsafe evidence: {path}")
    return json.loads(path.read_text())


def checked_file(path, digest):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"missing or unsafe archive: {path}")
    require(re.fullmatch(r"[a-f0-9]{64}", digest or "") and sha256_file(path) == digest,
            f"archive checksum mismatch: {path}")
    return path


def check_receipt(data, commit, checks=(), *, arch=None, negative=False):
    require(data.get("schemaVersion") == 1 and data.get("gitCommit") == commit
            and data.get("dirtyDiffSha256") == CLEAN_DIFF_SHA256, "receipt source identity mismatch")
    require(isinstance(data.get("command"), list) and bool(data["command"]) and data.get("cwd"),
            "receipt command/cwd missing")
    require(type(data.get("exitCode")) is int and data["exitCode"] == (1 if negative else 0),
            "failed receipt")
    values = data.get("checks", {})
    require(all((type(values.get(c)) is int and values[c] > 0) if c == "mediaFrames"
                else values.get(c) is True for c in checks), "receipt checks incomplete or incorrectly typed")
    if arch:
        platform = data.get("platform", {})
        machines = {"amd64": {"x86_64", "amd64"}, "arm64": {"arm64", "aarch64"}}
        require(data.get("arch") == arch and platform.get("system") == "Linux"
                and platform.get("machine") in machines[arch], "receipt native platform mismatch")
    if negative:
        require(data.get("expectedFailure") is True and data.get("probe") == "negative-base"
                and data.get("failureKind") == "missing-oscar-gui-profile"
                and not data.get("cleanupError"), "negative probe was infrastructure failure, not missing GUI")


def validate_tag(tag, chart_version):
    require(bool(re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", tag)),
            "release tag must be stable project SemVer")
    require(tag == "v" + chart_version, "release tag/chart version mismatch")
    return tag


def verify(artifacts, commit, *, project=ROOT):
    """Read-only verification; incomplete local evidence is deliberately rejected."""
    project, artifacts = Path(project), Path(artifacts)
    require(not artifacts.is_symlink() and not any(p.is_symlink() for p in artifacts.rglob("*")),
            "symlink in artifact evidence")
    require(bool(re.fullmatch(r"[a-f0-9]{40}", commit)), "full commit SHA required")
    identity = state_identity(project)
    require(identity == {"gitCommit": commit, "dirtyDiffSha256": CLEAN_DIFF_SHA256},
            "release requires clean exact HEAD commit")
    locked = load_lock(project=project)
    require(locked["oscar"]["version"] == "2.1.1"
            and locked["oscar"]["commit"] == "4f14624616d62c6986788417bc5c519c807a7ade",
            "stable OSCAR source required; alpha forbidden")
    chart = yaml.safe_load((project / "charts/oscar/Chart.yaml").read_text())
    require(str(chart["appVersion"]) == "2.1.1", "chart appVersion mismatch")
    static = read_json(artifacts / "static/check.json")
    check_receipt(static, commit, ["actionlint", "yamllint", "hadolint", "shellcheck", "pythonLint", "pytest"])
    platforms = {}
    for arch in ("amd64", "arm64"):
        folder = artifacts / "native" / arch
        build = read_json(folder / f"build-{arch}.json")
        check_receipt(build, commit, ["nativeHost", "nativeDaemon", "singleManifest", "configAndLayerIdentity"], arch=arch)
        require(build.get("sources") == locked, "build sources differ from stable exact lock")
        archive = checked_file(folder / f"image-{arch}.oci.tar", build.get("archiveSha256"))
        oci = inspect_oci(archive, arch)
        require(all(build.get(k) == v for k, v in oci.items()), "OCI/build identity mismatch")
        runtime = read_json(folder / f"runtime-{arch}.json")
        check_receipt(runtime, commit, REQUIRED_CHECKS, arch=arch)
        require(runtime.get("testScope") == TEST_SCOPE, "current container functional scope required")
        validate_checks(runtime.get("checks"))
        validate_process(runtime.get("process"))
        duration = runtime.get("durationSeconds")
        require(type(duration) in (int, float) and math.isfinite(duration) and duration >= 10,
                "startup smoke requires at least ten observed monotonic seconds")
        require("cleanupError" not in runtime and "error" not in runtime,
                "startup smoke failed or cleanup incomplete")
        require(runtime.get("image") == build.get("image") == f"oscar-under-test:{arch}",
                "runtime tested image reference mismatch")
        require(all(runtime.get(k) == build[k] for k in ("manifestDigest", "configDigest", "layerDigests")),
                "runtime tested image identity mismatch")
        require(runtime.get("archiveSha256") == build["archiveSha256"], "runtime archive identity mismatch")
        security = read_json(folder / f"security-{arch}.json")
        check_receipt(security, commit, ["noCritical", "acceptedHigh"], arch=arch)
        require(all(security.get(k) == build[k] for k in (
            "image", "manifestDigest", "configDigest", "archiveSha256")),
            "security tested image identity mismatch")
        require(security.get("scannerVersion") == load_lock(
            "ci/tools.lock.json", project=project)["trivy"]["version"], "security scanner version mismatch")
        report = read_json(checked_file(folder / "security-report.json", security.get("reportSha256")))
        require(report.get("Metadata", {}).get("ImageID") == build["configDigest"]
                and report["Metadata"].get("ImageConfig", {}).get("architecture") == arch
                and report["Metadata"].get("ImageConfig", {}).get("os") == "linux",
                "security report image mismatch")
        validate_report(report, ACCEPTED_HIGH)
        platforms[arch] = {**oci, "archiveSha256": build["archiveSha256"],
                           "archive": str(archive.resolve())}
    packages = {}
    for version in ("3.19.0", "4.3.2"):
        folder = artifacts / "chart" / f"helm-{version}"
        data = read_json(folder / "chart.json")
        check_receipt(data, commit, ["pytest", "lint", "render", "strictSchemas", "routeMatrix"])
        require(re.fullmatch("v" + re.escape(version) + r"(?:\+.*)?", data.get("helmVersion", "")),
                "Helm receipt version mismatch")
        matrix = data.get("matrix", {})
        require(set(matrix) == set(chart_matrix()) and all(v.get("valid", 0) > 0 and
                all(v.get(k) == 0 for k in ("invalid", "errors", "skipped")) for v in matrix.values()),
                "chart matrix incomplete/failed/skipped")
        package = read_json(folder / "package.json")
        check_receipt(package, commit, ["packagedChartTested"])
        require(package.get("chartVersion") == chart["version"], "packaged chart version mismatch")
        file = checked_file(folder / f"oscar-{chart['version']}.tgz", package.get("archiveSha256"))
        packages[version] = {"path": str(file.resolve()), "sha256": package["archiveSha256"]}
    source = artifacts / "sources"
    expected = run(["git", "archive", "--format=tar.gz", commit], cwd=project, capture_output=True).stdout
    expected_sha = hashlib.sha256(expected).hexdigest()
    verify_sources(source, commit, locked, expected_sha)
    return {"schemaVersion": 1, "gitCommit": commit, "testScope": TEST_SCOPE,
            "oscarVersion": "2.1.1", "imageTag": "2.1.1-r8",
            "chartVersion": chart["version"], "platforms": platforms, "charts": packages,
             "sources": {p.name: sha256_file(p) for p in sorted(source.iterdir()) if p.is_file()}}


def verify_sources(source, commit, locked, expected_sha):
    origin = read_json(source / "origin.json")
    check_receipt(origin, commit, ["sourceChecksum", "upstreamLicense", "patchList", "packagingInputs"])
    require(origin.get("oscar") == locked["oscar"], "source origin differs from source lock")
    if "build" in locked["oscar"]:
        require(origin.get("sourceProvenance") == source_provenance(locked)
                and origin.get("checks", {}).get("sourceProvenance") is True
                and "binaryProvenance" not in origin,
                "source provenance missing or inconsistent")
        require(origin.get("base") == locked["base"], "source base differs from exact lock")
    for key in ("sourceArchive", "packaging"):
        entry = origin[key]
        require(Path(entry["path"]).name == entry["path"], "unsafe source archive path")
        checked_file(source / entry["path"], entry["sha256"])
    require(origin["sourceArchive"]["sha256"] == locked["oscar"]["sha256"], "upstream source checksum mismatch")
    project_receipt = read_json(source / "project.json")
    check_receipt(project_receipt, commit, ["gitArchive"])
    checked_file(source / "project-source.tar.gz", project_receipt.get("archiveSha256"))
    require(expected_sha == project_receipt["archiveSha256"],
            "project source archive is not exact git commit")


def mutate(command, **kwargs):
    """Only external-write boundary; argv arrays, never shell interpolation."""
    return run(command, **kwargs)


def verify_source_assets(manifest, tag):
    """Anonymous HTTPS, without GH_TOKEN: sources must be public before binaries."""
    for name, digest in manifest["sources"].items():
        require(Path(name).name == name, "unsafe source asset")
        url = f"https://github.com/{REPO}/releases/download/{tag}/{quote(name, safe='')}"
        with urlopen(url, timeout=120) as response:
            require(hashlib.file_digest(response, "sha256").hexdigest() == digest,
                    "public source asset checksum mismatch")


def publish(artifacts, commit, registry, *, project=ROOT):
    manifest = verify(artifacts, commit, project=project)  # Before ANY mutation/login.
    require(registry == REGISTRY, "only approved registry permitted")
    tag = validate_tag(os.environ.get("GITHUB_REF_NAME", ""), manifest["chartVersion"])
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(run_id.isascii() and run_id.isdecimal() and int(run_id) > 0
            and attempt.isascii() and attempt.isdecimal() and int(attempt) > 0, "invalid run/attempt")
    require(os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF_TYPE") == "tag"
            and os.environ.get("GITHUB_REPOSITORY") == REPO
            and os.environ.get("GITHUB_SHA") == commit, "publish requires exact trusted tag push")
    # GitHub's needs dependency gates CI success; no second job-result API audit.
    manifest.update(runId=int(run_id), runAttempt=int(attempt),
                    runUrl=f"https://github.com/{REPO}/actions/runs/{run_id}", jobUrls={})
    token = os.environ.get("GH_TOKEN")
    require(bool(token), "job-scoped GH_TOKEN required")
    dockerhub_token = os.environ.get("DOCKERHUB_TOKEN")
    require(bool(dockerhub_token and dockerhub_token.strip()), "DOCKERHUB_TOKEN required")
    username = os.environ.get("GITHUB_ACTOR", "")
    require(bool(re.fullmatch(r"[A-Za-z0-9-]+(?:\[bot\])?", username)), "invalid publishing actor")
    tools = load_lock("ci/tools.lock.json", project=project)
    require(output(["skopeo", "--version"]).split()[-1] == tools["skopeo"]["version"], "unsupported skopeo")
    require(tools["buildx"]["version"] in output(["docker", "buildx", "version"]), "unsupported buildx")
    source = Path(artifacts) / "sources"
    # gh --verify-tag refuses a missing remote tag. Never overwrite an existing release.
    mutate(["gh", "release", "create", tag, "--repo", REPO, "--verify-tag", "--target", commit,
            "--prerelease", "--title", tag, "--notes", "Sources first; binary verification in progress.",
            *[str(p) for p in sorted(source.iterdir()) if p.is_file()]])
    verify_source_assets(manifest, tag)
    with tempfile.TemporaryDirectory(prefix="release-auth-", dir=Path(artifacts)) as temp:
        temp = Path(temp)
        auth = temp / "skopeo.json"
        docker = temp / "docker"
        docker.mkdir(mode=0o700)
        write_json(docker / "config.json", {
            "cliPluginsExtraDirs": [str(Path(project) / ".venv/docker/cli-plugins")]})
        (docker / "config.json").chmod(0o600)
        require(tools["buildx"]["version"] in output(["docker", "--config", docker, "buildx", "version"]),
                "isolated publication config lost the pinned Buildx plugin")
        mutate(["skopeo", "login", "--authfile", auth, "--username", username,
                "--password-stdin", "ghcr.io"], input=token, text=True)
        mutate(["skopeo", "login", "--authfile", auth, "--username", "frisbeecz24",
                "--password-stdin", "docker.io"], input=dockerhub_token, text=True)
        mutate(["docker", "--config", docker, "login", "ghcr.io", "--username", username,
                "--password-stdin"], input=token, text=True)
        for arch, platform in manifest["platforms"].items():
            ref = f"{IMAGE}:{manifest['imageTag']}-{arch}"
            mutate(["skopeo", "copy", "--preserve-digests", "--authfile", auth,
                    "oci-archive:" + platform["archive"], "docker://" + ref])
        refs = [f"{IMAGE}@{v['manifestDigest']}" for v in manifest["platforms"].values()]
        mutate(["docker", "--config", docker, "buildx", "imagetools", "create",
                "--tag", f"{IMAGE}:{manifest['imageTag']}", *refs])
        # Registry raw bytes, including final newline, not stripped CLI output.
        raw = run(["skopeo", "inspect", "--raw", "--authfile", auth,
                   "docker://" + IMAGE + ":" + manifest["imageTag"]], capture_output=True).stdout
        manifest["imageIndexDigest"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        update_dockerhub_metadata(token=dockerhub_token, project=project)
        mutate(["skopeo", "copy", "--all", "--preserve-digests", "--authfile", auth,
                "docker://" + IMAGE + "@" + manifest["imageIndexDigest"],
                "docker://" + DOCKERHUB_IMAGE + ":" + manifest["imageTag"]])
        manifest["dockerHubRepository"] = DOCKERHUB_IMAGE
        chart = manifest["charts"]["4.3.2"]
        manifest["chartDigest"] = publish_chart(
            chart["path"], sha256=chart["sha256"], version=manifest["chartVersion"],
            username=username, token=token)
        manifest["chartReference"] = REGISTRY + "/charts/oscar:" + manifest["chartVersion"]
    manifest.update(imageRepository=IMAGE, releaseTag=tag, repository=REPO,
                    releaseUrl=f"https://github.com/{REPO}/releases/tag/{tag}")
    target = Path(artifacts) / "release-manifest.json"
    write_json(target, manifest)
    mutate(["gh", "release", "upload", tag, str(target), "--repo", REPO])
    verify_published(target)
    mutate(["gh", "release", "edit", tag, "--repo", REPO, "--prerelease=false",
            "--notes", "Source-built Alpine OSCAR; native AMD64/ARM64 container-functional-v1, "
            "image-bound Trivy reports, Helm checks and source provenance. "
            "GUI, CPAP import, data migration and Kubernetes deployment are not proven by these checks. "
            "See release-manifest.json, acceptance documentation and NOTICE.md."])
    return manifest


def verify_published(path):
    manifest = read_json(path)
    require(manifest.get("testScope") in {TEST_SCOPE, "startup-smoke-v1"},
            "supported publication scope required")
    require(manifest.get("imageRepository") == IMAGE and manifest.get("repository") == REPO,
            "unapproved publication repository")
    validate_tag(manifest["releaseTag"], manifest["chartVersion"])
    require(manifest.get("chartReference") == REGISTRY + "/charts/oscar:" + manifest["chartVersion"],
            "unapproved chart reference")
    mirror = manifest.get("dockerHubRepository")
    require("dockerHubRepository" not in manifest or mirror in {DOCKERHUB_IMAGE, LEGACY_DOCKERHUB_IMAGE},
            "unapproved Docker Hub repository")
    for digest in [manifest.get("imageIndexDigest", ""), manifest.get("chartDigest", ""),
                   *(p.get("manifestDigest", "") for p in manifest["platforms"].values())]:
        require(bool(re.fullmatch(DIGEST, digest)), "invalid publication digest")
    tag_raw = run(["skopeo", "inspect", "--raw", "docker://" + IMAGE + ":" + manifest["imageTag"]],
                  capture_output=True).stdout
    require("sha256:" + hashlib.sha256(tag_raw).hexdigest() == manifest["imageIndexDigest"],
            "published image tag points to a different index")
    if mirror:
        mirror_raw = run(["skopeo", "inspect", "--raw", "docker://" + mirror + ":" + manifest["imageTag"]],
                         capture_output=True).stdout
        require("sha256:" + hashlib.sha256(mirror_raw).hexdigest() == manifest["imageIndexDigest"],
                "Docker Hub image tag points to a different index")
    index = json.loads(tag_raw)
    require(len(index["manifests"]) == 2 and all(d["platform"]["os"] == "linux"
            for d in index["manifests"]), "index must contain exactly two Linux platform manifests")
    actual = {d["platform"]["architecture"]: d["digest"] for d in index["manifests"]}
    require(actual == {a: p["manifestDigest"] for a, p in manifest["platforms"].items()},
            "published index platform mismatch")
    for arch, platform in manifest["platforms"].items():
        data = json.loads(output(["skopeo", "inspect", "--raw", "docker://" + IMAGE + "@" + platform["manifestDigest"]]))
        require(data["config"]["digest"] == platform["configDigest"]
                and [v["digest"] for v in data["layers"]] == platform["layerDigests"], "published config/layers changed")
    with tempfile.TemporaryDirectory(prefix="published-", dir=Path(path).parent) as temp:
        mutate(["helm", "pull", "oci://" + REGISTRY + "/charts/oscar",
                "--version", manifest["chartVersion"], "--destination", temp])
        checked_file(Path(temp) / f"oscar-{manifest['chartVersion']}.tgz", manifest["charts"]["4.3.2"]["sha256"])
    chart_raw = run(["skopeo", "inspect", "--raw", "docker://" + manifest["chartReference"]], capture_output=True).stdout
    require("sha256:" + hashlib.sha256(chart_raw).hexdigest() == manifest["chartDigest"], "published chart digest changed")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--artifacts", required=True, type=Path)
        command.add_argument("--commit", required=True)
        if name == "publish":
            command.add_argument("--registry", required=True)
    command = commands.add_parser("verify-published")
    command.add_argument("--release-manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify":
        print(json.dumps(verify(args.artifacts, args.commit), indent=2))
    elif args.command == "publish":
        publish(args.artifacts, args.commit, args.registry)
    else:
        verify_published(args.release_manifest)


if __name__ == "__main__":
    main()
