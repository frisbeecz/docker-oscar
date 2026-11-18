"""One complete native-image Trivy report, bound to the tested OCI archive. Apache-2.0."""
from collections import Counter
import argparse
import json
from pathlib import Path
import tempfile

from ci import load_lock, output, receipt, run, sha256_file, write_json
from ci.build_image import require_disposable_runner, require_native, require_native_daemon, verify_import
from ci.check import download, install_binary

# New images must not retain HIGH exceptions for the removed pip-vendored copies.
ACCEPTED_HIGH = set()


def validate_report(report: dict, accepted_high: set) -> dict:
    results = report.get("Results")
    if not isinstance(results, list) or not results:
        raise ValueError("complete Trivy package results required")
    findings, coverage = [], set()
    for result in results:
        if not isinstance(result, dict) or any(
                not isinstance(result.get(k), str) or not result[k].strip()
                for k in ("Target", "Class", "Type")):
            raise ValueError("incomplete Trivy package result")
        coverage.add((result["Class"], result["Type"]))
        vulnerabilities = result.get("Vulnerabilities")
        if vulnerabilities is None:  # Trivy omits this field for clean targets.
            vulnerabilities = []
        if not isinstance(vulnerabilities, list) or any(
                not isinstance(v, dict)
                or not isinstance(v.get("VulnerabilityID"), str) or not v["VulnerabilityID"].strip()
                or v.get("Severity") not in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
                for v in vulnerabilities):
            raise ValueError("invalid Trivy vulnerability findings")
        findings.extend(vulnerabilities)
    # This fixed Alpine image contains both APK and Python packages. Require
    # those scan targets even when they legitimately contain zero findings.
    if not {("os-pkgs", "alpine"), ("lang-pkgs", "python-pkg")} <= coverage:
        raise ValueError("incomplete Trivy Alpine/Python package coverage")
    high = {v["VulnerabilityID"] for v in findings if v["Severity"] == "HIGH"}
    if any(v["Severity"] == "CRITICAL" for v in findings) or high - accepted_high:
        raise ValueError("critical or unaccepted high vulnerability")
    return {"findings": dict(Counter(v["Severity"] for v in findings)), "acceptedHigh": sorted(high)}


def scan(image, arch, out_dir) -> dict:
    require_native(arch)
    require_disposable_runner()
    require_native_daemon(arch)
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"security-{arch}.json"
    report_path = folder / "security-report.json"
    if any(p.exists() or p.is_symlink() for p in (target, report_path)):
        raise FileExistsError("refusing to overwrite existing security evidence")
    result = receipt()
    try:
        build = json.loads((folder / f"build-{arch}.json").read_text())
        if (type(build["exitCode"]) is not int or build["exitCode"] != 0 or "cleanupError" in build
                or build["arch"] != arch or build["image"] != image
                or any(build[k] != result[k] for k in ("gitCommit", "dirtyDiffSha256"))
                or sha256_file(Path(build["archive"])) != build["archiveSha256"]):
            raise ValueError("security scan requires this exact tested build")
        inventory = json.loads(output(["docker", "image", "inspect", image]))[0]
        verify_import(build, inventory, arch)
        result.update(arch=arch, image=image, **{k: build[k] for k in (
            "manifestDigest", "configDigest", "archiveSha256")})
        scanner = load_lock("ci/tools.lock.json")["trivy"]
        # Keep evidence, not hundreds of MB of scanner/cache in uploaded artifacts.
        with tempfile.TemporaryDirectory(prefix="oscar-security-") as temporary:
            binary = Path(temporary) / "trivy"
            install_binary(download(scanner["artifacts"][arch]), "trivy", binary)
            version = output([str(binary), "--version"])
            if version.splitlines()[0] != "Version: " + scanner["version"]:
                raise ValueError("unsupported security scanner")
            (folder / "scanner-version.txt").write_text(version + "\n")
            cache = Path(temporary) / "cache"
            run([binary, "image", "--cache-dir", cache, "--download-db-only"])
            result["database"] = json.loads((cache / "db/metadata.json").read_text())
            run([binary, "image", "--cache-dir", cache, "--skip-db-update", "--image-src", "docker",
                 "--platform", "linux/" + arch, "--scanners", "vuln",
                 "--format", "json", "--output", report_path, image])
        report = json.loads(report_path.read_text())
        metadata = report["Metadata"]
        if (metadata.get("ImageID") != build["configDigest"]
                or metadata.get("ImageConfig", {}).get("architecture") != arch
                or metadata.get("ImageConfig", {}).get("os") != "linux"):
            raise ValueError("Trivy report does not describe the tested image")
        result.update(validate_report(report, ACCEPTED_HIGH),
                      reportSha256=sha256_file(report_path), scannerVersion=scanner["version"])
        result.update(checks={"noCritical": True, "acceptedHigh": True}, exitCode=0)
        return result
    except Exception as error:
        result.update(exitCode=1, error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(target, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    scan(args.image, args.arch, args.out_dir)


if __name__ == "__main__":
    main()
