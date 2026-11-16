"""Real chart publication protocol against an in-memory registry boundary."""
import base64
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import threading
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import pytest


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "oscar-0.1.0.tgz"
    with tarfile.open(path, "w:gz") as tar:
        data = b'apiVersion: v2\nname: oscar\nversion: 0.1.0\nappVersion: "2.1.1"\n'
        member = tarfile.TarInfo("oscar/Chart.yaml")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    return path


class Reply(io.BytesIO):
    def __init__(self, body=b"", status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class Registry:
    """Untagged manifests are deliberately never readable."""
    prefix = "/v2/frisbeecz/charts/oscar"

    def __init__(self):
        self.blobs = {}
        self.manifest = None
        self.calls = []
        self.failure = None
        self.location = self.prefix + "/blobs/uploads/one?state=opaque"
        self.corrupt = None
        self.redirect = None
        self.redirect_body = b""
        self.cdn_reads = 0

    def open(self, request, timeout):
        assert timeout == 120
        url = urlsplit(request.full_url)
        assert url.scheme == "https"
        if url.netloc == "pkg-containers.githubusercontent.com":
            assert request.get_header("Authorization") is None
            self.cdn_reads += 1
            return Reply(self.blobs[url.path.rsplit("/", 1)[-1]])
        assert url.netloc == "ghcr.io"
        method, path = request.get_method(), url.path
        self.calls.append((method, path))
        if self.failure and (method, path) == self.failure[:2]:
            return Reply(b'{"errors":[{"code":"DENIED"}]}', self.failure[2])
        if path == "/token":
            assert parse_qs(url.query) == {
                "service": ["ghcr.io"], "scope": ["repository:frisbeecz/charts/oscar:pull,push"]}
            assert request.get_header("Authorization") == "Basic " + base64.b64encode(b"actor:secret").decode()
            return Reply(b'{"token":"registry-secret"}')
        assert request.get_header("Authorization") == "Bearer registry-secret"
        if path == self.prefix + "/manifests/0.1.0":
            if method == "PUT":
                self.manifest = request.data
                doc = json.loads(self.manifest)
                assert doc["config"]["mediaType"] == "application/vnd.cncf.helm.config.v1+json"
                assert doc["layers"][0]["mediaType"] == "application/vnd.cncf.helm.chart.content.v1.tar+gzip"
                assert len(doc["layers"]) == 1
                for entry in [doc["config"], *doc["layers"]]:
                    assert entry["size"] == len(self.blobs[entry["digest"]])
                return Reply(status=201, headers={"Docker-Content-Digest": digest(self.manifest)})
            return Reply(self.manifest, headers={"Docker-Content-Digest": digest(self.manifest)}) if self.manifest else Reply(status=404)
        if path.startswith(self.prefix + "/manifests/"):
            return Reply(status=404)
        if path == self.prefix + "/blobs/uploads/" and method == "POST":
            return Reply(status=202, headers={"Location": self.location})
        if path == urlsplit(self.location).path and method == "PUT":
            query = parse_qs(url.query)
            # Registry-provided URL/query is opaque; only digest is appended.
            target = urljoin("https://ghcr.io", self.location)
            separator = "&" if urlsplit(target).query else "?"
            assert request.full_url == target + separator + urlencode({"digest": digest(request.data)})
            assert query["digest"] == [digest(request.data)]
            self.blobs[query["digest"][0]] = request.data
            return Reply(status=201, headers={"Docker-Content-Digest": digest(request.data)})
        if path.startswith(self.prefix + "/blobs/") and method == "GET":
            if self.redirect:
                return Reply(self.redirect_body, status=307,
                             headers={"Location": self.redirect + path.rsplit("/", 1)[-1]})
            data = self.blobs[path.rsplit("/", 1)[-1]]
            if self.corrupt == "chart" and data[:2] == b"\x1f\x8b":
                data += b"corrupt"
            if self.corrupt == "config" and data[:1] == b"{":
                data += b"corrupt"
            return Reply(data)
        raise AssertionError((method, path))


@pytest.fixture
def registry(monkeypatch):
    registry = Registry()
    # Only the HTTP boundary is replaced; all artifact/auth/integrity code runs.
    monkeypatch.setattr("urllib.request.OpenerDirector.open",
                        lambda opener, request, timeout: registry.open(request, timeout))
    return registry


def publish(package):
    module = importlib.import_module("ci.chart_registry")
    return module.publish_chart(package, sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
                                version="0.1.0", username="actor", token="secret")


def test_chart_can_be_published_when_untagged_manifests_are_unreadable(package, registry):
    result = publish(package)
    assert result == digest(registry.manifest)
    assert not any("/manifests/sha256:" in path for _, path in registry.calls)
    doc = json.loads(registry.manifest)
    assert doc["schemaVersion"] == 2
    assert registry.blobs[doc["layers"][0]["digest"]] == package.read_bytes()
    assert json.loads(registry.blobs[doc["config"]["digest"]]) == {
        "apiVersion": "v2", "name": "oscar", "version": "0.1.0", "appVersion": "2.1.1"}


@pytest.mark.parametrize("origin", ["", "https://ghcr.io"])
@pytest.mark.parametrize("query", ["", "?state=opaque%2Bvalue%3D&part=one&part=two"])
def test_ghcr_singular_upload_location_preserves_tested_chart(package, registry, origin, query):
    # GHCR HTTP transcript: POST /blobs/uploads/ returns /blobs/upload/<uuid>.
    # https://gist.github.com/shizhMSFT/b77f2d7f993268a1bdd45a7462866906
    path = Registry.prefix + "/blobs/upload/7d8507d3-d549-4fad-9113-aaea462eeb23"
    registry.location = origin + path + query
    assert publish(package) == digest(registry.manifest)
    doc = json.loads(registry.manifest)
    assert registry.blobs[doc["layers"][0]["digest"]] == package.read_bytes()
    assert registry.calls.count(("PUT", path)) == 2


@pytest.mark.parametrize("corrupt", ["chart", "config"])
def test_downloaded_chart_and_config_must_match_published_bytes(package, registry, corrupt):
    registry.corrupt = corrupt
    with pytest.raises(ValueError, match="(checksum|size|bytes)"):
        publish(package)


@pytest.mark.parametrize("body", [b"", b"redirect explanation" * 100])
def test_ghcr_blob_cdn_redirect_strips_registry_credentials(package, registry, body):
    registry.redirect = "https://pkg-containers.githubusercontent.com/ghcr1/blobs/"
    registry.redirect_body = body
    assert publish(package) == digest(registry.manifest)
    assert registry.cdn_reads == 2


@pytest.mark.parametrize("target", [
    "https://attacker.invalid/", "http://pkg-containers.githubusercontent.com/",
    "https://actor:secret@pkg-containers.githubusercontent.com/",
])
def test_blob_redirect_rejects_unapproved_destination(package, registry, target):
    registry.redirect = target
    with pytest.raises(ValueError, match="blob redirect"):
        publish(package)
    assert registry.cdn_reads == 0


def test_existing_chart_tag_is_not_overwritten(package, registry):
    registry.manifest = b'{"schemaVersion":2}'
    with pytest.raises(ValueError, match="already exists"):
        publish(package)
    assert all(method == "GET" for method, _ in registry.calls)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_registry_failure_stops_without_retry(package, registry, status):
    registry.failure = ("POST", Registry.prefix + "/blobs/uploads/", status)
    with pytest.raises(ValueError, match=f"HTTP {status}"):
        publish(package)
    assert registry.calls[-1] == registry.failure[:2]
    assert registry.calls.count(registry.failure[:2]) == 1
    assert registry.manifest is None


@pytest.mark.parametrize("location", [
    "https://attacker.invalid/upload", "//attacker.invalid/upload",
    "http://ghcr.io/v2/frisbeecz/charts/oscar/blobs/uploads/one",
    "/v2/another/repo/blobs/uploads/one", "/token",
    "https://actor:secret@ghcr.io/v2/frisbeecz/charts/oscar/blobs/uploads/one",
    Registry.prefix + "/blobs/uploads/one?digest=sha256:bad",
    "https://attacker.invalid/v2/frisbeecz/charts/oscar/blobs/upload/one",
    "http://ghcr.io/v2/frisbeecz/charts/oscar/blobs/upload/one",
    "https://actor:secret@ghcr.io/v2/frisbeecz/charts/oscar/blobs/upload/one",
    "/v2/another/repo/blobs/upload/one",
    Registry.prefix + "/blobs/upload/../manifests/0.1.0",
    Registry.prefix + "/blobs/upload/one?digest=sha256:bad",
    Registry.prefix + "/blobs/upload/one#fragment",
])
def test_upload_location_cannot_leak_credentials(package, registry, location):
    registry.location = location
    with pytest.raises(ValueError, match="upload location"):
        publish(package)
    assert registry.calls[-1][0] == "POST"


def test_modified_package_is_rejected_before_network(package, registry):
    module = importlib.import_module("ci.chart_registry")
    with pytest.raises(ValueError, match="checksum"):
        module.publish_chart(package, sha256="0" * 64, version="0.1.0", username="actor", token="secret")
    assert registry.calls == []


@pytest.mark.parametrize("version", ["0.1.1", "0.1.0/../../other", "0.1.0?overwrite=true"])
def test_chart_identity_is_checked_before_network(package, registry, version):
    module = importlib.import_module("ci.chart_registry")
    with pytest.raises(ValueError, match="version"):
        module.publish_chart(package, sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
                             version=version, username="actor", token="secret")
    assert registry.calls == []


def test_real_http_redirect_does_not_forward_authorization():
    module = importlib.import_module("ci.chart_registry")
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            self.send_response(307)
            self.send_header("Location", "/stolen")
            self.end_headers()

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with pytest.raises(ValueError, match="HTTP 307"):
                module._request("GET", f"http://127.0.0.1:{server.server_address[1]}/private",
                                "Bearer synthetic")
        finally:
            server.shutdown()
            thread.join()
    assert requests == [("/private", "Bearer synthetic")]


@contextmanager
def public_registry(registry):
    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.do_GET(head=True)

        def do_GET(self, head=False):
            if "/manifests/" in self.path:
                raw, media = registry.manifest, "application/vnd.oci.image.manifest.v1+json"
            elif "/blobs/" in self.path:
                raw, media = registry.blobs[self.path.rsplit("/", 1)[-1]], "application/octet-stream"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Docker-Content-Digest", digest(raw))
            self.end_headers()
            if not head:
                self.wfile.write(raw)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("version", ["3.19.0", "4.3.2"])
def test_real_helm_pulls_exact_original_chart(package, registry, tmp_path, version):
    publish(package)
    # Native Helm, no mocked subprocess or chart consumer.
    local = Path(__file__).resolve().parents[2] / ".venv/tools/bin" / ("helm-" + version)
    helm = str(local) if local.is_file() else shutil.which("helm-" + version)
    assert helm, "Helm is required for chart publication compatibility verification"
    actual = subprocess.run([helm, "version", "--short"], capture_output=True, text=True, check=True)
    assert actual.stdout.startswith("v" + version + "+")
    destination = tmp_path / "download"
    destination.mkdir()
    with public_registry(registry) as port:
        result = subprocess.run([
            helm, "pull", f"oci://127.0.0.1:{port}/frisbeecz/charts/oscar",
            "--version", "0.1.0", "--plain-http", "--destination", str(destination),
            "--registry-config", str(tmp_path / "helm-auth.json"),
        ], capture_output=True, text=True, env={**os.environ, "DOCKER_CONFIG": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert (destination / package.name).read_bytes() == package.read_bytes()
