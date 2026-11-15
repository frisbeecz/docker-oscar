"""Real Helm boundary helpers. SPDX-License-Identifier: Apache-2.0."""
import os
from pathlib import Path
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "charts/oscar"
API = "gateway.networking.k8s.io/v1/HTTPRoute"


def helm_result(values=None, api_versions=(), release="demo"):
    (ROOT / "artifacts/pytest-temp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/pytest-temp") as directory:
        file = Path(directory) / "values.yaml"
        file.write_text(yaml.safe_dump(values or {}))
        command = [os.environ.get("HELM", "helm"), "template", release, str(CHART), "-f", str(file)]
        for api in api_versions:
            command += ["--api-versions", api]
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def render_chart(values: dict, api_versions: tuple[str, ...] = (), release="demo") -> list[dict]:
    result = helm_result(values, api_versions, release)
    assert result.returncode == 0, result.stderr
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def pvc_names(docs: list[dict]) -> set[str]:
    return {d["metadata"]["name"] for d in docs if d["kind"] == "PersistentVolumeClaim"}


def config_pvc(storage_class: str | None) -> dict:
    return next(d for d in render_chart({"persistence": {"config": {"storageClass": storage_class}}})
                if d["kind"] == "PersistentVolumeClaim" and d["metadata"]["name"].endswith("-config-v2"))


def config_claim_reference(docs: list[dict]) -> str:
    deployment = next(d for d in docs if d["kind"] == "Deployment")
    return next(v for v in deployment["spec"]["template"]["spec"]["volumes"]
                if v["name"] == "config")["persistentVolumeClaim"]["claimName"]


def one(docs, kind):
    return next(d for d in docs if d["kind"] == kind)


def routes(ingress=True, gateway=True):
    return {
        "ingress": {"enabled": ingress, "hosts": [{"host": "oscar.example.org", "paths": [
            {"path": "/", "pathType": "Prefix"}]}], "tls": [
                {"secretName": "oscar-tls", "hosts": ["oscar.example.org"]}]},
        "gateway": {"enabled": gateway, "parentRefs": [{"name": "shared", "sectionName": "https"}],
                    "hostnames": ["oscar.example.org"]},
    }
