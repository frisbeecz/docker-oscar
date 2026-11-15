"""Workflow sequencing against an in-memory remote API model, not a cluster PASS."""
import copy

import pytest

from .conftest import API, render_chart
from .test_kubernetes import audit, claim_items, module


class RemoteModel:
    """External cluster/desktop model: tests the real smoke orchestrator's gates."""
    namespace = "test-ns"

    def __init__(self, *, lose_claim=False):
        self.events = []
        self.gateway = False
        self.objects = {}
        self.claim_state = None
        self.lose_claim = lose_claim
        self.generation = 0

    def fresh_preflight(self):
        self.events.append("fresh-preflight")
        assert not self.gateway

    def create_namespace(self):
        self.events.append("namespace-created")

    def deploy(self, release, values, *, upgrade=False):
        self.events.append(("deploy", release, upgrade))
        docs = render_chart(values, (API,) if self.gateway else (), release=release)
        if self.claim_state is None:
            assert values == {"image": {"repository": "oscar-under-test", "tag": "amd64",
                                        "digest": "", "pullPolicy": "Never"}}
            self.claim_state = module().claim_snapshot(claim_items(), namespace="test-ns", release="first")
        if release == "second":
            assert not any(d["kind"] == "PersistentVolumeClaim" for d in docs)
        updated = {}
        for d in docs:
            if d["kind"] in ("Ingress", "HTTPRoute"):
                kind = d["kind"].lower()
                self.generation += 1
                updated[kind] = {"uid": self.objects.get(kind, {}).get("uid", str(self.generation)),
                                 "spec": d["spec"]}
        self.objects = updated

    def claims(self, release=None):
        return copy.deepcopy(self.claim_state)

    def application(self, release, phase, tag):
        self.events.append(("gui", release, phase))
        assert phase == ("create" if tag == "create" else "verify")
        return audit()

    def replace_pod(self, release):
        self.events.append("pod-replaced")
        return {"before": "old", "after": "new", "imageID": "synthetic-unit-fixture"}

    def uninstall(self, release):
        self.events.append(("uninstall", release))
        self.objects = {}
        if self.lose_claim:
            self.claim_state["config"]["uid"] = "unexpected-replacement"

    def install_gateway(self, crd):
        self.events.append("gateway-installed")
        self.gateway = True

    def route(self, kind):
        return copy.deepcopy(self.objects[kind])

    def get(self, kind):
        return {"items": [self.objects[kind]] if kind in self.objects else []}

    def cleanup(self):
        self.events.append("owned-namespace-deleted")


def test_smoke_orchestration_orders_all_gates():
    k = module()
    model = RemoteModel()
    result = {"checks": {}}
    k.exercise_cluster(model, result, "oscar-under-test:amd64", None)
    assert result["checks"] == {
        "freshInstallWithoutGateway": True, "applicationSurvivesPodReplacement": True,
        "uninstallPreservesClaims": True, "reinstallWithExistingClaims": True,
        "routesIndependent": True, "pvcUidAndOwnershipPreserved": True, "ownedNamespaceCleaned": True}
    assert result["claimsBefore"] == result["claimsAfter"]
    assert model.events.index("gateway-installed") > model.events.index(("gui", "second", "verify"))
    assert model.events.index("pod-replaced") > model.events.index(("gui", "first", "create"))
    assert model.events[-2:] == [("uninstall", "second"), "owned-namespace-deleted"]


def test_pvc_identity_failure_stops_before_reuse_or_crd_mutation():
    k = module()
    model = RemoteModel(lose_claim=True)
    result = {"checks": {}}
    with pytest.raises(ValueError, match="PVC UID"):
        k.exercise_cluster(model, result, "oscar-under-test:amd64", None)
    assert "gateway-installed" not in model.events
    assert ("deploy", "second", False) not in model.events
    assert "owned-namespace-deleted" not in model.events
