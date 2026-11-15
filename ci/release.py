"""Fail-closed same-run release of tested bytes; no rebuilds. Apache-2.0."""
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
from ci.runtime import REQUIRED_CHECKS, TEST_SCOPE, validate_checks, validate_process

REPO = "frisbeecz/docker-oscar"
REGISTRY = "ghcr.io/frisbeecz"
IMAGE = REGISTRY + "/docker-oscar"
GATES = {"static", "helm-3.19.0", "helm-4.3.2", "native-amd64", "native-arm64"}
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


def verify_jobs(run_data, jobs, commit):
    require(run_data.get("head_sha") == commit
            and run_data.get("repository", {}).get("full_name") == REPO
            and run_data.get("event") == "push", "GitHub run identity/event mismatch")
    run_id, attempt = run_data.get("id"), run_data.get("run_attempt")
    require(type(run_id) is int and type(attempt) is int, "GitHub run id/attempt missing")
    url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    require(run_data.get("html_url") == url, "GitHub run URL mismatch")
    selected = {}
    for job in jobs:
        name = job.get("name", "").split(" / ")[-1]
        if name in GATES:
            require(name not in selected, "duplicate gate jobs")
            require(job.get("run_id") == run_id and job.get("run_attempt") == attempt
                    and job.get("head_sha") == commit and job.get("status") == "completed"
                    and job.get("conclusion") == "success", f"GitHub gate failed/skipped/mismatched: {name}")
            require(job.get("html_url", "").startswith(url + "/job/"), "job URL mismatch")
            selected[name] = job["html_url"]
    require(set(selected) == GATES, "missing mandatory GitHub gate jobs")
    return selected


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
        require(runtime.get("testScope") == TEST_SCOPE, "current startup smoke scope required")
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
    for directory in (source, *(artifacts / "native" / a / "sources" for a in ("amd64", "arm64"))):
        verify_sources(directory, commit, locked, expected_sha)
    run_data = read_json(artifacts / "evidence/run.json")
    jobs = verify_jobs(run_data, read_json(artifacts / "evidence/jobs.json"), commit)
    return {"schemaVersion": 1, "gitCommit": commit, "testScope": TEST_SCOPE,
            "oscarVersion": "2.1.1", "imageTag": "2.1.1-r1",
            "chartVersion": chart["version"], "platforms": platforms, "charts": packages,
            "sources": {p.name: sha256_file(p) for p in sorted(source.iterdir()) if p.is_file()},
            "runUrl": run_data["html_url"], "runId": run_data["id"], "runAttempt": run_data["run_attempt"],
            "jobUrls": jobs}


def verify_sources(source, commit, locked, expected_sha):
    origin = read_json(source / "origin.json")
    check_receipt(origin, commit, ["sourceChecksum", "upstreamLicense", "patchList", "packagingInputs"])
    require(origin.get("oscar") == locked["oscar"], "source origin differs from source lock")
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


