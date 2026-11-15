"""Native runner-only OCI build, verified local import. Apache-2.0."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tarfile
import uuid

from ci import ROOT, load_lock, output, receipt, run, sha256_file, write_json


def require_native(arch: str, *, system=None, machine=None) -> str:
    system = system or platform.system()
    machine = machine or platform.machine()
    native = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    if system != "Linux" or native != arch or arch not in {"amd64", "arm64"}:
        raise ValueError(f"native Linux {arch} required, got {system}/{machine}; emulation is not acceptance")
    return arch


def require_disposable_runner():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("privileged BuildKit infrastructure is approved only on a disposable GitHub-hosted runner")


def require_native_daemon(arch):
    info = json.loads(output(["docker", "info", "--format", "{{json .}}"]))
    require_native(arch, system="Linux" if info["OSType"] == "linux" else info["OSType"],
                   machine=info["Architecture"])
    return info


def inspect_oci(path: Path, arch: str) -> dict:
    """Verify descriptor and compressed/uncompressed layer contents without extraction."""
    with tarfile.open(path, "r:*") as tar:
        names = tar.getnames()
        if len(names) != len(set(names)):
            raise ValueError("duplicate OCI archive paths")
        def small(name):
            member = tar.getmember(name)
            if not member.isfile() or member.size > 16 * 1024 * 1024:
                raise ValueError("invalid OCI metadata member")
            return tar.extractfile(member).read()
        def blob(descriptor):
            digest = descriptor["digest"]
            if not digest.startswith("sha256:") or len(digest) != 71:
                raise ValueError("invalid OCI digest")
            data = small("blobs/sha256/" + digest[7:])
            if len(data) != descriptor["size"] or "sha256:" + hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("OCI blob digest mismatch")
            return data
        index = json.loads(small("index.json"))
        if len(index["manifests"]) != 1:
            raise ValueError("OCI archive must contain exactly one image manifest")
        desc = index["manifests"][0]
        manifest = json.loads(blob(desc))
        if "manifests" in manifest or "layers" not in manifest:
            raise ValueError("OCI archive must contain one platform image, not a nested index")
        config = json.loads(blob(manifest["config"]))
        if config["os"] != "linux" or config["architecture"] != arch:
            raise ValueError("OCI platform mismatch")
        diff_ids = []
        for layer in manifest["layers"]:
            digest = layer["digest"]
            if not digest.startswith("sha256:") or len(digest) != 71:
                raise ValueError("invalid layer digest")
            member = tar.getmember("blobs/sha256/" + digest[7:])
            if not member.isfile() or member.size != layer["size"]:
                raise ValueError("invalid layer size")
            with tar.extractfile(member) as stream:
                compressed_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if "sha256:" + compressed_hash != digest:
                raise ValueError("layer digest mismatch")
            with tar.extractfile(member) as raw:
                media = layer.get("mediaType", "")
                if media.endswith("+gzip"):
                    with gzip.GzipFile(fileobj=raw) as stream:
                        diff_ids.append("sha256:" + hashlib.file_digest(stream, "sha256").hexdigest())
                elif media.endswith(".tar"):
                    diff_ids.append("sha256:" + hashlib.file_digest(raw, "sha256").hexdigest())
                else:
                    raise ValueError(f"unsupported layer compression: {media}")
        if diff_ids != config["rootfs"]["diff_ids"]:
            raise ValueError("uncompressed layer identity mismatch")
        return {"manifestDigest": desc["digest"], "configDigest": manifest["config"]["digest"],
                "layerDigests": [v["digest"] for v in manifest["layers"]], "diffIds": diff_ids}


def verify_import(oci, image, arch):
    if (image["Id"] != oci["configDigest"] or image["Os"] != "linux"
            or image["Architecture"] != arch or image["RootFS"]["Layers"] != oci["diffIds"]):
        raise ValueError("Docker import config/layer identity mismatch")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    # Refuse before mkdir, daemon probe, builder bootstrap or receipt success.
    require_native(args.arch)
    require_disposable_runner()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    result = receipt(command=[sys.executable, "-m", "ci.build_image", *(argv or sys.argv[1:])])
    builder = "oscar-ci-build-" + uuid.uuid4().hex[:16]
    created = False
    try:
        tools = load_lock("ci/tools.lock.json")
        if tools["buildx"]["version"] not in output(["docker", "buildx", "version"]):
            raise ValueError("unsupported buildx version")
        if output(["skopeo", "--version"]).split()[-1] != tools["skopeo"]["version"]:
            raise ValueError("unsupported skopeo version")
        daemon = require_native_daemon(args.arch)
        result["daemon"] = {k: daemon.get(k) for k in ["OSType", "Architecture", "ServerVersion"]}
        run(["docker", "buildx", "create", "--name", builder, "--driver", "docker-container",
             "--driver-opt", "image=" + tools["buildkit"]["image"]])
        created = True
        archive = args.out_dir.resolve() / f"image-{args.arch}.oci.tar"
        if archive.exists():
            raise FileExistsError(f"refusing to overwrite {archive}")
        run(["docker", "buildx", "build", "--builder", builder, "--platform", f"linux/{args.arch}",
             "--provenance=false", "--output", f"type=oci,compression=gzip,dest={archive}",
             "--build-arg", "VCS_REF=" + (result["gitCommit"] or "unborn"), str(ROOT)])
        identity = inspect_oci(archive, args.arch)
        image = f"oscar-under-test:{args.arch}"
        run(["skopeo", "copy", f"oci-archive:{archive}", f"docker-daemon:{image}"])
        imported = json.loads(output(["docker", "image", "inspect", image]))[0]
        verify_import(identity, imported, args.arch)
        result.update(arch=args.arch, image=image, **identity,
                      archiveSha256=sha256_file(archive), archive=str(archive),
                      sources=load_lock(), attestation="none; separate source provenance only")
        result["checks"] = {"nativeHost": True, "nativeDaemon": True, "singleManifest": True,
                            "configAndLayerIdentity": True}
        result["exitCode"] = 0
    except Exception as error:
        result.update(exitCode=1, error=f"{type(error).__name__}: {error}")
        raise
    finally:
        try:
            if created:
                run(["docker", "buildx", "rm", builder])
        except Exception as error:
            result.update(exitCode=1, cleanupError=str(error))
            raise
        finally:
            write_json(args.out_dir / f"build-{args.arch}.json", result)


if __name__ == "__main__":
    main()
