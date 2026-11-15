"""The development interpreter and every hosted job use the selected Python."""
import json
from pathlib import Path
import tomllib

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("workflow", ["ci", "release"])
def test_every_python_setup_uses_314(workflow):
    data = yaml.safe_load((ROOT / f".github/workflows/{workflow}.yaml").read_text())
    setups = [
        step for job in data["jobs"].values() for step in job.get("steps", [])
        if step.get("uses", "").startswith("actions/setup-python@")
    ]
    assert setups, "each workflow must provision its interpreter"
    for step in setups:
        assert step["with"]["python-version"] == "3.14"
        assert not step["with"].get("allow-prereleases", False)


def test_local_python_and_package_requirement_match_ci():
    assert (ROOT / ".python-version").read_text().strip() == "3.14"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["requires-python"] == ">=3.14"
    tools = json.loads((ROOT / "ci/tools.lock.json").read_text())
    assert tools["python"]["version"] == "3.14"
