"""Debian official-package integration; no daemon or network."""
import os
import copy
import re
import subprocess

import pytest

from conftest import ROOT


HASHES = {
    "amd64": "a9256776774e9ae1313feb5ed0aa5fe38eb808168c3e2d5ea0e3e3ce4ce289dc",
    "arm64": "6973e4f8d81f170a6d59ea1205c954e231c8158f10c433cec3bc23e903f9bece",
}


def test_official_binary_provenance(lock):
    binaries = lock["oscar"]["binaries"]
    assert set(binaries) == set(HASHES)
    for arch, digest in HASHES.items():
        pin = binaries[arch]
        assert pin["url"] == f"https://www.sleepfiles.com/OSCAR/2.1.1/oscar20_2.1.1-Debian13_{arch}-Qt6.deb"
        assert pin["sha256"] == digest
        assert pin["architecture"] == arch
        assert pin["package"] == "oscar20"
        assert pin["version"] == "2.1.1-Debian13"
    assert lock["oscar"]["binarySourceCorrespondence"] == "version-aligned; not independently proven"


def install_run():
    text = (ROOT / "Dockerfile").read_text()
    commands = re.findall(r"^RUN (.*?)(?=^\w|\Z)", text, re.M | re.S)
    return next(command.replace("\\\n", "") for command in commands if "oscar.deb" in command)


@pytest.mark.parametrize("arch", ["amd64", "arm64", "s390x"])
def test_docker_install_selects_arch_and_verifies_before_apt(tmp_path, arch):
    # Execute the actual RUN shell with inert boundary commands, not a reimplementation.
    command = install_run().replace("/tmp/oscar.deb", str(tmp_path / "oscar.deb"))
    log = tmp_path / "calls"
    for name in ("curl", "sha256sum", "dpkg-deb", "dpkg", "apt-get", "mkdir", "test", "rm"):
        script = tmp_path / name
        script.write_text("""#!/bin/sh
printf '%s %s\\n' "${0##*/}" "$*" >> "$CALLS"
case "${0##*/}:$*" in
  sha256sum:*) cat >> "$CALLS"; exit "${BAD_HASH:-0}";;
  dpkg-deb:*Package*) echo "${PACKAGE_NAME:-oscar20}";;
  dpkg-deb:*Version*) echo "${PACKAGE_VERSION:-2.1.1-Debian13}";;
  dpkg-deb:*Architecture*) echo "${PACKAGE_ARCH:-$TARGETARCH}";;
  dpkg:*) echo "$TARGETARCH";;
esac
""")
        script.chmod(0o755)
    env = {**os.environ, "TARGETARCH": arch, "CALLS": str(log), "PATH": f"{tmp_path}:/usr/bin:/bin"}
    result = subprocess.run(["/bin/sh", "-c", command], env=env, capture_output=True)
    calls = log.read_text() if log.exists() else ""
    if arch == "s390x":
        assert result.returncode != 0
        assert "curl" not in calls and "apt-get" not in calls
        return
    assert result.returncode == 0, result.stderr
    assert f"Debian13_{arch}-Qt6.deb" in calls
    assert HASHES[arch] in calls
    assert calls.index("sha256sum") < calls.index("apt-get")
    log.unlink()
    result = subprocess.run(["/bin/sh", "-c", command], env={**env, "BAD_HASH": "1"}, capture_output=True)
    assert result.returncode != 0
    assert "apt-get" not in log.read_text()
    for key, wrong in (("PACKAGE_NAME", "other"), ("PACKAGE_VERSION", "2.0"),
                       ("PACKAGE_ARCH", "s390x")):
        log.unlink()
        result = subprocess.run(["/bin/sh", "-c", command], env={**env, key: wrong}, capture_output=True)
        assert result.returncode != 0
        assert "apt-get" not in log.read_text()


def test_debian_base_and_packaged_paths(lock):
    text = (ROOT / "Dockerfile").read_text()
    assert text.count("FROM ") == 1
    assert f":debiantrixie@{lock['base']['digest']}" in text
    assert lock["base"]["digest"] == "sha256:d03d09e9ceb770032db5892dd7caa9b207ef09b55a9b79491a1c4d37842e6c01"
    assert lock["base"]["sourceCommit"] == "e45b4fe636ee99860a40eb552d0e4b21aefad842"
    assert "ARG TARGETARCH" in text
    for forbidden in ("apk ", "qmake", "make -j", "/opt/oscar", "ln -s"):
        assert forbidden not in text
    for path in ("/usr/bin/OSCAR20", "/usr/share/OSCAR20/Translations", "/usr/share/OSCAR20/Html",
                 "/usr/share/doc/oscar20/copyright"):
        assert path in text


@pytest.mark.parametrize("mutation", ["architecture", "version", "url", "missing-platform", "correspondence"])
def test_source_manifest_rejects_inconsistent_binary_provenance(lock, mutation):
    from ci.source_bundle import binary_provenance
    locked = copy.deepcopy(lock)
    pin = locked["oscar"]["binaries"]["arm64"]
    if mutation == "missing-platform":
        del locked["oscar"]["binaries"]["arm64"]
    elif mutation == "correspondence":
        locked["oscar"]["binarySourceCorrespondence"] = "reproducible"
    else:
        pin[mutation] = "wrong"
    with pytest.raises(ValueError, match="binary provenance"):
        binary_provenance(locked)
