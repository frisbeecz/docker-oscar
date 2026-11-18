"""Production source-build contracts; no image build, daemon or network."""
import copy
import os
import re
import shutil
import subprocess

import pytest

from conftest import ROOT


def test_source_provenance_matches_locked_source(lock):
    from ci.source_bundle import source_provenance
    assert source_provenance(lock) == {
        "type": "source", "sourceCommit": lock["oscar"]["commit"],
        "sourceSha256": lock["oscar"]["sha256"], "recipe": "Dockerfile",
        "pythonRequirements": "python-requirements.txt",
    }
    assert "binaries" not in lock["oscar"]
    assert "binarySourceCorrespondence" not in lock["oscar"]


@pytest.mark.parametrize("mutation", ["recipe", "pythonRequirements", "type", "binaries", "sha256"])
def test_source_provenance_rejects_inconsistent_inputs(lock, mutation):
    from ci.source_bundle import source_provenance
    locked = copy.deepcopy(lock)
    if mutation in {"binaries", "sha256"}:
        locked["oscar"][mutation] = {} if mutation == "binaries" else "wrong"
    else:
        locked["oscar"]["build"][mutation] = "../wrong"
    with pytest.raises(ValueError, match="source provenance"):
        source_provenance(locked)


def test_wrong_source_hash_stops_before_unpack(tmp_path):
    # Execute the actual source-build RUN commands, not a rewritten hash check.
    runs = re.findall(r"^RUN (.*?)(?=^\w|\Z)", (ROOT / "Dockerfile").read_text(), re.M | re.S)
    source_runs = [r.replace("\\\n", "") for r in runs if "sha256sum" in r or "qmake6" in r]
    assert len(source_runs) == 2, "production recipe must verify source before qmake"
    calls = tmp_path / "calls"
    # macOS supplies the same checksum-file consumer as `shasum -a 256`.
    checksum = shutil.which("sha256sum")
    if checksum:
        (tmp_path / "sha256sum").symlink_to(checksum)
    else:
        checksum = shutil.which("shasum")
        assert checksum, "a native SHA256 checksum-file consumer is required"
        shim = tmp_path / "sha256sum"
        shim.write_text(f'#!/bin/sh\nexec "{checksum}" -a 256 "$@"\n')
        shim.chmod(0o755)
    for name in ("curl", "tar", "qmake6", "make"):
        path = tmp_path / name
        path.write_text('#!/bin/sh\nprintf "%s\\n" "${0##*/}" >> "$CALLS"\n'
                        + ('while [ "$#" -gt 0 ]; do\n'
                           'if [ "$1" = "-o" ]; then printf wrong > "$2"; exit 0; fi\n'
                           'shift\ndone\n' if name == "curl" else 'exit 0\n'))
        path.chmod(0o755)
    command = " && ".join(f"({r})" for r in source_runs).replace(
        "/tmp/oscar-source.tar.gz", str(tmp_path / "source.tar.gz"))
    result = subprocess.run(["/bin/sh", "-c", command], capture_output=True,
                            env={**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin", "CALLS": str(calls)})
    assert result.returncode != 0
    assert calls.read_text().splitlines() == ["curl"]
    assert b"FAILED" in result.stdout + result.stderr


def test_alpine_base_and_built_paths(lock):
    text = (ROOT / "Dockerfile").read_text()
    expected = f"FROM {lock['base']['repository']}:alpine324@{lock['base']['digest']}"
    assert text.count(expected) == 2
    assert lock["base"]["sourceCommit"] == "4acbc9ebc23dfdc0ed6f815223f13412bd3735f5"
    assert "apt-get" not in text and ".deb" not in text
    assert "qmake6 /src/OSCAR_QT.pro" in text and "make -j2" in text
    for path in ("/usr/bin/OSCAR20", "/usr/share/OSCAR20/Translations",
                 "/usr/share/OSCAR20/Html", "/usr/share/licenses/OSCAR20/COPYING"):
        assert path in text
    assert "/lsiopy/bin/python3 -m pip check" in text
    assert "--require-hashes" in text and "--only-binary=:all:" in text


def test_legacy_binary_provenance_still_validates(lock):
    from ci.source_bundle import binary_provenance
    legacy = copy.deepcopy(lock)
    legacy["oscar"].pop("build", None)
    legacy["oscar"]["binarySourceCorrespondence"] = "version-aligned; not independently proven"
    legacy["oscar"]["binaries"] = {
        arch: {"url": f"https://www.sleepfiles.com/OSCAR/2.1.1/oscar20_2.1.1-Debian13_{arch}-Qt6.deb",
               "sha256": "a" * 64, "architecture": arch, "package": "oscar20", "version": "2.1.1-Debian13"}
        for arch in ("amd64", "arm64")}
    assert binary_provenance(legacy)["correspondence"] == "version-aligned; not independently proven"
    legacy["oscar"]["binaries"]["arm64"]["architecture"] = "amd64"
    with pytest.raises(ValueError, match="binary provenance"):
        binary_provenance(legacy)
