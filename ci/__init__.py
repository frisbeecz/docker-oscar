"""Shared provenance and strict-schema contracts. SPDX-License-Identifier: Apache-2.0."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIFF_SHA256 = hashlib.sha256(b"[]").hexdigest()


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command, *, cwd=ROOT, **kwargs):
    return subprocess.run([str(x) for x in command], cwd=cwd, check=True, **kwargs)


def output(command, *, cwd=ROOT) -> str:
    return run(command, cwd=cwd, stdout=subprocess.PIPE, text=True).stdout.strip()


def load_lock(name="versions.lock.json", *, project=ROOT) -> dict:
    return json.loads((Path(project) / name).read_text())


def state_identity(project=ROOT) -> dict:
    """Hash changed paths, index entries, modes and working bytes, including untracked.

    Paths come exclusively from git -z; ignored untracked data is never read.
    Symlinks hash their target string, never the target's contents.
    """
    project = Path(project).resolve()
    head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"],
                          cwd=project, capture_output=True, text=True)
    if head.returncode not in (0, 1):
        raise RuntimeError("cannot determine git identity")
    changed = set()
    for args in [
        ["diff", "--no-renames", "--name-only", "-z"],
        ["diff", "--cached", "--no-renames", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ]:
        changed.update(p for p in run(["git", *args], cwd=project, capture_output=True).stdout.split(b"\0") if p)
    entries = []
    for raw in sorted(changed):
        path = os.fsdecode(raw)
        file = project / path
        index = run(["git", "ls-files", "--stage", "-z", "--", path],
                    cwd=project, capture_output=True).stdout
        item = {"path": path, "indexSha256": hashlib.sha256(index).hexdigest()}
        try:
            info = file.lstat()
        except FileNotFoundError:
            item["kind"] = "deleted"
        else:
            item["mode"] = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                item.update(kind="symlink", sha256=hashlib.sha256(os.fsencode(os.readlink(file))).hexdigest())
            elif stat.S_ISREG(info.st_mode):
                item.update(kind="file", sha256=sha256_file(file))
            else:
                raise ValueError(f"unsupported changed path: {path}")
        entries.append(item)
    return {"gitCommit": head.stdout.strip() if head.returncode == 0 else None,
            "dirtyDiffSha256": hashlib.sha256(canonical_json(entries)).hexdigest()}


def receipt(*, command=None, project=ROOT) -> dict:
    return {"schemaVersion": 1, **state_identity(project),
            "command": command or [sys.executable, *sys.argv], "cwd": str(Path(project).resolve()),
            "exitCode": None,
            "platform": {"system": platform.system(), "machine": platform.machine(),
                         "python": platform.python_version()},
            "checks": {}}


def write_json(path: Path, value) -> None:
    """Atomic receipt publication; never replace a receipt with partial JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(canonical_json(value) + b"\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def strict_gateway_schema(crd_bytes: bytes, metadata_schema: dict) -> dict:
    """Derive v1 HTTPRoute from the locked CRD; never ignore unknown fields.

    Caller verifies the CRD SHA and the derived canonical JSON SHA in tools.lock.
    Map-valued additionalProperties and preserve-unknown subtrees remain maps.
    CEL/admission validation remains a native Kubernetes gate, not JSON Schema.
    """
    import yaml
    crd = next(d for d in yaml.safe_load_all(crd_bytes)
               if d and d.get("metadata", {}).get("name") == "httproutes.gateway.networking.k8s.io")
    schema = copy.deepcopy(next(v["schema"]["openAPIV3Schema"]
                                for v in crd["spec"]["versions"] if v["name"] == "v1"))
    schema["properties"]["metadata"] = copy.deepcopy(metadata_schema)
    def strict(value):
        if isinstance(value, dict):
            if ("properties" in value and "additionalProperties" not in value
                    and not value.get("x-kubernetes-preserve-unknown-fields")):
                value["additionalProperties"] = False
            for child in value.values():
                strict(child)
        elif isinstance(value, list):
            for child in value:
                strict(child)
    strict(schema)
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    return schema
