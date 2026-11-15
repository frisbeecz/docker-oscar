"""Disposable GitHub-runner-only Kubernetes acceptance; never creates a cluster.

Explicit kubeconfig, context, run marker and native image receipt are mandatory.
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

import yaml

from ci import ROOT, load_lock, receipt, run, sha256_file, write_json
from ci.build_image import require_native
from ci.chart import CHART, prepare_schemas, route_values
from ci import gui
from ci.runtime import AUDIT_SCRIPT, PROCESS_SCRIPT, PROFILE, open_page, preflight_tools

OWNER = "io.docker-oscar.ci-run"
ROLES = ("config", "data", "sdcard")
DIGEST = r"sha256:[a-f0-9]{64}"


def validate_kubeconfig(path, context, run_id):
    if not run_id or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", run_id):
        raise ValueError("explicit safe run-id required")
    if not context or context != f"kind-oscar-ci-{run_id}":
        raise ValueError("explicit context must match kind-oscar-ci-RUNID")
    if path is None or not Path(path).is_file():
        raise ValueError("explicit kubeconfig file required; ambient config is forbidden")
    config = yaml.safe_load(Path(path).read_text())
    if not isinstance(config, dict) or config.get("current-context") != context:
        raise ValueError("kubeconfig current-context mismatch")
    if set(config) - {"apiVersion", "kind", "preferences", "current-context", "clusters", "contexts", "users"}:
        raise ValueError("unsupported kubeconfig fields")
    if config.get("apiVersion") != "v1" or config.get("kind") != "Config" or config.get("preferences", {}):
        raise ValueError("only plain kind kubeconfig supported")
    for field in ("clusters", "contexts", "users"):
        entries = config.get(field)
        if (not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict)
                or entries[0].get("name") != context):
            raise ValueError("only a single, explicitly owned context/cluster/user is allowed")
    cluster = config["clusters"][0].get("cluster", {})
    user = config["users"][0].get("user", {})
    ctx = config["contexts"][0].get("context", {})
    if ctx != {"cluster": context, "user": context}:
        raise ValueError("context must bind only the owned cluster and user, without a namespace")
    if set(cluster) != {"server", "certificate-authority-data"}:
        raise ValueError("embedded CA and direct TLS endpoint required; no proxies or external files")
    if set(user) != {"client-certificate-data", "client-key-data"}:
        raise ValueError("embedded kind client certificate required; no exec/auth plugins/tokens/files")
    if any(not isinstance(v, str) or not v for v in [*cluster.values(), *user.values()]):
        raise ValueError("empty or malformed kubeconfig credentials/endpoint")
    url = urlsplit(cluster["server"])
    if (url.scheme != "https" or url.hostname not in {"127.0.0.1", "::1", "localhost"}
            or not url.port or url.port < 1024 or url.username or url.password
            or url.path not in ("", "/") or url.query or url.fragment):
        raise ValueError("only the disposable kind loopback TLS API endpoint is allowed")
    return config


def require_cluster(nodes, marker, run_id, context, arch):
    if marker.get("data") != {"runId": run_id, "context": context, "purpose": "disposable-oscar-ci"}:
        raise ValueError("missing/mismatched disposable CI cluster marker")
    items = nodes.get("items", [])
    if not items:
        raise ValueError("owned native kind nodes required")
    for node in items:
        if node.get("metadata", {}).get("labels", {}).get(OWNER) != run_id:
            raise ValueError("refusing unowned cluster node")
        info = node.get("status", {}).get("nodeInfo", {})
        if info.get("architecture") != arch or info.get("operatingSystem") != "linux":
            raise ValueError("cluster node is not the requested native Linux architecture")


def image_values(image):
    match = re.fullmatch(r"([a-z0-9][a-z0-9./:_-]*):([a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127})", image)
    repository_pattern = json.loads((CHART / "values.schema.json").read_text())[
        "properties"]["image"]["properties"]["repository"]["pattern"]
    if not match or not re.fullmatch(repository_pattern, match[1]):
        raise ValueError("test image must be an explicit repository:tag already loaded into kind")
    return {"image": {"repository": match[1], "tag": match[2], "digest": "", "pullPolicy": "Never"}}


def load_build(directory, arch, identity):
    build = json.loads((Path(directory) / f"build-{arch}.json").read_text())
    if (build.get("exitCode") != 0 or build.get("arch") != arch
            or any(build.get(k) != identity[k] for k in ("gitCommit", "dirtyDiffSha256"))):
        raise ValueError("build receipt must match this exact source state and architecture")
    for digest in [build.get("manifestDigest", ""), build.get("configDigest", ""), *build.get("layerDigests", [])]:
        if not re.fullmatch(DIGEST, digest):
            raise ValueError("invalid native build digest")
    if not build.get("layerDigests"):
        raise ValueError("native build layer identities required")
    return build


def claim_snapshot(items, *, namespace, release=None):
    if len(items) != 3:
        raise ValueError("exactly three retained claims required")
    snapshot = {}
    for role in ROLES:
        matches = [c for c in items if c["metadata"]["name"].endswith(f"-{role}-v2")]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous generation-v2 claim")
        claim = matches[0]
        meta = claim["metadata"]
        annotations = meta.get("annotations", {})
        labels = meta.get("labels", {})
        if (meta.get("namespace") != namespace or not meta.get("uid") or meta.get("deletionTimestamp")
                or claim.get("status", {}).get("phase") != "Bound" or not claim.get("spec", {}).get("volumeName")
                or annotations.get("helm.sh/resource-policy") != "keep"
                or annotations.get("meta.helm.sh/release-namespace") != namespace
                or labels.get("app.kubernetes.io/managed-by") != "Helm"
                or not annotations.get("meta.helm.sh/release-name")
                or (release is not None and annotations.get("meta.helm.sh/release-name") != release)):
            raise ValueError("claim binding/ownership/retention mismatch")
        snapshot[role] = {"name": meta["name"], "uid": meta["uid"], "namespace": namespace,
                          "volumeName": claim["spec"]["volumeName"],
                          "releaseName": annotations["meta.helm.sh/release-name"],
                          "releaseNamespace": annotations["meta.helm.sh/release-namespace"],
                          "managedBy": labels["app.kubernetes.io/managed-by"],
                          "resourcePolicy": annotations["helm.sh/resource-policy"]}
    return snapshot


def compare_claims(before, after):
    if before != after:
        raise ValueError("PVC UID, bound volume or Helm ownership changed")


def reuse_values(snapshot, image):
    values = image_values(image)
    values["persistence"] = {role: {"existingClaim": snapshot[role]["name"]} for role in ROLES}
    return values


def validate_application(before, after):
    for audit in (before, after):
        if (PROFILE not in audit["profiles"] or audit["language"] != "en_US"
                or not audit["data"] or not audit["dataFiles"] or not audit["qtConfig"] or audit["outsideDatabases"]):
            raise ValueError("application profile, separate Qt state or no-fallback audit failed")
        for key, prefix in [("data", "Documents/OSCAR20_Data/"), ("dataFiles", "Documents/OSCAR20_Data/"),
                            ("qtConfig", ".config/")]:
            if any(x["uid"] != 1000 or x["gid"] != 1000 or not x["path"].startswith(prefix) for x in audit[key]):
                raise ValueError("application default UID/GID or persistent path mismatch")
        if any(d["integrity"] != "ok" for d in audit["data"]):
            raise ValueError("SQLite integrity failure")
    for key in ("profiles", "language"):
        if before[key] != after[key]:
            raise ValueError("application-created state did not survive pod replacement")
    for key in ("data", "qtConfig"):
        if [d["path"] for d in before[key]] != [d["path"] for d in after[key]]:
            raise ValueError("separate application/Qt state did not survive pod replacement")


def gui_values(values):
    # First install is actual chart defaults except image/Never. Only subsequent
    # GUI exercises request the same deterministic software desktop as Task 1.
    values = copy.deepcopy(values)
    values["env"] = {"LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8", "SELKIES_USE_CPU": "true",
                     "SELKIES_ENCODER": "h264enc", "SELKIES_MANUAL_RESOLUTION": "true",
                     "SELKIES_MANUAL_WIDTH": "1280", "SELKIES_MANUAL_HEIGHT": "800"}
    return values


class Cluster:
    def __init__(self, kubeconfig, context, run_id, arch, artifacts):
        self.kubeconfig, self.context, self.run_id, self.arch = str(kubeconfig), context, run_id, arch
        self.artifacts = Path(artifacts)
        self.namespace = f"oscar-ci-{run_id[:32]}-{uuid.uuid4().hex[:10]}"
        self.namespace_uid = None
        self.commands = []
        self.env = {k: v for k, v in os.environ.items()
                    if k.upper() not in {"KUBECONFIG", "KUBERNETES_MASTER", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
        self.env.update(KUBECONFIG=self.kubeconfig, NO_PROXY="127.0.0.1,localhost,::1",
                        no_proxy="127.0.0.1,localhost,::1")
        self.expected_image = None
        self.build = None

    def invoke(self, command, **kwargs):
        entry = {"command": [str(x) for x in command], "cwd": str(ROOT), "exitCode": None}
        self.commands.append(entry)
        try:
            completed = run(command, env=self.env, capture_output=True, text=True, timeout=600, **kwargs)
        except subprocess.CalledProcessError as error:
            entry["exitCode"] = error.returncode
            (self.artifacts / f"command-{len(self.commands):03d}.log").write_text(
                (error.stdout or "") + (error.stderr or ""))
            raise
        else:
            entry["exitCode"] = completed.returncode
            (self.artifacts / f"command-{len(self.commands):03d}.log").write_text(completed.stdout + completed.stderr)
            return completed.stdout.strip()

    def kubectl(self, *args):
        return self.invoke(["kubectl", "--kubeconfig", self.kubeconfig, "--context", self.context,
                            "--request-timeout=360s", *args])

    def helm(self, *args):
        return self.invoke(["helm", "--kubeconfig", self.kubeconfig, "--kube-context", self.context, *args])

    def get(self, resource, name=None, *, cluster=False, extra=()):
        return json.loads(self.kubectl("get", resource, *([name] if name else []),
                                      *([] if cluster else ["-n", self.namespace]), *extra, "-o", "json"))

    def guard_cluster(self):
        require_cluster(self.get("nodes", cluster=True),
                        json.loads(self.kubectl("get", "configmap", "oscar-ci-owner", "-n", "kube-system",
                                                "-o", "json")),
                        self.run_id, self.context, self.arch)

    def fresh_preflight(self):
        self.guard_cluster()
        crds = self.get("crd", cluster=True)["items"]
        if any(c["spec"]["group"] == "gateway.networking.k8s.io" for c in crds):
            raise ValueError("fresh-install gate requires a disposable cluster without Gateway API CRDs")

    def create_namespace(self):
        self.guard_cluster()
        file = self.artifacts / "namespace.yaml"
        file.write_text(yaml.safe_dump({"apiVersion": "v1", "kind": "Namespace", "metadata": {
            "name": self.namespace, "labels": {OWNER: self.run_id}}}))
        self.kubectl("create", "-f", str(file))
        self.namespace_uid = self.get("namespace", self.namespace, cluster=True)["metadata"]["uid"]
        self.guard_namespace()

    def guard_namespace(self):
        self.guard_cluster()
        ns = self.get("namespace", self.namespace, cluster=True)["metadata"]
        if (self.namespace_uid is None or ns.get("uid") != self.namespace_uid
                or ns.get("labels", {}).get(OWNER) != self.run_id or ns.get("deletionTimestamp")):
            raise ValueError("refusing mutation of an unowned/replaced namespace")

    def deploy(self, release, values, *, upgrade=False):
        self.guard_namespace()
        file = self.artifacts / f"{release}-{len(self.commands):03d}.values.yaml"
        file.write_text(yaml.safe_dump(values))
        self.helm("upgrade" if upgrade else "install", release, str(CHART), "-n", self.namespace,
                  "-f", str(file), "--wait", "--timeout", "300s")
        self.wait_pod(release)

    def wait_pod(self, release):
        self.kubectl("rollout", "status", f"deployment/{release}-oscar", "-n", self.namespace, "--timeout=300s")
        self.kubectl("wait", "pod", "-n", self.namespace, "-l", f"app.kubernetes.io/instance={release}",
                     "--for=condition=Ready", "--timeout=300s")
        pod = self.pod(release)
        for role in ROLES:
            volume = next(v for v in pod["spec"]["volumes"] if v["name"] == role)
            claim = self.get("pvc", volume["persistentVolumeClaim"]["claimName"])
            if claim.get("status", {}).get("phase") != "Bound":
                raise ValueError("persistent claim not bound")
        return pod

    def pod(self, release):
        items = self.get("pods", extra=("-l", f"app.kubernetes.io/instance={release}"))["items"]
        pods = [p for p in items if not p["metadata"].get("deletionTimestamp")]
        if len(pods) != 1:
            raise ValueError("exactly one owned application pod required")
        pod = pods[0]
        container = pod["spec"]["containers"][0]
        statuses = pod.get("status", {}).get("containerStatuses", [])
        if (len(pod["spec"]["containers"]) != 1 or len(statuses) != 1 or not statuses[0].get("ready")
                or container["image"] != self.expected_image or container["imagePullPolicy"] != "Never"):
            raise ValueError("ready singleton with exact local image and Never pull policy required")
        spec = pod["spec"]
        security = container.get("securityContext", {})
        mounts = {m["name"]: m for m in container.get("volumeMounts", [])}
        volumes = {v["name"]: v for v in spec.get("volumes", [])}
        if (spec.get("automountServiceAccountToken") is not False or spec.get("hostNetwork", False)
                or spec.get("hostPID", False) or spec.get("hostIPC", False)
                or security.get("allowPrivilegeEscalation") is not False or security.get("privileged", False)
                or "NET_RAW" not in security.get("capabilities", {}).get("drop", [])
                or security.get("capabilities", {}).get("add")
                or any("hostPath" in v for v in volumes.values())):
            raise ValueError("pod security contract mismatch")
        for role, path in [("config", "/config"), ("data", "/config/Documents/OSCAR20_Data"),
                           ("sdcard", "/config/SDCARD")]:
            mount = mounts.get(role, {})
            if (mount.get("mountPath") != path or mount.get("readOnly", False) != (role == "sdcard")
                    or not volumes.get(role, {}).get("persistentVolumeClaim", {}).get("claimName")
                    or mount.get("subPath") or mount.get("subPathExpr")):
                raise ValueError("pod persistent mount contract mismatch")
        image_id = statuses[0]["imageID"]
        digest = re.search(DIGEST + r"$", image_id)
        if not digest or digest[0] not in {self.build["configDigest"], self.build["manifestDigest"]}:
            raise ValueError("running pod imageID is not the natively built OCI config/manifest")
        return pod

    def claims(self, release=None):
        return claim_snapshot(self.get("pvc")["items"], namespace=self.namespace, release=release)

    def uninstall(self, release):
        self.guard_namespace()
        self.helm("uninstall", release, "-n", self.namespace, "--wait", "--timeout", "300s")

    def replace_pod(self, release):
        self.guard_namespace()
        pod = self.pod(release)
        self.kubectl("delete", "pod", pod["metadata"]["name"], "-n", self.namespace, "--wait=true", "--timeout=180s")
        after = self.wait_pod(release)
        if pod["metadata"]["uid"] == after["metadata"]["uid"]:
            raise ValueError("pod replacement did not occur")
        return {"before": pod["metadata"]["uid"], "after": after["metadata"]["uid"],
                "imageID": after["status"]["containerStatuses"][0]["imageID"]}

    @contextmanager
    def port_forward(self, pod, tag):
        log_file = self.artifacts / f"{tag}.port-forward.log"
        command = ["kubectl", "--kubeconfig", self.kubeconfig, "--context", self.context, "-n", self.namespace,
                   "port-forward", f"pod/{pod}", "--address", "127.0.0.1", ":3000"]
        entry = {"command": command, "cwd": str(ROOT), "exitCode": None}
        self.commands.append(entry)
        with log_file.open("w") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=self.env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("owned pod port-forward terminated before readiness")
                    match = re.search(r"Forwarding from 127\.0\.0\.1:([0-9]+) -> 3000", log_file.read_text())
                    if match:
                        url = "http://127.0.0.1:" + match[1]
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError("owned port-forward startup timed out")
                    time.sleep(0.1)
                while True:
                    try:
                        with urllib.request.urlopen(url, timeout=3) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, TimeoutError):
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError("forwarded Selkies service not ready")
                    time.sleep(0.2)
                yield url
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                entry["exitCode"] = process.returncode
                entry["terminatedByHarness"] = True

    def application(self, release, phase, tag):
        from playwright.sync_api import sync_playwright
        pod = self.pod(release)["metadata"]["name"]
        frames = []
        with self.port_forward(pod, tag) as url, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--disable-gpu"])
            context = browser.new_context(viewport={"width": 1280, "height": 800},
                                          device_scale_factor=1, locale="en-US")
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            try:
                page = open_page(context, url, frames)
                evidence = gui.exercise(page, phase, PROFILE, self.artifacts / tag)
                if sum(f["mediaFrames"] for f in frames) < 1:
                    raise ValueError("no actual Selkies WebSocket media frames")
                processes = json.loads(self.kubectl("exec", pod, "-n", self.namespace, "--",
                                                    "python3", "-c", PROCESS_SCRIPT))
                if len(processes) != 1 or processes[0]["uid"] != 1000 or processes[0]["gid"] != 1000:
                    raise ValueError("exactly one default unprivileged OSCAR process required")
                audit = json.loads(self.kubectl("exec", pod, "-n", self.namespace, "--",
                                               "python3", "-c", AUDIT_SCRIPT))
                validate_application(audit, audit)
                write_json(self.artifacts / f"{tag}.json", {"gui": evidence, "audit": audit, "websockets": frames})
                return audit
            finally:
                context.tracing.stop(path=str(self.artifacts / f"{tag}.trace.zip"))
                context.close()
                browser.close()

    def install_gateway(self, crd):
        self.guard_namespace()
        pin = load_lock("ci/tools.lock.json")["schemas"]["gateway"]
        if sha256_file(crd) != pin["sha256"]:
            raise ValueError("Gateway CRD checksum mismatch")
        docs = [doc for doc in yaml.safe_load_all(crd.read_text()) if doc]
        crds = []
        for doc in docs:
            kind, version = doc.get("kind"), doc.get("apiVersion")
            name = doc.get("metadata", {}).get("name", "")
            if (kind == "CustomResourceDefinition" and version == "apiextensions.k8s.io/v1"
                    and name.endswith(".gateway.networking.k8s.io")):
                crds.append(name)
            elif (kind in {"ValidatingAdmissionPolicy", "ValidatingAdmissionPolicyBinding"}
                  and version == "admissionregistration.k8s.io/v1"
                  and name == "safe-upgrades.gateway.networking.k8s.io"):
                pass  # Keep upstream upgrade-safety policies; these are not CRDs.
            else:
                raise ValueError("unexpected object in pinned standard Gateway bundle")
        # Validate the complete inventory before the first cluster mutation.
        # Upstream documents server-side apply for its standard install bundle.
        self.kubectl("apply", "--server-side", "-f", str(crd))
        for name in crds:
            self.kubectl("wait", f"crd/{name}", "--for=condition=Established", "--timeout=60s")

    def route(self, kind):
        doc = self.get(kind, "second-oscar")
        return {"uid": doc["metadata"]["uid"], "spec": doc["spec"]}

    def cleanup(self):
        self.guard_namespace()
        self.kubectl("delete", "namespace", self.namespace, "--wait=true", "--timeout=180s")


def exercise_cluster(cluster, result, image, crd):
    cluster.fresh_preflight()
    cluster.create_namespace()
    result["namespace"] = cluster.namespace
    values = image_values(image)
    cluster.deploy("first", values)
    baseline = cluster.claims(release="first")
    result["claimsBefore"] = baseline
    result["checks"]["freshInstallWithoutGateway"] = True
    values = gui_values(values)
    cluster.deploy("first", values, upgrade=True)
    first = cluster.application("first", "create", "create")
    result["podReplacement"] = cluster.replace_pod("first")
    second = cluster.application("first", "verify", "after-replacement")
    validate_application(first, second)
    result["checks"]["applicationSurvivesPodReplacement"] = True
    cluster.uninstall("first")
    compare_claims(baseline, cluster.claims())
    result["checks"]["uninstallPreservesClaims"] = True
    reused = gui_values(reuse_values(baseline, image))
    cluster.deploy("second", reused)
    compare_claims(baseline, cluster.claims())
    validate_application(first, cluster.application("second", "verify", "after-reuse"))
    result["checks"]["reinstallWithExistingClaims"] = True
    cluster.install_gateway(crd)
    both = {**reused, **route_values(True, True)}
    cluster.deploy("second", both, upgrade=True)
    route = cluster.route("httproute")
    cluster.route("ingress")
    cluster.deploy("second", {**reused, **route_values(False, True)}, upgrade=True)
    if cluster.route("httproute") != route:
        raise ValueError("disabling ingress changed HTTPRoute identity/spec")
    if cluster.get("ingress")["items"]:
        raise ValueError("disabled ingress still exists")
    cluster.deploy("second", both, upgrade=True)
    ingress = cluster.route("ingress")
    cluster.deploy("second", {**reused, **route_values(True, False)}, upgrade=True)
    if cluster.route("ingress") != ingress:
        raise ValueError("disabling gateway changed Ingress identity/spec")
    if cluster.get("httproute")["items"]:
        raise ValueError("disabled HTTPRoute still exists")
    result["checks"]["routesIndependent"] = True
    cluster.uninstall("second")
    final = cluster.claims()
    compare_claims(baseline, final)
    result["claimsAfter"] = final
    result["checks"]["pvcUidAndOwnershipPreserved"] = True
    cluster.cleanup()
    result["checks"]["ownedNamespaceCleaned"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args(argv)
    config = validate_kubeconfig(args.kubeconfig, args.context, args.run_id)
    image_values(args.image)
    arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    require_native(arch)
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("Kubernetes acceptance is restricted to disposable GitHub-hosted native runners")
    args.artifacts = args.artifacts.resolve()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    target = args.artifacts / "kubernetes.json"
    if target.exists():
        raise FileExistsError("refusing to overwrite existing Kubernetes receipt")
    result = receipt(command=[sys.executable, "-m", "ci.kubernetes", *(sys.argv[1:] if argv is None else argv)])
    cluster = None
    try:
        preflight_tools()
        tools = load_lock("ci/tools.lock.json")
        version = run(["helm", "version", "--short"], capture_output=True, text=True).stdout.strip()
        if not any(re.fullmatch(r"v" + re.escape(v) + r"(?:\+.*)?", version) for v in tools["helm"]):
            raise ValueError("unsupported Helm version")
        build = load_build(args.artifacts, arch, result)
        result.update(arch=arch, image=args.image, runId=args.run_id,
                      manifestDigest=build["manifestDigest"], configDigest=build["configDigest"],
                      layerDigests=build["layerDigests"], buildReceiptSha256=sha256_file(
                          args.artifacts / f"build-{arch}.json"))
        schemas = prepare_schemas(ROOT / "artifacts/chart/schemas")
        crd = Path(schemas["HTTPRoute"]["path"]).parent / "gateway-standard.yaml"
        # Freeze validated credentials in a private temporary file: no later
        # kubeconfig edits, external auth plugins, or ambient context fallback.
        with tempfile.TemporaryDirectory(prefix="owned-kube-", dir=args.artifacts) as directory:
            private_config = Path(directory) / "kubeconfig"
            private_config.write_text(yaml.safe_dump(config))
            private_config.chmod(0o600)
            cluster = Cluster(private_config, args.context, args.run_id, arch, args.artifacts)
            cluster.expected_image, cluster.build = args.image, build
            exercise_cluster(cluster, result, args.image, crd)
        result["exitCode"] = 0
    except Exception as error:
        # Do not keep mutating after a failed infra/permission/runtime gate.
        # The owning disposable runner tears down its cluster. Port-forwards
        # always terminate via their context manager, even when GUI checks fail.
        result.update(exitCode=1, error=f"{type(error).__name__}: {error}",
                      cleanup="No failure-path cluster mutation; disposable runner must destroy its cluster")
        raise
    finally:
        if cluster is not None:
            result["commands"] = cluster.commands
            result["namespace"] = cluster.namespace
        write_json(target, result)


if __name__ == "__main__":
    main()