def github_evidence(directory):
    """Read only this run and attempt; no arbitrary run/artifact selection."""
    require(os.environ.get("GITHUB_REPOSITORY") == REPO, "unexpected GitHub repository")
    run_id, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    require(run_id.isdecimal() and attempt.isdecimal(), "invalid run/attempt")
    data = json.loads(output(["gh", "api", f"repos/{REPO}/actions/runs/{run_id}"]))
    pages = json.loads(output(["gh", "api", "--paginate", "--slurp",
                             f"repos/{REPO}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"]))
    jobs = [j for page in pages for j in page["jobs"]]
    verify_jobs(data, jobs, os.environ["GITHUB_SHA"])
    write_json(Path(directory) / "run.json", data)
    write_json(Path(directory) / "jobs.json", jobs)


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
    require(os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF_TYPE") == "tag"
            and os.environ.get("GITHUB_REPOSITORY") == REPO
            and os.environ.get("GITHUB_SHA") == commit
            and os.environ.get("GITHUB_RUN_ID") == str(manifest["runId"])
            and os.environ.get("GITHUB_RUN_ATTEMPT") == str(manifest["runAttempt"]),
            "publish requires exact tag push in the verified run/attempt")
    # Independently re-read server state before first external write.
    with tempfile.TemporaryDirectory(prefix="release-verify-", dir=Path(artifacts)) as temp:
        github_evidence(temp)
        require(read_json(Path(temp) / "run.json")["head_branch"] == tag, "tag/run mismatch")
        require(verify_jobs(read_json(Path(temp) / "run.json"), read_json(Path(temp) / "jobs.json"), commit)
                == manifest["jobUrls"], "GitHub job evidence changed")
    token = os.environ.get("GH_TOKEN")
    require(bool(token), "job-scoped GH_TOKEN required")
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
        helm = temp / "helm.json"
        mutate(["skopeo", "login", "--authfile", auth, "--username", username,
                "--password-stdin", "ghcr.io"], input=token, text=True)
        mutate(["docker", "--config", docker, "login", "ghcr.io", "--username", username,
                "--password-stdin"], input=token, text=True)
        mutate(["helm", "registry", "login", "ghcr.io", "--username", username, "--password-stdin",
                "--registry-config", helm], input=token, text=True)
        for arch, platform in manifest["platforms"].items():
            ref = f"{IMAGE}:{manifest['imageTag']}-{arch}"
            mutate(["skopeo", "copy", "--preserve-digests", "--authfile", auth,
                    "oci-archive:" + platform["archive"], "docker://" + ref])
            actual = json.loads(output(["skopeo", "inspect", "--authfile", auth, "docker://" + ref]))
            require(actual["Digest"] == platform["manifestDigest"], "registry platform digest changed")
        refs = [f"{IMAGE}@{v['manifestDigest']}" for v in manifest["platforms"].values()]
        mutate(["docker", "--config", docker, "buildx", "imagetools", "create",
                "--tag", f"{IMAGE}:{manifest['imageTag']}", *refs])
        # Registry raw bytes, including final newline, not stripped CLI output.
        raw = run(["skopeo", "inspect", "--raw", "--authfile", auth,
                   "docker://" + IMAGE + ":" + manifest["imageTag"]], capture_output=True).stdout
        manifest["imageIndexDigest"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        chart = manifest["charts"]["4.3.2"]
        mutate(["helm", "push", chart["path"], "oci://" + REGISTRY + "/charts", "--registry-config", helm])
        manifest["chartReference"] = REGISTRY + "/charts/oscar:" + manifest["chartVersion"]
        chart_manifest = run(["skopeo", "inspect", "--raw", "--authfile", auth,
                              "docker://" + manifest["chartReference"]], capture_output=True).stdout
        manifest["chartDigest"] = "sha256:" + hashlib.sha256(chart_manifest).hexdigest()
    manifest.update(imageRepository=IMAGE, releaseTag=tag, repository=REPO,
                    releaseUrl=f"https://github.com/{REPO}/releases/tag/{tag}")
    target = Path(artifacts) / "release-manifest.json"
    write_json(target, manifest)
    mutate(["gh", "release", "upload", tag, str(target), "--repo", REPO])
    verify_published(target)
    mutate(["gh", "release", "edit", tag, "--repo", REPO, "--prerelease=false",
            "--notes", "Native AMD64/ARM64 startup-smoke-v1, Helm render/schema checks and source provenance. "
            "GUI, import, persistence and Kubernetes deployment are unverified. See release-manifest.json and NOTICE.md."])
    return manifest


def verify_published(path):
    manifest = read_json(path)
    require(manifest.get("testScope") == TEST_SCOPE, "current startup smoke publication scope required")
    require(manifest.get("imageRepository") == IMAGE and manifest.get("repository") == REPO,
            "unapproved publication repository")
    validate_tag(manifest["releaseTag"], manifest["chartVersion"])
    require(manifest.get("chartReference") == REGISTRY + "/charts/oscar:" + manifest["chartVersion"],
            "unapproved chart reference")
    for digest in [manifest.get("imageIndexDigest", ""), manifest.get("chartDigest", ""),
                   *(p.get("manifestDigest", "") for p in manifest["platforms"].values())]:
        require(bool(re.fullmatch(DIGEST, digest)), "invalid publication digest")
    tag_raw = run(["skopeo", "inspect", "--raw", "docker://" + IMAGE + ":" + manifest["imageTag"]],
                  capture_output=True).stdout
    require("sha256:" + hashlib.sha256(tag_raw).hexdigest() == manifest["imageIndexDigest"],
            "published image tag points to a different index")
    raw = run(["skopeo", "inspect", "--raw", "docker://" + IMAGE + "@" + manifest["imageIndexDigest"]],
              capture_output=True).stdout
    require("sha256:" + hashlib.sha256(raw).hexdigest() == manifest["imageIndexDigest"], "index digest mismatch")
    index = json.loads(raw)
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
        mutate(["gh", "release", "download", manifest["releaseTag"], "--repo", REPO,
                "--dir", temp, "--pattern", "*"])
        for name, digest in manifest["sources"].items():
            require(Path(name).name == name, "unsafe source asset name")
            checked_file(Path(temp) / name, digest)
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
    command = commands.add_parser("evidence")
    command.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify":
        print(json.dumps(verify(args.artifacts, args.commit), indent=2))
    elif args.command == "publish":
        publish(args.artifacts, args.commit, args.registry)
    elif args.command == "evidence":
        github_evidence(args.out_dir)
    else:
        verify_published(args.release_manifest)


if __name__ == "__main__":
    main()
