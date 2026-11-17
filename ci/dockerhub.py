"""Docker Hub metadata and a fixed migration of the already-tested v1.0.2 image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ci import ROOT, run

REPOSITORY = "frisbeecz24/docker-oscar"
IMAGE = "docker.io/" + REPOSITORY
HUB = "https://hub.docker.com"
DESCRIPTION = "OSCAR CPAP data analysis in your browser. Web uploads, persistent storage, AMD64 and ARM64."
EXISTING_TAG = "2.1.1-r7"
EXISTING_DIGEST = "sha256:386ff28089d399c1305f42cb811a53ce9c9ac18695981888fb13094d348fad0f"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(method, url, *, bearer=None, data=None, missing_ok=False):
    """No redirects/retries; never include server bodies or credentials in errors."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    request = Request(url, headers=headers, method=method,
                      data=json.dumps(data).encode() if data is not None else None)
    try:
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        if missing_ok and method == "GET" and error.code == 404:
            return None
        raise ValueError(f"Docker Hub {method}: HTTP {error.code}") from None
    except URLError:
        raise ValueError(f"Docker Hub {method}: connection failed") from None


def update_metadata(*, token, project=ROOT):
    overview = (Path(project) / "docs/dockerhub.md").read_text()
    if not token or not token.strip() or not overview.strip() or len(DESCRIPTION) > 100:
        raise ValueError("Docker Hub token and valid metadata required")
    access = api("POST", HUB + "/v2/auth/token",
                 data={"identifier": "frisbeecz24", "secret": token}).get("access_token")
    if not isinstance(access, str) or not access or "\r" in access or "\n" in access:
        raise ValueError("Docker Hub returned an invalid access token")
    # The access token is never printed or written to disk.
    modern = HUB + "/v2/namespaces/frisbeecz24/repositories"
    repository = api("GET", modern + "/docker-oscar", bearer=access, missing_ok=True)
    if repository is None:
        api("POST", modern, bearer=access, data={
            "namespace": "frisbeecz24", "name": "docker-oscar", "registry": "docker.io",
            "is_private": False, "description": DESCRIPTION, "full_description": overview})
    elif repository.get("is_private") is not False:
        raise ValueError("Docker Hub destination is private; visibility will not be changed")
    endpoint = HUB + "/v2/repositories/" + REPOSITORY + "/"
    api("PATCH", endpoint, bearer=access,
        data={"description": DESCRIPTION, "full_description": overview})
    api("PATCH", endpoint + "categories/", bearer=access,
        data=[{"slug": "data-science", "name": "Data science"}])
    actual = api("GET", endpoint)  # Public metadata must match the requested update.
    if (actual.get("description") != DESCRIPTION
            or actual.get("full_description", "").strip() != overview.strip()
            or "data-science" not in {c["slug"] for c in actual.get("categories", [])}):
        raise ValueError("Docker Hub metadata readback mismatch")


def check_index(reference):
    raw = run(["skopeo", "inspect", "--raw", "docker://" + reference],
              capture_output=True).stdout
    if "sha256:" + hashlib.sha256(raw).hexdigest() != EXISTING_DIGEST:
        raise ValueError("Existing image points to a different index; no overwrite permitted")
    index = json.loads(raw)
    if (len(index["manifests"]) != 2
            or {(m["platform"]["os"], m["platform"]["architecture"])
                for m in index["manifests"]} != {("linux", "amd64"), ("linux", "arm64")}):
        raise ValueError("Existing image must contain both tested Linux architectures")


def migrate_v102():
    """Copy exactly the released r7 index; no input can select arbitrary content."""
    if (os.environ.get("GITHUB_REPOSITORY") != "frisbeecz/docker-oscar"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"):
        raise ValueError("Migration requires an explicit workflow dispatch on trusted main")
    token = os.environ.get("DOCKERHUB_TOKEN", "")
    if not token.strip():
        raise ValueError("DOCKERHUB_TOKEN required")
    source = "ghcr.io/frisbeecz/docker-oscar@" + EXISTING_DIGEST
    destination = IMAGE + ":" + EXISTING_TAG
    check_index(source)
    exists = api("GET", HUB + "/v2/repositories/" + REPOSITORY + "/tags/" + EXISTING_TAG,
                 missing_ok=True) is not None
    if exists:
        check_index(destination)  # Refuse a conflicting tag before any metadata mutation.
    update_metadata(token=token)
    if not exists:
        with tempfile.TemporaryDirectory(prefix="oscar-dockerhub-") as directory:
            auth = Path(directory) / "auth.json"
            run(["skopeo", "login", "--authfile", auth, "--username", "frisbeecz24",
                 "--password-stdin", "docker.io"], input=token, text=True)
            run(["skopeo", "copy", "--all", "--preserve-digests", "--authfile", auth,
                 "docker://" + source, "docker://" + destination])
        check_index(destination)  # Anonymous read, with no registry credentials.
    print("Docker Hub metadata and v1.0.2 image migration verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["migrate-v102"])
    parser.parse_args()
    migrate_v102()


if __name__ == "__main__":
    main()
