"""Docker Hub metadata and the fixed, already-tested image migration."""
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError

import pytest


def product():
    return importlib.import_module("ci.dockerhub")


@pytest.fixture
def hub(monkeypatch):
    module = product()
    state = {"repository": None, "calls": [], "tag": None}

    def request(_opener, req, **kwargs):
        assert kwargs["timeout"] == 60
        assert req.full_url.startswith("https://hub.docker.com/v2/")
        method = req.get_method()
        path = req.full_url.removeprefix("https://hub.docker.com")
        data = json.loads(req.data) if req.data else None
        auth = req.get_header("Authorization")
        state["calls"].append((method, path, data, auth))
        if path == "/v2/auth/token":
            assert method == "POST" and auth is None
            assert data == {"identifier": "frisbeecz24", "secret": "synthetic-pat"}
            body = {"access_token": "synthetic-bearer"}
        elif path.endswith("/tags/2.1.1-r7"):
            assert method == "GET" and auth is None
            if state["tag"] is None:
                raise HTTPError(req.full_url, 404, "not found", {}, io.BytesIO())
            body = state["tag"]
        elif path == "/v2/namespaces/frisbeecz24/repositories/docker-oscar":
            assert method == "GET" and auth == "Bearer synthetic-bearer"
            if state["repository"] is None:
                raise HTTPError(req.full_url, 404, "not found", {}, io.BytesIO())
            body = state["repository"]
        elif path == "/v2/namespaces/frisbeecz24/repositories":
            assert method == "POST" and auth == "Bearer synthetic-bearer"
            assert data["name"] == "docker-oscar" and data["is_private"] is False
            assert data["namespace"] == "frisbeecz24"
            state["repository"] = dict(data, categories=[])
            body = state["repository"]
        else:
            assert path.startswith("/v2/repositories/frisbeecz24/docker-oscar/")
            if method == "PATCH":
                assert auth == "Bearer synthetic-bearer"
                if path.endswith("/categories/"):
                    assert data == [{"slug": "data-science", "name": "Data science"}]
                    state["repository"]["categories"] = data
                else:
                    assert path == "/v2/repositories/frisbeecz24/docker-oscar/"
                    assert set(data) == {"description", "full_description"}
                    state["repository"].update(data)
                body = state["repository"]
            else:
                assert method == "GET" and auth is None
                body = state["repository"]
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.OpenerDirector.open", request)
    monkeypatch.setenv("DOCKERHUB_TOKEN", "synthetic-pat")
    return module, state


def test_metadata_creates_requested_public_repository_and_updates_overview(hub):
    module, state = hub
    module.update_metadata(token="synthetic-pat")
    actual = state["repository"]
    assert actual["is_private"] is False
    assert 0 < len(actual["description"]) <= 100
    assert "CPAP" in actual["description"]
    assert actual["full_description"] == (module.ROOT / "docs/dockerhub.md").read_text()
    assert "docker compose up -d" in actual["full_description"]
    assert "/config/Uploads" in actual["full_description"]
    assert actual["categories"] == [{"slug": "data-science", "name": "Data science"}]
    assert all("synthetic-pat" not in path for _, path, _, _ in state["calls"])
    assert all(method != "DELETE" for method, *_ in state["calls"])


def test_existing_public_repository_is_not_recreated(hub):
    module, state = hub
    state["repository"] = {"is_private": False}
    module.update_metadata(token="synthetic-pat")
    assert sum(method == "POST" for method, *_ in state["calls"]) == 1  # auth only


def test_successful_metadata_patches_need_no_response_body(hub, monkeypatch):
    module, state = hub
    import urllib.request
    original = urllib.request.OpenerDirector.open
    def empty_patch(opener, req, **kwargs):
        response = original(opener, req, **kwargs)
        return io.BytesIO(b"") if req.get_method() == "PATCH" else response
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", empty_patch)
    module.update_metadata(token="synthetic-pat")
    assert state["repository"]["categories"][0]["slug"] == "data-science"


def test_private_repository_is_not_made_public(hub):
    module, state = hub
    state["repository"] = {"is_private": True}
    with pytest.raises(ValueError, match="private"):
        module.update_metadata(token="synthetic-pat")
    assert not any(method == "PATCH" for method, *_ in state["calls"])


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_hub_failure_stops_without_retry_or_secret_in_error(hub, monkeypatch, status):
    module, _ = hub
    calls = []
    def denied(_opener, req, **kwargs):
        calls.append(req)
        raise HTTPError(req.full_url, status, "synthetic-pat", {}, io.BytesIO(b"synthetic-pat"))
    monkeypatch.setattr("urllib.request.OpenerDirector.open", denied)
    with pytest.raises(ValueError, match=f"HTTP {status}") as error:
        module.update_metadata(token="synthetic-pat")
    assert "synthetic-pat" not in str(error.value)
    assert len(calls) == 1


