"""Local safety/retention tests, NOT deployment evidence.

Only external process transport is substituted. No live kubeconfig is used.
SPDX-License-Identifier: Apache-2.0
"""
import copy
import importlib
import json
import os
import subprocess

import pytest
import yaml

from .conftest import ROOT, one, pvc_names, render_chart

CONTEXT = "kind-oscar-ci-unit"


def module():
    assert (ROOT / "ci/kubernetes.py").is_file(), "isolated Kubernetes harness missing"
    return importlib.import_module("ci.kubernetes")


def kubeconfig():
    return {"apiVersion": "v1", "kind": "Config", "current-context": CONTEXT,
            "clusters": [{"name": CONTEXT, "cluster": {
                "server": "https://127.0.0.1:16443", "certificate-authority-data": "Y2E="}}],
            "contexts": [{"name": CONTEXT, "context": {"cluster": CONTEXT, "user": CONTEXT}}],
            "users": [{"name": CONTEXT, "user": {
                "client-certificate-data": "Y2VydA==", "client-key-data": "a2V5"}}]}


def cluster_inputs():
    nodes = {"items": [{"metadata": {"name": "oscar-ci-unit-control-plane",
                                    "labels": {"io.docker-oscar.ci-run": "unit"}},
                        "status": {"nodeInfo": {"architecture": "amd64", "operatingSystem": "linux"}}}]}
    marker = {"metadata": {"name": "oscar-ci-owner", "namespace": "kube-system"},
              "data": {"runId": "unit", "context": CONTEXT, "purpose": "disposable-oscar-ci"}}
    return nodes, marker


def claim_items():
    return [{"metadata": {"name": f"first-oscar-{r}-v2", "namespace": "test-ns", "uid": f"uid-{r}",
                           "labels": {"app.kubernetes.io/managed-by": "Helm"},
                           "annotations": {"meta.helm.sh/release-name": "first",
                                           "meta.helm.sh/release-namespace": "test-ns",
                                           "helm.sh/resource-policy": "keep"}},
             "status": {"phase": "Bound"}, "spec": {"volumeName": f"pv-{r}"}}
            for r in ["config", "data", "sdcard"]]


def audit():
    return {"profiles": ["ci-synthetic"], "language": "en_US",
            "data": [{"path": "Documents/OSCAR20_Data/oscar.db", "uid": 1000, "gid": 1000, "integrity": "ok"}],
            "dataFiles": [{"path": "Documents/OSCAR20_Data/oscar.db", "uid": 1000, "gid": 1000}],
            "qtConfig": [{"path": ".config/OSCAR/OSCAR.conf", "uid": 1000, "gid": 1000}],
            "outsideDatabases": []}


