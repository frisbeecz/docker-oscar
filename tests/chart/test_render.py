"""Chart contracts, not YAML substring tests. SPDX-License-Identifier: Apache-2.0."""
import pytest

from .conftest import (API, config_claim_reference, config_pvc, helm_result, one,
                       pvc_names, render_chart, routes)


def test_defaults():
    docs = render_chart({})
    assert sorted(d["kind"] for d in docs) == sorted([
        "Deployment", "Service", "ServiceAccount", *["PersistentVolumeClaim"] * 3])
    deployment = one(docs, "Deployment")
    assert deployment["spec"]["replicas"] == 1
    assert deployment["spec"]["strategy"] == {"type": "Recreate"}
    assert pvc_names(docs) == {"demo-oscar-config-v2", "demo-oscar-data-v2", "demo-oscar-sdcard-v2"}
    for role, size in [("config", "1Gi"), ("data", "5Gi"), ("sdcard", "2Gi")]:
        pvc = next(d for d in docs if d["metadata"]["name"] == f"demo-oscar-{role}-v2")
        assert pvc["spec"] == {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": size}}}
        assert pvc["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep"
    service = one(docs, "Service")
    assert service["spec"]["type"] == "ClusterIP"
    assert service["spec"]["ports"] == [{"name": "http", "port": 3000, "targetPort": "http", "protocol": "TCP"}]


@pytest.mark.parametrize("ingress,gateway", [(False, False), (True, False), (False, True), (True, True)])
def test_route_matrix(ingress, gateway):
    docs = render_chart(routes(ingress, gateway), (API,) if gateway else ())
    assert sum(d["kind"] == "Ingress" for d in docs) == int(ingress)
    assert sum(d["kind"] == "HTTPRoute" for d in docs) == int(gateway)
    service = one(docs, "Service")
    if ingress:
        backend = one(docs, "Ingress")["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]
        assert backend == {"name": service["metadata"]["name"], "port": {"name": "http"}}
    if gateway:
        route = one(docs, "HTTPRoute")
        assert route["apiVersion"] == "gateway.networking.k8s.io/v1"
        assert route["spec"]["parentRefs"] == [{"name": "shared", "sectionName": "https"}]
        assert route["spec"]["rules"][0]["backendRefs"] == [
            {"name": service["metadata"]["name"], "port": service["spec"]["ports"][0]["port"]}]


def test_storage_class_three_states():
    assert "storageClassName" not in config_pvc(None)["spec"]
    assert config_pvc("")["spec"]["storageClassName"] == ""
    assert config_pvc("example-sc")["spec"]["storageClassName"] == "example-sc"


@pytest.mark.parametrize("role", ["data", "sdcard"])
@pytest.mark.parametrize("value", [None, "", "example-sc"])
def test_other_storage_classes(role, value):
    docs = render_chart({"persistence": {role: {"storageClass": value}}})
    spec = next(d["spec"] for d in docs if d["kind"] == "PersistentVolumeClaim"
                and d["metadata"]["name"].endswith(f"-{role}-v2"))
    assert ("storageClassName" in spec) == (value is not None)
    if value is not None:
        assert spec["storageClassName"] == value


def test_existing_claim_is_not_managed():
    docs = render_chart({"persistence": {"config": {"existingClaim": "external-config"}}})
    assert pvc_names(docs) == {"demo-oscar-data-v2", "demo-oscar-sdcard-v2"}
    assert config_claim_reference(docs) == "external-config"
    all_external = render_chart({"persistence": {r: {"existingClaim": f"external-{r}"}
                                                for r in ["config", "data", "sdcard"]}})
    assert pvc_names(all_external) == set()


def test_digest_precedes_tag():
    docs = render_chart({"image": {"tag": "2.1.1-r8", "digest": "sha256:" + "a" * 64}})
    image = one(docs, "Deployment")["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image == "ghcr.io/frisbeecz/docker-oscar@sha256:" + "a" * 64


def test_gateway_api_detection():
    assert helm_result(routes(False, True)).returncode != 0
    missing = helm_result(routes(False, True), ("gateway.networking.k8s.io/v1",))
    assert missing.returncode != 0
    assert "gateway.networking.k8s.io/v1/HTTPRoute" in missing.stderr
    assert render_chart(routes(False, False))


@pytest.mark.parametrize("values", [{}, {"nameOverride": "a" * 63}, {"fullnameOverride": "b" * 63}])
def test_claim_names_long_release(values):
    docs = render_chart(values, release="r" * 53)
    names = pvc_names(docs)
    assert len(names) == 3
    assert all(len(n) <= 63 for n in names)
    assert {n.split("-")[-2] for n in names} == {"config", "data", "sdcard"}
    volumes = one(docs, "Deployment")["spec"]["template"]["spec"]["volumes"]
    assert {v["persistentVolumeClaim"]["claimName"] for v in volumes if "persistentVolumeClaim" in v} == names


def test_security_and_mounts():
    docs = render_chart({})
    pod = one(docs, "Deployment")["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert pod["automountServiceAccountToken"] is False
    assert one(docs, "ServiceAccount")["automountServiceAccountToken"] is False
    assert not pod.get("hostNetwork", False)
    assert all("hostPath" not in v for v in pod["volumes"])
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False, "capabilities": {"drop": ["NET_RAW"]}}
    assert container["volumeMounts"] == [
        {"name": "config", "mountPath": "/config"},
        {"name": "data", "mountPath": "/config/Documents/OSCAR20_Data"},
        {"name": "sdcard", "mountPath": "/config/SDCARD", "readOnly": True},
        {"name": "shm", "mountPath": "/dev/shm"}]
    assert next(v for v in pod["volumes"] if v["name"] == "shm") == {
        "name": "shm", "emptyDir": {"medium": "Memory", "sizeLimit": "512Mi"}}
    env = {e["name"]: e["value"] for e in container["env"]}
    assert env == {"PUID": "1000", "PGID": "1000", "TZ": "Etc/UTC",
                   "PIXELFLUX_WAYLAND": "true", "RESTART_APP": "true", "HARDEN_DESKTOP": "true"}
    for probe, period, threshold in [("startupProbe", 5, 60), ("readinessProbe", 10, 3), ("livenessProbe", 30, 3)]:
        assert container[probe] == {"tcpSocket": {"port": "http"}, "periodSeconds": period,
                                    "timeoutSeconds": 3, "failureThreshold": threshold}


def test_extra_pvc_mounts():
    docs = render_chart({"extraPvcMounts": [
        {"name": "legacy", "claimName": "legacy-copy", "mountPath": "/imports/legacy"},
        {"name": "writable", "claimName": "writable-copy", "mountPath": "/imports/writable", "readOnly": False}]})
    pod = one(docs, "Deployment")["spec"]["template"]["spec"]
    mounts = {m["name"]: m for m in pod["containers"][0]["volumeMounts"]}
    assert mounts["legacy"]["readOnly"] is True
    assert mounts["writable"]["readOnly"] is False
    assert next(v for v in pod["volumes"] if v["name"] == "legacy") == {
        "name": "legacy", "persistentVolumeClaim": {"claimName": "legacy-copy"}}


def test_configurable_objects():
    docs = render_chart({
        "serviceAccount": {"create": False, "name": "external-sa"},
        "env": {"PUID": "1234", "PGID": "2345", "TZ": "Europe/Prague"},
        "envFrom": [{"secretRef": {"name": "desktop-auth"}}, {"configMapRef": {"name": "desktop-settings"}}],
        "imagePullSecrets": [{"name": "registry"}], "nodeSelector": {"example.org/pool": "desktop"},
        "tolerations": [{"key": "desktop", "operator": "Exists", "effect": "NoSchedule"}],
        "affinity": {"nodeAffinity": {"preferredDuringSchedulingIgnoredDuringExecution": []}},
        "readinessProbe": {"tcpSocket": None, "httpGet": {"path": "/", "port": "http"}, "periodSeconds": 17},
        "persistence": {"sdcard": {"readOnly": False}}})
    assert not any(d["kind"] == "ServiceAccount" for d in docs)
    pod = one(docs, "Deployment")["spec"]["template"]["spec"]
    assert pod["serviceAccountName"] == "external-sa"
    assert pod["imagePullSecrets"] == [{"name": "registry"}]
    assert pod["nodeSelector"] == {"example.org/pool": "desktop"}
    assert pod["tolerations"] == [{"key": "desktop", "operator": "Exists", "effect": "NoSchedule"}]
    assert pod["containers"][0]["envFrom"] == [{"secretRef": {"name": "desktop-auth"}},
                                              {"configMapRef": {"name": "desktop-settings"}}]
    assert pod["containers"][0]["readinessProbe"]["httpGet"] == {"path": "/", "port": "http"}


INVALID = [
    {"replicaCount": 0}, {"replicaCount": 2}, {"image": {"repository": ""}},
    {"image": {"repository": "ghcr.io/example/image:tag"}},
    {"image": {"tag": "bad tag"}}, {"image": {"tag": "bad:tag"}},
    {"image": {"digest": "sha256:no"}}, {"image": {"digest": "sha512:" + "a" * 64}},
    {"persistence": {"config": {"size": ""}}}, {"persistence": {"data": {"enabled": False}}},
    {"persistence": {"config": {"readOnly": True}}}, {"persistence": {"data": {"readOnly": True}}},
    {"persistence": {"config": {"size": "0Gi"}}},
    {"ingress": {"enabled": True}}, {"gateway": {"enabled": True}},
    {"env": []}, {"env": {"PASSWORD": 123}}, {"envFrom": [{"secretRef": {"name": ""}}]},
    {"envFrom": [{"secretRef": {"name": "a"}, "configMapRef": {"name": "b"}}]},
    {"startupProbe": "yes"}, {"livenessProbe": {"periodSeconds": 0}},
    {"readinessProbe": {"tcpSocket": None}}, {"readinessProbe": {"exec": {"command": ["true"]}}},
    *[{"extraPvcMounts": [{"name": "import", "claimName": "copy", "mountPath": p}]}
      for p in ["/config", "/config/SDCARD", "/imports/../config", "/imports/a/../../config",
                "/imports", "/imports/a/b", "/imports/.hidden", "/imports/a..b"]],
    {"extraPvcMounts": [{"name": "config", "claimName": "copy", "mountPath": "/imports/copy"}]},
    {"extraPvcMounts": [{"name": "a", "claimName": "copy", "mountPath": "/imports/a", "hostPath": "/"}]},
    {"extraPvcMounts": [{"name": "a", "claimName": "copy", "mountPath": "/imports/a"},
                       {"name": "a", "claimName": "copy", "mountPath": "/imports/b"}]},
    {"extraPvcMounts": [{"name": "a", "claimName": "copy", "mountPath": "/imports/a"},
                       {"name": "b", "claimName": "copy", "mountPath": "/imports/a"}]},
]


@pytest.mark.parametrize("values", INVALID)
def test_reject_invalid_values(values):
    result = helm_result(values, (API,))
    assert result.returncode != 0, result.stdout
