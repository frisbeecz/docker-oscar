"""No empty lint inputs, silent tool skip, unsafe tar extraction or fake negative."""
import importlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def product():
    assert (ROOT / "ci/check.py").is_file(), "common check CLI missing"
    return importlib.import_module("ci.check")


def test_file_detection_includes_extensionless_shell_and_excludes_go_templates():
    groups = product().discover()
    assert "root/usr/local/bin/oscar-start" in groups["shell"]
    assert "root/defaults/autostart_wayland" in groups["shell"]
    assert "Dockerfile" in groups["docker"]
    assert ".github/workflows/ci.yaml" in groups["yaml"]
    assert "charts/oscar/values.yaml" in groups["yaml"]
    assert "charts/oscar/templates/deployment.yaml" not in groups["yaml"]
    assert "ci/release.py" in groups["python"]


def test_missing_tool_fails_before_checks(tmp_path):
    with pytest.raises((ValueError, FileNotFoundError)):
        product().tool("actionlint", directory=tmp_path, search_path="")


def test_tar_binary_extraction_rejects_duplicate_or_symlink(tmp_path):
    for mode in ("duplicate", "symlink"):
        archive = tmp_path / f"{mode}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            item = tarfile.TarInfo("some/bin/tool")
            if mode == "symlink":
                item.type = tarfile.SYMTYPE
                item.linkname = "/etc/passwd"
                tar.addfile(item)
            else:
                for _ in range(2):
                    item.size = 3
                    tar.addfile(item, io.BytesIO(b"bin"))
        with pytest.raises(ValueError):
            product().install_binary(archive, "tool", tmp_path / "tool")
        assert not (tmp_path / "tool").exists()


@pytest.mark.parametrize("failure", ["harness-error", "exit-zero", "cleanup"])
def test_negative_cli_does_not_swallow_infra(tmp_path, failure):
    check = product()
    path = tmp_path / "negative-base-runtime-amd64.json"
    receipt = {"exitCode": 1, "expectedFailure": True, "failureKind": "missing-oscar-gui-profile"}
    code = 1
    if failure == "harness-error":
        receipt.update(expectedFailure=False, failureKind="harness-error")
    elif failure == "exit-zero":
        code = 0
    else:
        receipt["cleanupError"] = "daemon unavailable"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        check.validate_negative(path, code)


def test_negative_cli_accepts_only_missing_gui(tmp_path):
    path = tmp_path / "negative.json"
    path.write_text(json.dumps({"exitCode": 1, "expectedFailure": True,
                               "failureKind": "missing-oscar-gui-profile"}))
    product().validate_negative(path, 1)


def test_negative_probe_refuses_local_before_daemon(tmp_path, monkeypatch):
    check = product()
    monkeypatch.setattr(check.platform, "system", lambda: "Darwin")
    def forbidden(*args, **kwargs):
        raise AssertionError("local daemon touched")
    monkeypatch.setattr(check, "run", forbidden)
    with pytest.raises(ValueError, match="native"):
        check.negative_probe("arm64", tmp_path)
