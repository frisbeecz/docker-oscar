"""Pinned, native Trivy comparison; reports findings without suppressing unfixed CVEs."""
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import urllib.request

arch, mode = sys.argv[1:]
assert mode in ("prepare", "released", "base", "candidate")
assert os.environ.get("GITHUB_ACTIONS") == "true"
assert os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
assert os.environ.get("GITHUB_REPOSITORY") == "frisbeecz/docker-oscar"
assert os.environ.get("GITHUB_REF") == "refs/heads/spike/oscar-alpine"
assert platform.machine() == {"amd64": "x86_64", "arm64": "aarch64"}[arch]
inputs = json.loads(Path("spike/alpine/inputs.json").read_text())
out = Path("artifacts/alpine") / arch
out.mkdir(parents=True, exist_ok=True)
tool = out / "trivy"
cache = Path("artifacts/trivy-cache")
if mode == "prepare":
    version = inputs["trivy"]["version"]
    filename = f"trivy_{version}_Linux-" + {"amd64": "64bit", "arm64": "ARM64"}[arch] + ".tar.gz"
    with urllib.request.urlopen(
            f"https://github.com/aquasecurity/trivy/releases/download/v{version}/{filename}",
            timeout=180) as response:
        raw = response.read()
    assert hashlib.sha256(raw).hexdigest() == inputs["trivy"]["sha256"][arch]
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        entry = archive.getmember("trivy")
        assert entry.isfile()
        tool.write_bytes(archive.extractfile(entry).read())
    tool.chmod(0o700)
    with (out / "scanner-version.txt").open("w") as f:
        subprocess.run([str(tool), "--version"], check=True, stdout=f)
    subprocess.run([str(tool), "image", "--cache-dir", str(cache), "--download-db-only"],
                   check=True)
    (out / "database.json").write_bytes((cache / "db/metadata.json").read_bytes())
else:
    reference = {"released": inputs["releasedImage"], "base": inputs["base"],
                 "candidate": "oscar-alpine-spike:" + arch}[mode]
    report = out / (mode + "-trivy.json")
    subprocess.run([str(tool), "image", "--cache-dir", str(cache), "--skip-db-update",
                    "--image-src", "docker" if mode == "candidate" else "remote",
                    "--platform", "linux/" + arch, "--scanners", "vuln",
                    "--format", "json", "--output", str(report), reference], check=True)
    data = json.loads(report.read_text())
    findings = [v for result in data.get("Results", []) for v in result.get("Vulnerabilities", [])]
    summary = {"reference": reference, "architecture": arch, "scanner": inputs["trivy"]["version"],
               "database": json.loads((out / "database.json").read_text()),
               "os": data.get("Metadata", {}).get("OS"),
               "findings": dict(Counter(v["Severity"] for v in findings)),
               "uniqueVulnerabilities": len({v["VulnerabilityID"] for v in findings}),
               "withFixedVersion": sum(bool(v.get("FixedVersion")) for v in findings)}
    (out / (mode + "-summary.json")).write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