def test_http_redirect_cannot_forward_bearer(hub, monkeypatch):
    module, _ = hub
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    paths = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(307)
            self.send_header("Location", "/stolen")
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Undo the fake HTTP boundary: this check exercises real urllib redirect handling.
    monkeypatch.undo()
    try:
        with pytest.raises(ValueError, match="HTTP 307"):
            module.api("GET", f"http://127.0.0.1:{server.server_port}/private", bearer="synthetic-bearer")
        assert paths == ["/private"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def migration(hub, monkeypatch):
    module, state = hub
    raw = json.dumps({"manifests": [
        {"platform": {"architecture": arch, "os": "linux"}} for arch in ("amd64", "arm64")
    ]}).encode()
    monkeypatch.setattr(module, "EXISTING_DIGEST", "sha256:" + hashlib.sha256(raw).hexdigest())
    monkeypatch.setenv("GITHUB_REPOSITORY", "frisbeecz/docker-oscar")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    calls = []
    def boundary(command, **kwargs):
        argv = list(map(str, command))
        calls.append((argv, kwargs))
        if argv[:2] == ["skopeo", "copy"]:
            assert "--all" in argv and "--preserve-digests" in argv
            assert argv[-2] == "docker://ghcr.io/frisbeecz/docker-oscar@" + module.EXISTING_DIGEST
            assert argv[-1] == "docker://docker.io/frisbeecz24/docker-oscar:2.1.1-r7"
            auth = Path(argv[argv.index("--authfile") + 1])
            assert auth.parent.stat().st_mode & 0o777 == 0o700
        elif argv[:2] == ["skopeo", "login"]:
            assert kwargs["input"] == "synthetic-pat"
            assert "synthetic-pat" not in argv
        else:
            assert argv[:3] == ["skopeo", "inspect", "--raw"]
            assert "--authfile" not in argv
        return subprocess.CompletedProcess(argv, 0, stdout=raw)
    monkeypatch.setattr(module, "run", boundary)
    return module, state, calls


def test_existing_image_migration_preserves_index_and_cleans_credentials(migration):
    module, state, calls = migration
    module.migrate_v102()
    copies = [c for c, _ in calls if c[:2] == ["skopeo", "copy"]]
    assert len(copies) == 1
    assert not Path(copies[0][copies[0].index("--authfile") + 1]).parent.exists()
    assert state["repository"]["categories"][0]["slug"] == "data-science"


def test_matching_existing_tag_needs_no_copy_or_registry_login(migration):
    module, state, calls = migration
    state["tag"] = {"name": "2.1.1-r7"}
    module.migrate_v102()
    assert all(c[1] not in ("copy", "login") for c, _ in calls)


def test_conflicting_tag_is_never_overwritten(migration, monkeypatch):
    module, state, calls = migration
    state["tag"] = {"name": "2.1.1-r7"}
    original = module.run
    def conflict(command, **kwargs):
        if str(command[-1]).endswith("docker-oscar:2.1.1-r7"):
            return subprocess.CompletedProcess(command, 0, stdout=b"other image")
        return original(command, **kwargs)
    monkeypatch.setattr(module, "run", conflict)
    with pytest.raises(ValueError, match="different index"):
        module.migrate_v102()
    assert not any(method in ("PATCH", "POST") for method, *_ in state["calls"])
    assert all(c[1] not in ("copy", "login") for c, _ in calls)


def test_copy_failure_cleans_credentials_and_never_retries(migration, monkeypatch):
    module, _, _ = migration
    original = module.run
    copies = []
    def fail(command, **kwargs):
        if list(command[:2]) == ["skopeo", "copy"]:
            copies.append(command)
            raise subprocess.CalledProcessError(1, command)
        return original(command, **kwargs)
    monkeypatch.setattr(module, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        module.migrate_v102()
    assert len(copies) == 1
    assert not Path(copies[0][copies[0].index("--authfile") + 1]).parent.exists()


@pytest.mark.parametrize("key,value", [
    ("GITHUB_REF", "refs/heads/untrusted"),
    ("GITHUB_REPOSITORY", "other/repo"),
    ("GITHUB_EVENT_NAME", "pull_request"),
])
def test_manual_migration_refuses_untrusted_execution_before_network(migration, monkeypatch, key, value):
    module, state, calls = migration
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="main"):
        module.migrate_v102()
    assert state["calls"] == [] and calls == []
