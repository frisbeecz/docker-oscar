"""Real Helm lint/render/strict-schema matrix. SPDX-License-Identifier: Apache-2.0."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

import yaml

from ci import (ROOT, canonical_json, load_lock, output, receipt, run, sha256_file,
                strict_gateway_schema, write_json)

API = "gateway.networking.k8s.io/v1/HTTPRoute"
CHART = ROOT / "charts/oscar"
SCHEMAS = {
    "Deployment": ("apps/v1", "deployment-apps-v1.json"),
    "Service": ("v1", "service-v1.json"),
    "PersistentVolumeClaim": ("v1", "persistentvolumeclaim-v1.json"),
    "ServiceAccount": ("v1", "serviceaccount-v1.json"),
    "Ingress": ("networking.k8s.io/v1", "ingress-networking-v1.json"),
    "HTTPRoute": ("gateway.networking.k8s.io/v1", "httproute-v1-strict.json"),
}


def verified_input(directory, name, pin):
    """Reuse successful inputs; corrupt cached bytes fail closed, never refresh."""
    target = Path(directory) / name
    candidates = [target, ROOT / "artifacts/image01/upstream" / name]
    source = next((p for p in candidates if p.exists()), None)
    if source is not None:
        if sha256_file(source) != pin["sha256"]:
            raise ValueError(f"checksum mismatch: {source.name}")
        data = source.read_bytes()
    else:
        with urllib.request.urlopen(pin["url"], timeout=60) as response:
            data = response.read()
        import hashlib
        if hashlib.sha256(data).hexdigest() != pin["sha256"]:
            raise ValueError(f"download checksum mismatch: {name}")
    if target != source:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return target


def prepare_schemas(directory):
    directory = Path(directory).resolve()
    pins = load_lock("ci/tools.lock.json")["schemas"]
    for name, pin in pins["kubernetes"]["files"].items():
        verified_input(directory, name, pin)
    crd = verified_input(directory, "gateway-standard.yaml", pins["gateway"])
    metadata = json.loads((directory / "service-v1.json").read_text())["properties"]["metadata"]
    derived = canonical_json(strict_gateway_schema(crd.read_bytes(), metadata)) + b"\n"
    target = directory / "httproute-v1-strict.json"
    import hashlib
    expected = pins["gateway"]["strictSchemaSha256"]
    if hashlib.sha256(derived).hexdigest() != expected:
        raise ValueError("derived HTTPRoute schema checksum mismatch")
    if target.exists() and sha256_file(target) != expected:
        raise ValueError("cached HTTPRoute schema checksum mismatch")
    target.write_bytes(derived)
    # Keep the upstream dialect declarations byte-for-byte. Kubeconform 0.8.0
    # handles the upstream generic schema# URI; do not coerce via jsonschema's
    # newer-default dialect or rewrite the pinned input to suppress warnings.
    return {kind: {"apiVersion": api, "path": str(directory / name),
                   "sha256": sha256_file(directory / name)}
            for kind, (api, name) in SCHEMAS.items()}


def validate_documents(documents, schemas, kubeconform):
    totals = {"valid": 0, "invalid": 0, "errors": 0, "skipped": 0}
    pins = load_lock("ci/tools.lock.json")
    with tempfile.TemporaryDirectory(prefix="strict-", dir=Path(schemas["Deployment"]["path"]).parent) as tmp:
        for index, doc in enumerate(documents):
            pin = schemas.get(doc["kind"])
            if not pin or doc["apiVersion"] != pin["apiVersion"]:
                raise ValueError(f"no pinned schema for {doc['apiVersion']}/{doc['kind']}")
            if sha256_file(Path(pin["path"])) != pin["sha256"]:
                raise ValueError("schema changed during validation")
            path = Path(tmp) / f"{index}.yaml"
            path.write_text(yaml.safe_dump(doc))
            command = [kubeconform, "-strict", "-summary", "-output", "json",
                       "-kubernetes-version", pins["schemas"]["kubernetes"]["version"],
                       "-schema-location", pin["path"], str(path)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)
            summary = json.loads(result.stdout)["summary"]
            if summary != {"valid": 1, "invalid": 0, "errors": 0, "skipped": 0}:
                raise ValueError(f"incomplete strict validation: {summary}")
            for key in totals:
                totals[key] += summary[key]
    return totals


def route_values(ingress, gateway):
    return {
        "ingress": {"enabled": ingress, "className": "example", "hosts": [
            {"host": "oscar.example.org", "paths": [{"path": "/", "pathType": "Prefix"}]}],
            "tls": [{"secretName": "oscar-tls", "hosts": ["oscar.example.org"]}]},
        "gateway": {"enabled": gateway, "parentRefs": [{"name": "shared", "sectionName": "https"}],
                    "hostnames": ["oscar.example.org"]},
    }


def matrix():
    cases = {f"routes-{int(i)}-{int(g)}": route_values(i, g)
             for i, g in [(False, False), (True, False), (False, True), (True, True)]}
    cases["existing-claims"] = {"persistence": {
        role: {"existingClaim": f"external-{role}"} for role in ["config", "data", "sdcard"]}}
    cases["digest"] = {"image": {"digest": "sha256:" + "a" * 64}}
    cases["empty-storage-class"] = {"persistence": {r: {"storageClass": ""} for r in ["config", "data", "sdcard"]}}
    cases["extra-pvc"] = {"extraPvcMounts": [
        {"name": "legacy", "claimName": "legacy-copy", "mountPath": "/imports/legacy"}]}
    return cases


def lint_chart(helm, values_file, log_file):
    # Lint has no --api-versions. Its LintMode records template fail() as INFO;
    # capability enforcement is separately exercised by real template calls,
    # both positive with the exact G/V/K and negative without it.
    with Path(log_file).open("w") as log:
        run([helm, "lint", str(CHART), "--strict", "-f", str(values_file)],
            stdout=log, stderr=subprocess.STDOUT)


def execute(args, result):
    tools = load_lock("ci/tools.lock.json")
    helm_version = output([args.helm, "version", "--short"])
    match = re.match(r"v([0-9]+\.[0-9]+\.[0-9]+)(?:\+|$)", helm_version)
    if not match or match[1] not in tools["helm"]:
        raise ValueError(f"unsupported Helm version: {helm_version}")
    kube_version = output([args.kubeconform, "-v"])
    if kube_version != "v" + tools["kubeconform"]["version"]:
        raise ValueError(f"unsupported kubeconform version: {kube_version}")
    result.update(helmVersion=helm_version, kubeconformVersion=kube_version)
    schemas = prepare_schemas(args.schema_cache)
    result["schemas"] = schemas
    result["schemaDialectPolicy"] = "Pinned upstream bytes, kubeconform 0.8.0 native dialect handling; no rewriting or missing-schema bypass"
    env = {**os.environ, "HELM": args.helm, "KUBECONFORM": args.kubeconform}
    with (args.out_dir / "pytest.log").open("w") as log:
        run([sys.executable, "-m", "pytest", "tests/chart", "-q"], env=env, stdout=log, stderr=subprocess.STDOUT)
    result["checks"]["pytest"] = True
    result["matrix"] = {}
    for name, values in matrix().items():
        file = args.out_dir / f"{name}.values.yaml"
        file.write_text(yaml.safe_dump(values))
        capabilities = ["--api-versions", API] if values.get("gateway", {}).get("enabled") else []
        lint_chart(args.helm, file, args.out_dir / f"{name}.lint.log")
        manifest = output([args.helm, "template", "demo", str(CHART), "-f", str(file), *capabilities])
        (args.out_dir / f"{name}.yaml").write_text(manifest + "\n")
        documents = [d for d in yaml.safe_load_all(manifest) if d]
        result["matrix"][name] = validate_documents(documents, schemas, args.kubeconform)
    result["checks"].update(lint=True, render=True, strictSchemas=True, routeMatrix=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helm", required=True)
    parser.add_argument("--kubeconform", default=os.environ.get("KUBECONFORM", "kubeconform"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--schema-cache", type=Path, default=ROOT / "artifacts/chart/schemas")
    args = parser.parse_args(argv)
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / "chart.json"
    if target.exists():
        raise FileExistsError("refusing to overwrite an existing chart receipt")
    result = receipt(command=[sys.executable, "-m", "ci.chart", *(sys.argv[1:] if argv is None else argv)])
    try:
        execute(args, result)
        result["exitCode"] = 0
    except Exception as error:
        result.update(exitCode=1, error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(target, result)


if __name__ == "__main__":
    main()