def test_refuse_ambient_kubeconfig(tmp_path, monkeypatch):
    k = module()
    monkeypatch.setenv("KUBECONFIG", "/must/not/use/ambient")
    result = subprocess.run([os.sys.executable, "-m", "ci.kubernetes", "--image", "oscar-under-test:amd64",
                             "--run-id", "unit", "--artifacts", str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError):
        k.validate_kubeconfig(None, CONTEXT, "unit")


@pytest.mark.parametrize("mutation", [
    lambda c: c.update({"current-context": "production"}),
    lambda c: c["clusters"][0]["cluster"].update({"server": "https://cluster.example.org:6443"}),
    lambda c: c["clusters"][0]["cluster"].update({"server": "http://127.0.0.1:16443"}),
    lambda c: c["clusters"][0]["cluster"].update({"server": "https://user@127.0.0.1:16443"}),
    lambda c: c["clusters"][0]["cluster"].update({"insecure-skip-tls-verify": True}),
    lambda c: c["clusters"][0]["cluster"].update({"proxy-url": "https://proxy.example.org"}),
    lambda c: c["users"][0]["user"].update({"exec": {"command": "dangerous"}}),
    lambda c: c["users"][0]["user"].update({"tokenFile": "/secret"}),
    lambda c: c["users"][0]["user"].update({"client-key": "/secret"}),
    lambda c: c["contexts"].append(copy.deepcopy(c["contexts"][0])),
    lambda c: c["contexts"][0]["context"].update({"namespace": "production"}),
])
def test_kubeconfig_rejects_untrusted_inputs(tmp_path, mutation):
    k = module()
    config = kubeconfig()
    mutation(config)
    file = tmp_path / "kubeconfig"
    file.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        k.validate_kubeconfig(file, CONTEXT, "unit")


def test_explicit_kubeconfig_and_run_id(tmp_path):
    k = module()
    file = tmp_path / "kubeconfig"
    file.write_text(yaml.safe_dump(kubeconfig()))
    assert k.validate_kubeconfig(file, CONTEXT, "unit") == kubeconfig()
    for context, run_id in [(None, "unit"), ("kind-oscar-ci-other", "unit"),
                            (CONTEXT, "../unit"), (CONTEXT, "other")]:
        with pytest.raises(ValueError):
            k.validate_kubeconfig(file, context, run_id)


def test_fresh_install():
    k = module()
    nodes, marker = cluster_inputs()
    k.require_cluster(nodes, marker, "unit", CONTEXT, "amd64")
    for changed_nodes, changed_marker in [
        ({"items": []}, marker), (nodes, {"data": {}}),
        ({"items": [{"metadata": {"labels": {}}, "status": nodes["items"][0]["status"]}]}, marker),
    ]:
        with pytest.raises(ValueError):
            k.require_cluster(changed_nodes, changed_marker, "unit", CONTEXT, "amd64")
    with pytest.raises(ValueError):
        k.require_cluster(nodes, marker, "unit", CONTEXT, "arm64")
    values = k.image_values("oscar-under-test:amd64")
    assert values == {"image": {"repository": "oscar-under-test", "tag": "amd64",
                                "digest": "", "pullPolicy": "Never"}}
    docs = render_chart(values)
    assert not any(d["kind"] in ("Ingress", "HTTPRoute") for d in docs)
    assert len(pvc_names(docs)) == 3


@pytest.mark.parametrize("image", ["", "image", "image:latest@sha256:no", "image:bad tag", "-bad:tag",
                                  "image:embedded:tag"])
def test_invalid_test_image(image):
    with pytest.raises(ValueError):
        module().image_values(image)


def test_application_survives_pod_replacement():
    k = module()
    first = audit()
    k.validate_application(first, copy.deepcopy(first))
    for field, bad in [("profiles", []), ("language", ""), ("data", []), ("qtConfig", []),
                       ("outsideDatabases", ["/tmp/fallback.db"])]:
        second = copy.deepcopy(first)
        second[field] = bad
        with pytest.raises(ValueError):
            k.validate_application(first, second)
    for field in ["data", "dataFiles", "qtConfig"]:
        second = copy.deepcopy(first)
        second[field][0]["uid"] = 0
        with pytest.raises(ValueError):
            k.validate_application(first, second)


def test_uninstall_preserves_claims():
    k = module()
    items = claim_items()
    baseline = k.claim_snapshot(items, namespace="test-ns", release="first")
    k.compare_claims(baseline, k.claim_snapshot(copy.deepcopy(items), namespace="test-ns"))
    for mutate in [
        lambda c: c[0]["metadata"].update(uid="replacement"),
        lambda c: c[0]["metadata"]["annotations"].update({"meta.helm.sh/release-name": "second"}),
        lambda c: c[0]["metadata"]["labels"].update({"app.kubernetes.io/managed-by": "other"}),
        lambda c: c[0]["spec"].update(volumeName="replacement-pv"),
        lambda c: c.pop(),
    ]:
        changed = copy.deepcopy(items)
        mutate(changed)
        with pytest.raises(ValueError):
            current = k.claim_snapshot(changed, namespace="test-ns")
            k.compare_claims(baseline, current)


def test_reinstall_with_existing_claims():
    k = module()
    baseline = k.claim_snapshot(claim_items(), namespace="test-ns", release="first")
    values = k.reuse_values(baseline, "oscar-under-test:amd64")
    docs = render_chart(values, release="second")
    assert pvc_names(docs) == set()
    volumes = one(docs, "Deployment")["spec"]["template"]["spec"]["volumes"]
    assert {v["persistentVolumeClaim"]["claimName"] for v in volumes if "persistentVolumeClaim" in v} == {
        "first-oscar-config-v2", "first-oscar-data-v2", "first-oscar-sdcard-v2"}


def test_every_transport_command_is_explicit(tmp_path, monkeypatch):
    k = module()
    captured = []
    def transport(command, **kwargs):
        captured.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout='{"items":[]}', stderr="")
    monkeypatch.setattr(k, "run", transport)
    cluster = k.Cluster(tmp_path / "owned-kubeconfig", CONTEXT, "unit", "amd64", tmp_path)
    cluster.kubectl("get", "pods", "-o", "json")
    cluster.helm("list", "-o", "json")
    assert len(captured) == 2
    for command, kwargs in captured:
        assert "--kubeconfig" in command
        assert str(tmp_path / "owned-kubeconfig") in command
        assert CONTEXT in command
        assert kwargs["env"]["KUBECONFIG"] == str(tmp_path / "owned-kubeconfig")
        assert kwargs["timeout"] > 0


