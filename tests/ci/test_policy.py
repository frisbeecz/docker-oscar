"""Policy is evaluated on YAML nodes and the transitive job graph."""
from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflows():
    paths = [ROOT / ".github/workflows" / f"{name}.yaml" for name in ("ci", "release")]
    assert all(p.is_file() for p in paths), "required workflows missing"
    return {p.stem: yaml.safe_load(p.read_text()) for p in paths}


def closure(jobs, name, seen=None):
    seen = set() if seen is None else seen
    assert name not in seen, "cyclic needs"
    needs = jobs[name].get("needs", [])
    needs = [needs] if isinstance(needs, str) else needs
    result = set(needs)
    for dependency in needs:
        assert dependency in jobs
        result |= closure(jobs, dependency, seen | {name})
    return result


def test_no_privileged_pr():
    ws = workflows()
    ci = ws["ci"]
    events = ci.get("on", ci.get(True))
    assert {"pull_request", "push", "workflow_call"} <= set(events)
    assert not {"pull_request_target", "workflow_run"} & set(events)
    for job in ci["jobs"].values():
        assert "secrets" not in job
        for step in job.get("steps", []):
            text = str(step)
            assert "secrets." not in text or "secrets.GITHUB_TOKEN" in text
            assert not re.search(r"docker login|gh release|ci\.release publish|skopeo copy", text)


def test_actions_sha_pinned():
    for wf in workflows().values():
        for job in wf["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert re.fullmatch(r"[\w.-]+/[\w./-]+@[a-f0-9]{40}", step["uses"])
                if step.get("uses", "").startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False


def test_minimal_job_permissions():
    for name, wf in workflows().items():
        assert wf["permissions"] == {"contents": "read"}
        for key, job in wf["jobs"].items():
            perms = job.get("permissions", {})
            if name == "release" and key == "publish":
                assert perms == {"contents": "write", "packages": "write"}
            else:
                assert all(v == "read" for v in perms.values())
                assert set(perms) <= {"contents"}
            assert not job.get("continue-on-error", False)


def test_dockerhub_secret_is_scoped_to_trusted_publish_step():
    """A build, PR job or dependency installer must never receive the registry token."""
    ws = workflows()
    assert "DOCKERHUB_TOKEN" not in ws["release"].get("env", {})
    consumers = []
    for name, workflow in ws.items():
        for key, job in workflow["jobs"].items():
            assert "DOCKERHUB_TOKEN" not in job.get("env", {})
            for step in job.get("steps", []):
                value = step.get("env", {}).get("DOCKERHUB_TOKEN")
                if value is not None:
                    consumers.append((name, key, step))
    assert len(consumers) == 1
    name, key, step = consumers[0]
    assert (name, key) == ("release", "publish")
    assert step["env"]["DOCKERHUB_TOKEN"] == "${{ secrets.DOCKERHUB_TOKEN }}"
    assert "ci.release publish " in step["run"]
    assert not step.get("if")


def test_release_dependency_closure():
    ws = workflows()
    jobs = ws["release"]["jobs"]
    assert closure(jobs, "publish") == {"tests"}
    assert jobs["tests"]["uses"] == "./.github/workflows/ci.yaml"
    assert not jobs["publish"].get("if"), "publish uses implicit success(), never always()"
    ci_jobs = ws["ci"]["jobs"]
    assert set(ci_jobs) == {"static", "helm", "native"}
    assert set(ci_jobs["helm"]["strategy"]["matrix"]["helm"]) == {"3.19.0", "4.3.2"}
    native = ci_jobs["native"]["strategy"]["matrix"]["include"]
    assert {(p["arch"], p["runner"]) for p in native} == {
        ("amd64", "ubuntu-24.04"), ("arm64", "ubuntu-24.04-arm")}
    assert ci_jobs["native"]["strategy"]["fail-fast"] is False
    assert all(not ci_jobs[j].get("if") for j in ci_jobs)


def test_native_gate_is_startup_only_and_success_upload_depends_on_smoke():
    ws = workflows()
    for wf in ws.values():
        for job in wf["jobs"].values():
            text = str(job).lower()
            assert not re.search(r"ci\.kubernetes|ci\.gui|--negative|kind (create|load|delete)|"
                                 r"tesseract|traineddata|playwright install|chromium|"
                                 r"gui,|ocr|profile|persistence", text)
    steps = ws["ci"]["jobs"]["native"]["steps"]
    source = next(i for i, s in enumerate(steps) if "ci.check --sources" in s.get("run", ""))
    build = next(i for i, s in enumerate(steps) if "-m ci.build_image " in s.get("run", ""))
    smoke = next(i for i, s in enumerate(steps) if "ci.runtime " in s.get("run", ""))
    upload = next(i for i, s in enumerate(steps)
                  if s.get("with", {}).get("name") == "native-${{ matrix.arch }}")
    assert source < build < smoke < upload
    assert all(not steps[i].get("if") for i in (source, build, smoke, upload))
    assert "--negative-base-probe" not in steps[smoke]["run"]
    diagnostics = next(s for s in steps if s.get("if") == "failure()")
    assert diagnostics["with"]["path"].splitlines() == [
        "artifacts/native/**/*.json", "artifacts/native/**/*.log"]


def test_publication_inputs_are_data():
    for wf in workflows().values():
        for job in wf["jobs"].values():
            for step in job.get("steps", []):
                # Expressions are allowed in env/with, not executable shell source.
                assert "${{" not in step.get("run", "")
    steps = workflows()["release"]["jobs"]["publish"]["steps"]
    publish = next(i for i, s in enumerate(steps) if "ci.release publish " in s.get("run", ""))
    # publish() validates the downloaded artifacts itself before its first write.
    # No independent verify step or API audit is needed in the workflow.
    assert all(not re.search(r"login|gh release|skopeo copy|imagetools create|helm push",
                             s.get("run", "")) for s in steps[:publish])
    downloads = [i for i, s in enumerate(steps)
                 if s.get("uses", "").startswith("actions/download-artifact@")]
    assert len(downloads) == 3 and all(i < publish for i in downloads)


@pytest.mark.parametrize("workflow", ["ci", "release"])
def test_no_hidden_failure_or_cross_run_download(workflow):
    for job in workflows()[workflow]["jobs"].values():
        for step in job.get("steps", []):
            assert not step.get("continue-on-error", False)
            if step.get("uses", "").startswith("actions/download-artifact@"):
                assert not set(step.get("with", {})) & {"run-id", "github-token", "repository"}
                assert step.get("with", {}).get("digest-mismatch") == "error"
