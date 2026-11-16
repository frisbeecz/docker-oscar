"""Publish tested Helm bytes directly under their tag, without an untagged GET.

Only GHCR's approved chart repository is writable. No retries, credential
files or credential-bearing redirects/subprocess arguments. Apache-2.0.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from urllib.error import HTTPError
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

BASE = "https://ghcr.io"
REPOSITORY = "frisbeecz/charts/oscar"
PREFIX = "/v2/" + REPOSITORY
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
CONFIG = "application/vnd.cncf.helm.config.v1+json"
CHART = "application/vnd.cncf.helm.chart.content.v1.tar+gzip"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(method, url, authorization, *, data=None, media=None, statuses=(200,), limit=1024 * 1024):
    headers = {"Accept": MANIFEST}
    if authorization:
        headers["Authorization"] = authorization
    if media:
        headers["Content-Type"] = media
    request = Request(url, data=data, headers=headers, method=method)
    try:
        response = build_opener(_NoRedirect()).open(request, timeout=120)
    except HTTPError as error:
        # An absent *tag* is an expected preflight response, not a retry signal.
        if error.code not in statuses:
            error.close()
            raise ValueError(f"chart registry {method}: HTTP {error.code}") from None
        response = error
    with response:
        _require(response.status in statuses, f"chart registry {method}: HTTP {response.status}")
        if response.status == 307:
            return response.status, response.headers, b""
        body = response.read(limit + 1)
        _require(len(body) <= limit, "chart registry response size exceeds expected bytes")
        return response.status, response.headers, body


def _descriptor(media, data):
    return {"mediaType": media, "digest": "sha256:" + hashlib.sha256(data).hexdigest(), "size": len(data)}


def publish_chart(path, *, sha256, version, username, token):
    """Return the verified OCI digest; preserve the tested .tgz byte for byte."""
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), "missing or unsafe chart")
    package = path.read_bytes()
    _require(hashlib.sha256(package).hexdigest() == sha256, "chart archive checksum mismatch")
    _require(re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version),
             "stable chart version required")
    with tarfile.open(fileobj=io.BytesIO(package), mode="r:gz") as archive:
        members = [m for m in archive.getmembers() if m.name == "oscar/Chart.yaml"]
        _require(len(members) == 1 and members[0].isfile() and members[0].size <= 1024 * 1024,
                 "missing or unsafe chart metadata")
        metadata = yaml.safe_load(archive.extractfile(members[0]).read())
    _require(isinstance(metadata, dict) and metadata.get("name") == "oscar"
             and metadata.get("version") == version and metadata.get("apiVersion") == "v2",
             "chart metadata name/version mismatch")
    config = json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode()
    config_descriptor, chart_descriptor = _descriptor(CONFIG, config), _descriptor(CHART, package)
    manifest = json.dumps({
        "schemaVersion": 2, "mediaType": MANIFEST,
        "config": config_descriptor, "layers": [chart_descriptor],
        "annotations": {"org.opencontainers.image.source": "https://github.com/frisbeecz/docker-oscar"},
    }, separators=(",", ":"), sort_keys=True).encode()
    expected = _descriptor(MANIFEST, manifest)["digest"]
    _require(isinstance(username, str) and re.fullmatch(r"[A-Za-z0-9-]+(?:\[bot\])?", username)
             and isinstance(token, str) and bool(token), "invalid publishing credentials")
    basic = "Basic " + base64.b64encode(f"{username}:{token}".encode()).decode()
    token_url = BASE + "/token?" + urlencode({
        "service": "ghcr.io", "scope": f"repository:{REPOSITORY}:pull,push"})
    _, _, raw = _request("GET", token_url, basic)
    access = json.loads(raw)
    bearer = access.get("token") or access.get("access_token")
    _require(isinstance(bearer, str) and bool(bearer) and "\r" not in bearer and "\n" not in bearer,
             "invalid registry access token")
    authorization = "Bearer " + bearer
    tag_url = BASE + PREFIX + "/manifests/" + version
    status, _, _ = _request("GET", tag_url, authorization, statuses=(200, 404))
    _require(status == 404, "chart tag already exists; refusing overwrite")
    for descriptor, data in [(config_descriptor, config), (chart_descriptor, package)]:
        upload_url = BASE + PREFIX + "/blobs/uploads/"
        _, headers, _ = _request("POST", upload_url, authorization,
                                 data=b"", statuses=(202,))
        raw_location = headers.get("Location", "")
        location = urljoin(upload_url, raw_location)
        parsed = urlsplit(location)
        # Location is opaque: do not guess upload endpoint or identifier syntax.
        # Constrain the credential destination, not GHCR's session URL format.
        checks = {
            "missing": bool(raw_location),
            "https": parsed.scheme == "https",
            "origin": parsed.netloc == "ghcr.io",
            "repository": parsed.path.startswith(PREFIX + "/blobs/"),
            "traversal": not any(p in {".", ".."} for p in unquote(parsed.path).split("/")),
            "fragment": not parsed.fragment,
            "digest": "digest" not in parse_qs(parsed.query, keep_blank_values=True),
        }
        # Only invariant names, never signed URL/query values or credentials.
        failed = ", ".join(name for name, valid in checks.items() if not valid)
        _require(not failed, "unsafe registry upload location: " + failed)
        separator = "&" if parsed.query else "?"
        _request("PUT", location + separator + urlencode({"digest": descriptor["digest"]}),
                 authorization, data=data, media="application/octet-stream", statuses=(201,))
    # Unlike Helm ExtendedCopy/Tag, this sends locally held bytes directly by
    # version. It never asks the registry to fetch an untagged manifest.
    _request("PUT", tag_url, authorization, data=manifest, media=MANIFEST, statuses=(201,))
    _, _, published = _request("GET", tag_url, authorization, limit=len(manifest))
    _require(_descriptor(MANIFEST, published)["digest"] == expected, "published manifest checksum mismatch")
    for descriptor, _ in [(config_descriptor, config), (chart_descriptor, package)]:
        status, headers, downloaded = _request(
            "GET", BASE + PREFIX + "/blobs/" + descriptor["digest"], authorization,
            limit=descriptor["size"], statuses=(200, 307))
        if status == 307:
            # GHCR serves blobs via signed CDN URLs. Never forward its bearer.
            location = headers.get("Location", "")
            parsed = urlsplit(location)
            _require(parsed.scheme == "https" and parsed.netloc == "pkg-containers.githubusercontent.com"
                     and parsed.path.startswith("/ghcr1/blobs/") and not parsed.fragment,
                     "unsafe registry blob redirect")
            _, _, downloaded = _request("GET", location, None, limit=descriptor["size"])
        _require(len(downloaded) == descriptor["size"]
                 and _descriptor(descriptor["mediaType"], downloaded)["digest"] == descriptor["digest"],
                 "downloaded chart/config bytes checksum mismatch")
    return expected
