"""Tarball builds must not report the packaging repository's VCS revision."""
from pathlib import Path
import tarfile

import pytest

from ci import check


def make_source(tmp_path: Path, version: str) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    # A tiny real Make target models upstream's GOFLAGS-sensitive version output.
    # The actual Go VCS behavior is separately reproduced in the diagnostic log.
    (source / "Makefile").write_text(
        "bin/skopeo:\n"
        "\tmkdir -p bin\n"
        "\tprintf '%s\\n' '#!/bin/sh' "
        f"'echo \"skopeo version {version}"
        "$(if $(filter -buildvcs=false,$(GOFLAGS)),, commit: unrelated-parent)\"' "
        "> bin/skopeo\n"
        "\tchmod +x bin/skopeo\n"
    )
    return source


def test_tarball_bootstrap_suppresses_parent_vcs_and_checks_exact_version(tmp_path, monkeypatch, capsys):
    source = make_source(tmp_path, "1.25.1")
    target = tmp_path / "installed/skopeo"
    target.parent.mkdir()
    monkeypatch.setenv("GOFLAGS", "-buildvcs=true")
    check.build_skopeo(source, target, "1.25.1")
    assert check.output([str(target), "--version"]) == "skopeo version 1.25.1"
    assert target.stat().st_mode & 0o111
    assert "skopeo version 1.25.1" in capsys.readouterr().out
    assert check.os.environ["GOFLAGS"] == "-buildvcs=true"


@pytest.mark.parametrize("version", [
    "1.25.2", "1.25.10", "1.25.1-dev", "1.25.1 commit: unexpected",
])
def test_tarball_bootstrap_wrong_version_rejected_before_install(tmp_path, version):
    source = make_source(tmp_path, version)
    target = tmp_path / "skopeo"
    with pytest.raises(ValueError, match="unsupported skopeo version") as error:
        check.build_skopeo(source, target, "1.25.1")
    assert version in str(error.value)
    assert not target.exists()


def test_native_bootstrap_only_builds_locked_skopeo_without_browser_or_ocr(tmp_path, monkeypatch):
    source = make_source(tmp_path, "1.25.1")
    archive = tmp_path / "skopeo.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname="skopeo-1.25.1")
    root = tmp_path / "checkout"
    binary = root / ".venv/tools/bin"
    binary.mkdir(parents=True)
    tools = check.load_lock("ci/tools.lock.json")
    calls, downloads = [], []
    original_run = check.run
    def host_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["sudo", "apt-get"]:
            return
        assert command[:2] == ["make", "bin/skopeo"], command
        return original_run(command, **kwargs)
    def cached(pin):
        assert pin == tools["skopeo"]["source"], "unnecessary OCR/browser acquisition"
        downloads.append(pin)
        return archive
    monkeypatch.setattr(check, "ROOT", root)
    monkeypatch.setattr(check, "BIN", binary)
    monkeypatch.setattr(check, "require_disposable_runner", lambda: None)
    monkeypatch.setattr(check, "require_native", lambda arch: None)
    monkeypatch.setattr(check, "load_lock", lambda *a: tools)
    monkeypatch.setattr(check, "download", cached)
    monkeypatch.setattr(check, "run", host_run)
    check.native_tools()
    assert check.output([str(binary / "skopeo"), "--version"]) == "skopeo version 1.25.1"
    assert downloads == [tools["skopeo"]["source"]]
    packages = next(c for c in calls if c[:3] == ["sudo", "apt-get", "install"])
    assert not {"libleptonica-dev", "autoconf", "automake", "libtool"} & set(packages)
