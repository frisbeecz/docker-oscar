"""Real pinned bundle regression; only external cluster transport is replaced.

These tests are not Kubernetes deployment evidence.
SPDX-License-Identifier: Apache-2.0
"""
from pathlib import Path

import pytest
import yaml

from ci import load_lock, sha256_file
from ci.chart import prepare_schemas
from ci.kubernetes import Cluster
from .conftest import ROOT


@pytest.fixture
def bundle():
    schemas = prepare_schemas(ROOT / "artifacts/chart/schemas")
    path = Path(schemas["HTTPRoute"]["path"]).parent / "gateway-standard.yaml"
    assert sha256_file(path) == load_lock("ci/tools.lock.json")["schemas"]["gateway"]["sha256"]
    return path


def transport_cluster(tmp_path):
    cluster = Cluster(tmp_path / "unused-kubeconfig", "kind-oscar-ci-unit", "unit", "amd64", tmp_path)
    events = []
    cluster.guard_namespace = lambda: events.append(("guard",))
    cluster.kubectl = lambda *args: events.append(args)
    return cluster, events


def test_install_actual_pinned_bundle_includes_admission_and_waits_only_crds(tmp_path, bundle):
    docs = [doc for doc in yaml.safe_load_all(bundle.read_text()) if doc]
    crds = [doc for doc in docs if doc["kind"] == "CustomResourceDefinition"]
    assert len(crds) == 10
    assert {doc["kind"] for doc in docs} == {
        "CustomResourceDefinition", "ValidatingAdmissionPolicy", "ValidatingAdmissionPolicyBinding"}
    cluster, events = transport_cluster(tmp_path)
    cluster.install_gateway(bundle)
    assert events == [
        ("guard",), ("apply", "--server-side", "-f", str(bundle)),
        *(("wait", f"crd/{doc['metadata']['name']}", "--for=condition=Established", "--timeout=60s")
          for doc in crds)]


def test_corrupt_gateway_bundle_cannot_mutate_cluster(tmp_path, bundle):
    corrupt = tmp_path / "corrupt.yaml"
    corrupt.write_bytes(bundle.read_bytes() + b"\n# changed\n")
    cluster, events = transport_cluster(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        cluster.install_gateway(corrupt)
    assert events == [("guard",)]


@pytest.mark.parametrize("unexpected", [
    {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "unrelated"}},
    {"apiVersion": "wrong.example/v1", "kind": "CustomResourceDefinition",
     "metadata": {"name": "httproutes.gateway.networking.k8s.io"}},
    {"apiVersion": "admissionregistration.k8s.io/v1", "kind": "ValidatingAdmissionPolicy",
     "metadata": {"name": "unrelated-policy"}},
])
def test_unexpected_bundle_document_rejected_before_apply(tmp_path, bundle, unexpected, monkeypatch):
    candidate = tmp_path / "unexpected.yaml"
    candidate.write_text(bundle.read_text() + "\n---\n" + yaml.safe_dump(unexpected))
    pin = load_lock("ci/tools.lock.json")
    pin["schemas"]["gateway"]["sha256"] = sha256_file(candidate)
    # Simulate a future lock update: the complete inventory must be checked
    # before any apply, not merely rejected after partially mutating a cluster.
    monkeypatch.setattr("ci.kubernetes.load_lock", lambda *_: pin)
    cluster, events = transport_cluster(tmp_path)
    with pytest.raises(ValueError, match="unexpected object"):
        cluster.install_gateway(candidate)
    assert events == [("guard",)]
