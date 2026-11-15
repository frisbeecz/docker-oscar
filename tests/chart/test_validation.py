"""Exercise the actual strict validator, including its failure paths."""
import copy
import importlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from .conftest import API, ROOT, render_chart, routes


@pytest.fixture(scope="module")
def schemas():
    chart = importlib.import_module("ci.chart")
    return chart.prepare_schemas(ROOT / "artifacts/chart/schemas")


def test_pinned_schemas(schemas):
    chart = importlib.import_module("ci.chart")
    docs = render_chart(routes(), (API,))
    evidence = chart.validate_documents(docs, schemas, os.environ.get("KUBECONFORM", "kubeconform"))
    assert evidence["valid"] == 8
    assert evidence["invalid"] == evidence["errors"] == evidence["skipped"] == 0


@pytest.mark.parametrize("kind", ["Deployment", "Service", "PersistentVolumeClaim",
                                  "ServiceAccount", "Ingress", "HTTPRoute"])
def test_strict_unknown_nested_fields(schemas, kind):
    chart = importlib.import_module("ci.chart")
    doc = copy.deepcopy(next(d for d in render_chart(routes(), (API,)) if d["kind"] == kind))
    if kind == "ServiceAccount":
        doc["metadata"]["unexpectedTypo"] = True
    elif kind == "HTTPRoute":
        doc["spec"]["rules"][0]["unexpectedTypo"] = True
    elif kind == "Deployment":
        doc["spec"]["template"]["spec"]["containers"][0]["unexpectedTypo"] = True
    else:
        doc["spec"]["unexpectedTypo"] = True
    with pytest.raises(subprocess.CalledProcessError):
        chart.validate_documents([doc], schemas, os.environ.get("KUBECONFORM", "kubeconform"))


def test_missing_schema_is_failure(schemas):
    chart = importlib.import_module("ci.chart")
    with pytest.raises(ValueError, match="schema"):
        chart.validate_documents([{"apiVersion": "example.org/v1", "kind": "Unknown"}], schemas, "kubeconform")
    with pytest.raises(ValueError, match="schema"):
        chart.validate_documents([{"apiVersion": "apps/v9", "kind": "Deployment"}], schemas, "kubeconform")


def test_corrupt_schema_is_not_redownloaded(tmp_path, schemas, monkeypatch):
    chart = importlib.import_module("ci.chart")
    target = tmp_path / "schemas"
    shutil.copytree(Path(schemas["Deployment"]["path"]).parent, target)
    (target / "deployment-apps-v1.json").write_text("{}")
    monkeypatch.setattr(chart.urllib.request, "urlopen",
                        lambda *a, **kw: pytest.fail("checksum failure must not trigger a download"))
    with pytest.raises(ValueError, match="checksum"):
        chart.prepare_schemas(target)


def test_cli_refuses_overwrite(tmp_path):
    target = tmp_path / "chart.json"
    target.write_text("old evidence")
    result = subprocess.run([os.sys.executable, "-m", "ci.chart", "--helm", "helm",
                             "--out-dir", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert target.read_text() == "old evidence"


def test_lint_route_matrix(tmp_path):
    chart = importlib.import_module("ci.chart")
    for name, values in chart.matrix().items():
        file = tmp_path / f"{name}.yaml"
        file.write_text(yaml.safe_dump(values))
        chart.lint_chart(os.environ.get("HELM", "helm"), file, tmp_path / f"{name}.log")
