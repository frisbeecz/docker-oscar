"""Exact corresponding OSCAR source and explicit packaging inputs. Apache-2.0."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile

from ci import ROOT, load_lock, receipt, run, sha256_file, write_json

SOURCE_FILES = [
    "Dockerfile", ".dockerignore", ".gitignore", "versions.lock.json", "python-requirements.txt",
    "root/defaults/autostart_wayland", "root/usr/local/bin/oscar-start",
    "root/etc/s6-overlay/s6-rc.d/init-oscar-data/run",
    "root/etc/s6-overlay/s6-rc.d/init-oscar-data/type",
    "root/etc/s6-overlay/s6-rc.d/init-oscar-data/up",
    "root/etc/s6-overlay/s6-rc.d/init-oscar-data/dependencies.d/init-custom-files",
    "root/etc/s6-overlay/s6-rc.d/init-services/dependencies.d/init-oscar-data",
    "ci/__init__.py", "ci/build_image.py", "ci/runtime.py", "ci/runtime_checks.py", "ci/gui.py",
    "ci/security.py", "ci/check.py", "ci/chart.py",
    "ci/source_bundle.py", "ci/tools.lock.json", "requirements-ci.lock",
    "pyproject.toml", "LICENSE", "NOTICE.md", "README.md",
    "docs/container.md", "docs/migration.md",
]


def binary_provenance(locked):
    source = locked["oscar"]
    packages = source["binaries"]
    if (set(packages) != {"amd64", "arm64"}
            or set(locked["platforms"]) != {"linux/" + arch for arch in packages}
            or source["binarySourceCorrespondence"] != "version-aligned; not independently proven"):
        raise ValueError("inconsistent binary provenance platforms/correspondence")
    for arch, pin in packages.items():
        expected_url = (f"https://www.sleepfiles.com/OSCAR/{source['version']}/"
                        f"oscar20_{source['version']}-Debian13_{arch}-Qt6.deb")
        if (pin["architecture"] != arch or pin["package"] != "oscar20"
                or pin["version"] != source["version"] + "-Debian13"
                or pin["url"] != expected_url or not re.fullmatch(r"[a-f0-9]{64}", pin["sha256"])):
            raise ValueError("inconsistent binary provenance package")
    return {"packages": packages, "sourceTag": "v" + source["version"],
            "sourceCommit": source["commit"],
            "correspondence": source["binarySourceCorrespondence"]}


def source_provenance(locked: dict) -> dict:
    source = locked["oscar"]
    build = {"type": "source", "recipe": "Dockerfile", "pythonRequirements": "python-requirements.txt"}
    if (source.get("build") != build or "binaries" in source or "binarySourceCorrespondence" in source
            or not re.fullmatch(r"[a-f0-9]{40}", source.get("commit", ""))
            or not re.fullmatch(r"[a-f0-9]{64}", source.get("sha256", ""))
            or source.get("url") != ("https://gitlab.com/CrimsonNape/OSCAR-SQL/-/archive/"
                                    f"{source['commit']}/OSCAR-SQL-{source['commit']}.tar.gz")):
        raise ValueError("inconsistent source provenance")
    return {**build, "sourceCommit": source["commit"], "sourceSha256": source["sha256"]}


def build_bundle(out_dir: Path, *, project=ROOT, source_archive: Path | None = None, command=None) -> dict:
    project, out_dir = Path(project), Path(out_dir)
    locked = load_lock(project=project)
    source = locked["oscar"]
    proof = "sourceProvenance" if "build" in source else "binaryProvenance"
    provenance = source_provenance(locked) if proof == "sourceProvenance" else binary_provenance(locked)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oscar-source-", dir=out_dir.parent) as tmp:
        tmp = Path(tmp)
        archive = Path(source_archive) if source_archive else tmp / "upstream.tar.gz"
        if source_archive is None:
            run(["curl", "--fail", "--location", "--connect-timeout", "20", "--max-time", "300",
                 "--max-filesize", "268435456", source["url"], "-o", archive])
        if sha256_file(archive) != source["sha256"]:
            raise ValueError("upstream source checksum mismatch")
        if source["patches"]:
            raise ValueError("patch list is nonempty but this revision has no patch application implementation")
        with tarfile.open(archive, "r:gz") as tar:
            licenses = [m for m in tar.getmembers() if m.name.count("/") == 1 and m.name.endswith("/COPYING")]
            if len(licenses) != 1 or not licenses[0].isfile():
                raise ValueError("missing upstream COPYING")
            upstream_license = tar.extractfile(licenses[0]).read()
        out_dir.mkdir(parents=True, exist_ok=True)
        if any(out_dir.iterdir()):
            raise FileExistsError("source output must be empty")
        upstream = out_dir / f"oscar-{source['version']}-{source['commit']}.tar.gz"
        shutil.copyfile(archive, upstream)
        (out_dir / "OSCAR-COPYING").write_bytes(upstream_license)
        packaging = out_dir / "packaging.tar.gz"
        files = SOURCE_FILES + [str(p.relative_to(project)) for p in sorted((project / "tests").rglob("*.py"))]
        with tarfile.open(packaging, "w:gz") as tar:
            for name in files:
                path = project / name
                if not path.is_file() or path.is_symlink():
                    raise ValueError(f"missing or unsafe source input: {name}")
                tar.add(path, arcname="docker-oscar/" + name, recursive=False)
        origin = {**receipt(project=project, command=command), "exitCode": 0, "oscar": source,
                  proof: provenance,
                  "base": locked["base"], "patches": [], "license": "Apache-2.0",
                  "sourceArchive": {"path": upstream.name, "sha256": sha256_file(upstream)},
                  "packaging": {"path": packaging.name, "sha256": sha256_file(packaging)},
                  "files": {name: sha256_file(project / name) for name in files},
                  "checks": {"sourceChecksum": True, "upstreamLicense": True,
                              "patchList": True, "packagingInputs": True,
                               proof: True}}
        write_json(out_dir / "origin.json", origin)
        return origin


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, help="offline cache; always checked against the lock")
    args = parser.parse_args(argv)
    build_bundle(args.out_dir, source_archive=args.source_archive,
                 command=[sys.executable, "-m", "ci.source_bundle", *(argv or sys.argv[1:])])


if __name__ == "__main__":
    main()
