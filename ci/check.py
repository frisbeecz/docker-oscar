"""Common real-tool checks and disposable-runner preparation. Apache-2.0."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit

import yaml

from ci import ROOT, load_lock, output, receipt, run, sha256_file, write_json
from ci.build_image import require_disposable_runner, require_native
from ci.chart import API, CHART, matrix, prepare_schemas, validate_documents, verified_input

BIN = ROOT / ".venv/tools/bin"
CACHE = ROOT / "artifacts/ci01/upstream"


def discover(project=ROOT):
    project = Path(project)
    paths = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=project, capture_output=True).stdout.split(b"\0")
    groups = {"python": [], "yaml": [], "docker": [], "shell": []}
    for raw in sorted(set(paths) - {b""}):
        name = os.fsdecode(raw)
        file = project / name
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"unsafe lint input: {name}")
        if file.suffix == ".py":
            groups["python"].append(name)
        if file.suffix in (".yaml", ".yml") and not name.startswith("charts/oscar/templates/"):
            groups["yaml"].append(name)  # Go templates are validated after real Helm rendering.
        if file.name == "Dockerfile" or file.name.startswith("Dockerfile."):
            groups["docker"].append(name)
        with file.open("rb") as stream:
            first = stream.readline(256)
        if (name == "root/defaults/autostart_wayland" or file.suffix in (".sh", ".bash")
                or re.match(rb"#![^\n]*(?:/| )(?:ba|da|a|k|z)?sh(?:\s|$)", first)):
            groups["shell"].append(name)
    if not all(groups.values()):
        raise ValueError(f"empty lint input class: {groups}")
    return groups


def tool(name, *, directory=BIN, search_path=None):
    local = Path(directory) / name
    if local.is_file() and os.access(local, os.X_OK):
        return str(local.resolve())
    found = shutil.which(name, path=search_path)
    if not found:
        raise FileNotFoundError(f"required tool missing: {name}; run ci.check --install-tools in a project venv")
    return found


def install_binary(archive, basename, target):
    """Select one regular binary without extracting archive paths or links."""
    target = Path(target)
    if str(archive).endswith((".tar.gz", ".tgz", ".tar.xz")):
        with tarfile.open(archive, "r:*") as tar:
            members = [m for m in tar.getmembers() if Path(m.name).name == basename]
            if len(members) != 1 or not members[0].isfile() or members[0].size > 512 * 1024 * 1024:
                raise ValueError("unsafe or ambiguous tool archive")
            data = tar.extractfile(members[0]).read()
    else:
        data = Path(archive).read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o755)


def download(pin):
    return verified_input(CACHE, Path(urlsplit(pin["url"]).path).name, pin)


def install_tools():
    if sys.prefix == sys.base_prefix or not Path(sys.prefix).resolve().is_relative_to(ROOT):
        raise ValueError("tool installation requires a project-local virtual environment")
    tools = load_lock("ci/tools.lock.json")
    arch = {"x86_64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine())
    system = platform.system().lower()
    key = f"{system}-{arch}"
    for name in ("actionlint", "hadolint", "shellcheck", "ruff"):
        pin = tools["releaseTools"][name]["artifacts"][key]
        install_binary(download(pin), name, BIN / name)
    for name in ("pathspec", "yamllint"):
        wheel = download(tools["releaseTools"][name]["wheel"])
        run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
    for version in tools["helm"]:
        pin = (tools["helm"][version]["artifacts"][arch] if system == "linux"
               else tools["releaseTools"]["helm-" + version]["artifacts"][key])
        install_binary(download(pin), "helm", BIN / ("helm-" + version))
    shutil.copyfile(BIN / "helm-4.3.2", BIN / "helm")
    (BIN / "helm").chmod(0o755)
    if system == "linux":
        for name in ("kubeconform", "buildx"):
            pin = tools[name]["artifacts"][arch]
            target = (ROOT / ".venv/docker/cli-plugins/docker-buildx" if name == "buildx" else BIN / name)
            install_binary(download(pin), name, target)


def build_skopeo(source, target, version):
    # An upstream tarball has no VCS identity. Without this flag, Go stamps our
    # enclosing packaging checkout instead and Skopeo appends its unrelated SHA.
    run(["make", "bin/skopeo", "BUILDTAGS=containers_image_openpgp",
         "GOFLAGS=-buildvcs=false"], cwd=source)
    actual = output([str(Path(source).resolve() / "bin/skopeo"), "--version"])
    print(f"Built Skopeo: {actual}", flush=True)
    if actual != f"skopeo version {version}":
        raise ValueError(f"unsupported skopeo version: {actual!r}; expected {version}")
    shutil.copyfile(Path(source) / "bin/skopeo", target)
    Path(target).chmod(0o755)


def native_tools():
    require_disposable_runner()
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine())
    require_native(arch)
    tools = load_lock("ci/tools.lock.json")
    build = ROOT / ".venv/build"
    build.mkdir(parents=True, exist_ok=True)
    # Host dependencies only on the explicitly approved disposable CI runner.
    run(["sudo", "apt-get", "update"])
    run(["sudo", "apt-get", "install", "-y", "--no-install-recommends", "build-essential",
         "pkg-config",
         "libarchive-dev", "libcurl4-openssl-dev", "libgpgme-dev", "libassuan-dev",
         "libbtrfs-dev", "libdevmapper-dev", "libseccomp-dev"])
    archive = download(tools["skopeo"]["source"])
    destination = build / "skopeo"
    if destination.exists():
        raise FileExistsError(f"refusing to reuse partial native build: {destination}")
    destination.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(destination, filter="data")
    folders = [p for p in destination.iterdir() if p.is_dir()]
    if len(folders) != 1:
        raise ValueError("unexpected native source layout")
    build_skopeo(folders[0], BIN / "skopeo", tools["skopeo"]["version"])


def static_checks(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "check.json"
    if target.exists():
        raise FileExistsError("refusing to overwrite static receipt")
    result = receipt()
    try:
        files = discover()
        result["inputs"] = files
        pins = load_lock("ci/tools.lock.json")["releaseTools"]
        for name, flag in (("actionlint", "-version"), ("hadolint", "--version"),
                           ("shellcheck", "--version"), ("ruff", "--version")):
            if pins[name]["version"] not in output([tool(name), flag]):
                raise ValueError(f"unsupported {name} version")
        if importlib.metadata.version("yamllint") != pins["yamllint"]["version"]:
            raise ValueError("unsupported yamllint version")
        commands = {
            "actionlint": [tool("actionlint"), "-color", *[f for f in files["yaml"] if f.startswith(".github/workflows/")]],
            "yamllint": [sys.executable, "-m", "yamllint", "-d",
                         "{extends: relaxed, rules: {line-length: disable, truthy: disable}}", *files["yaml"]],
            # Warnings are retained in logs; errors block. OS package warning
            # DL3018 is not represented as a reproducibility claim.
            "hadolint": [tool("hadolint"), "--failure-threshold", "error", *files["docker"]],
            "shellcheck": [tool("shellcheck"), "--shell=sh", *files["shell"]],
            "pythonLint": [tool("ruff"), "check", "--select", "E9,F63,F7,F82", *files["python"]],
            "pytest": [sys.executable, "-m", "pytest", "-q"],
        }
        for check, command in commands.items():
            with (directory / f"{check}.log").open("w") as log:
                run(command, stdout=log, stderr=subprocess.STDOUT)
            result["checks"][check] = True
        result["exitCode"] = 0
    except Exception as error:
        result.update(exitCode=1, error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(target, result)


def chart_checks(version, directory):
    directory = Path(directory)
    helm = tool("helm-" + version)
    run([sys.executable, "-m", "ci.chart", "--helm", helm, "--out-dir", directory])
    # Package once, then lint/render/strict validate the exact tarball to publish.
    # No default/tag rewriting after this point.
    result = receipt()
    run([helm, "package", CHART, "--destination", directory])
    chart = yaml.safe_load((CHART / "Chart.yaml").read_text())
    archive = directory / f"oscar-{chart['version']}.tgz"
    schemas = prepare_schemas(ROOT / "artifacts/chart/schemas")
    for name, values in matrix().items():
        file = directory / f"{name}.values.yaml"
        run([helm, "lint", archive, "--strict", "-f", file])
        caps = ["--api-versions", API] if values.get("gateway", {}).get("enabled") else []
        manifest = output([helm, "template", "demo", archive, "-f", file, *caps])
        validate_documents([d for d in yaml.safe_load_all(manifest) if d], schemas, tool("kubeconform"))
    # Negative schema/capability cases against the packaged archive itself.
    for args in (["--set", "replicaCount=2"], ["--set", "gateway.enabled=true"]):
        completed = subprocess.run([helm, "template", "negative", archive, *args], cwd=ROOT, capture_output=True)
        if completed.returncode == 0:
            raise ValueError("packaged chart accepted invalid values/missing Gateway API")
    result.update(exitCode=0, chartVersion=chart["version"], archiveSha256=sha256_file(archive),
                  checks={"packagedChartTested": True})
    write_json(directory / "package.json", result)


def source_checks(directory):
    directory = Path(directory)
    from ci.source_bundle import build_bundle
    pin = load_lock()["oscar"]
    cached = ROOT / "artifacts/image01/upstream/oscar.tar.gz"
    build_bundle(directory, source_archive=cached if cached.exists() else None)
    result = receipt()
    archive = directory / "project-source.tar.gz"
    with archive.open("wb") as file:
        run(["git", "archive", "--format=tar.gz", result["gitCommit"]], stdout=file)
    result.update(exitCode=0, archiveSha256=sha256_file(archive), checks={"gitArchive": True})
    write_json(directory / "project.json", result)


def validate_negative(path, code):
    data = json.loads(Path(path).read_text())
    if (code == 0 or data.get("exitCode") != 1 or data.get("expectedFailure") is not True
            or data.get("failureKind") != "missing-oscar-gui-profile" or data.get("cleanupError")):
        raise ValueError("negative probe did not fail specifically for missing OSCAR GUI")


def negative_probe(arch, directory):
    require_native(arch)
    require_disposable_runner()
    base = load_lock()["base"]
    image = f"{base['repository']}:{base['tag']}@{base['digest']}"
    run(["docker", "pull", "--platform", "linux/" + arch, image])
    completed = subprocess.run([sys.executable, "-m", "ci.runtime", "--arch", arch, "--image", image,
                                "--run-id", os.environ["OSCAR_RUN_ID"], "--artifacts", directory,
                                "--negative-base-probe"], cwd=ROOT)
    validate_negative(Path(directory) / f"negative-base-runtime-{arch}.json", completed.returncode)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--install-tools", action="store_true")
    operation.add_argument("--native-tools", action="store_true")
    operation.add_argument("--static-only", action="store_true")
    operation.add_argument("--chart", choices=["3.19.0", "4.3.2"])
    operation.add_argument("--sources", action="store_true")
    operation.add_argument("--negative", choices=["amd64", "arm64"])
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args(argv)
    # Put verified project-local tools first, never change account/global settings.
    os.environ["PATH"] = str(BIN) + os.pathsep + os.environ.get("PATH", "")
    if args.install_tools:
        install_tools()
    elif args.native_tools:
        native_tools()
    elif args.chart:
        chart_checks(args.chart, args.out_dir or ROOT / f"artifacts/chart/helm-{args.chart}")
    elif args.sources:
        source_checks(args.out_dir or ROOT / "artifacts/sources")
    elif args.negative:
        negative_probe(args.negative, args.out_dir or ROOT / f"artifacts/native/{args.negative}/negative")
    else:
        static_checks(args.out_dir or ROOT / "artifacts/ci01/static")
        if not args.static_only:
            for version in ("3.19.0", "4.3.2"):
                chart_checks(version, ROOT / f"artifacts/ci01/chart/helm-{version}")


if __name__ == "__main__":
    main()