def test_build_receipt_must_match_exact_state(tmp_path):
    k = module()
    result = {"gitCommit": "commit", "dirtyDiffSha256": "diff"}
    build = {"gitCommit": "commit", "dirtyDiffSha256": "diff", "exitCode": 0, "arch": "amd64",
             "manifestDigest": "sha256:" + "a" * 64, "configDigest": "sha256:" + "b" * 64,
             "layerDigests": ["sha256:" + "c" * 64]}
    file = tmp_path / "build-amd64.json"
    file.write_text(json.dumps(build))
    assert k.load_build(tmp_path, "amd64", result)["configDigest"] == "sha256:" + "b" * 64
    build["dirtyDiffSha256"] = "different"
    file.write_text(json.dumps(build))
    with pytest.raises(ValueError):
        k.load_build(tmp_path, "amd64", result)


@pytest.mark.parametrize("mutation", [
    lambda p: p["spec"]["containers"][0].update(imagePullPolicy="IfNotPresent"),
    lambda p: p["spec"]["containers"][0].update(image="different:amd64"),
    lambda p: p["status"]["containerStatuses"][0].update(imageID="sha256:" + "f" * 64),
    lambda p: p["status"]["containerStatuses"][0].update(ready=False),
    lambda p: p["spec"].update(automountServiceAccountToken=True),
    lambda p: p["spec"].update(hostNetwork=True),
    lambda p: p["spec"]["containers"][0]["securityContext"].update(allowPrivilegeEscalation=True),
    lambda p: p["spec"]["volumes"].append({"name": "host", "hostPath": {"path": "/"}}),
    lambda p: p["spec"]["containers"][0]["volumeMounts"][2].update(readOnly=False),
])
def test_pod_identity_cannot_fall_back_to_a_registry_image(tmp_path, mutation):
    k = module()
    cluster = k.Cluster(tmp_path / "owned-kubeconfig", CONTEXT, "unit", "amd64", tmp_path)
    cluster.expected_image = "oscar-under-test:amd64"
    cluster.build = {"configDigest": "sha256:" + "b" * 64, "manifestDigest": "sha256:" + "a" * 64}
    pod = one(render_chart(k.image_values("oscar-under-test:amd64")), "Deployment")["spec"]["template"]
    pod["metadata"] = {"name": "owned-pod", "uid": "owned-uid"}
    pod["status"] = {"containerStatuses": [{"ready": True, "imageID": "containerd://sha256:" + "b" * 64}]}
    cluster.get = lambda *a, **kw: {"items": [pod]}
    assert cluster.pod("first") == pod
    mutation(pod)
    with pytest.raises(ValueError):
        cluster.pod("first")


@pytest.mark.parametrize("meta", [
    {"uid": "different", "labels": {"io.docker-oscar.ci-run": "unit"}},
    {"uid": "owned", "labels": {"io.docker-oscar.ci-run": "other"}},
    {"uid": "owned", "labels": {"io.docker-oscar.ci-run": "unit"}, "deletionTimestamp": "now"},
])
def test_namespace_guard_refuses_replacement_or_foreign_owner(tmp_path, meta):
    k = module()
    cluster = k.Cluster(tmp_path / "owned-kubeconfig", CONTEXT, "unit", "amd64", tmp_path)
    cluster.namespace_uid = "owned"
    cluster.guard_cluster = lambda: None  # Remote cluster-marker gate is tested independently.
    cluster.get = lambda *a, **kw: {"metadata": meta}
    with pytest.raises(ValueError, match="namespace"):
        cluster.guard_namespace()
