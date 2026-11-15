"""The distributed chart must carry its own Apache license and notice."""
import os
import subprocess
import tarfile

import yaml

from .conftest import CHART, ROOT


def test_packaged_chart_carries_apache_license_and_notice(tmp_path):
    subprocess.run([os.environ.get("HELM", "helm"), "package", str(CHART),
                    "--destination", str(tmp_path)], check=True, capture_output=True, text=True)
    archives = list(tmp_path.glob("*.tgz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        metadata = yaml.safe_load(archive.extractfile("oscar/Chart.yaml").read())
        assert metadata["annotations"]["licenses"] == "Apache-2.0"
        license_text = archive.extractfile("oscar/LICENSE").read()
        assert license_text == (ROOT / "LICENSE").read_bytes()
        assert b"Version 2.0, January 2004" in license_text
        assert b"Copyright (C) 2026 docker-oscar contributors" in archive.extractfile("oscar/NOTICE").read()
