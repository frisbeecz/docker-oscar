# Experimental Alpine feasibility probe

**Throwaway experiment, not a supported image or a production migration.**
The production Dockerfile, release workflow, image tags, Helm chart and K3s deployment
are not changed by this branch.

The branch-only `Alpine feasibility spike` workflow uses native AMD64 and ARM64 GitHub
hosted runners. It builds the same OSCAR 2.1.1 source used by the current source receipt,
but against Alpine's musl and Qt6 instead of reusing the Debian binary. The LinuxServer
Alpine 3.24 base index and source archive are digest-pinned in this experiment.

Each runner:

1. Installs the SHA256-verified Trivy 0.76.2 binary and downloads one vulnerability database.
2. Scans the published Debian image and the Alpine base without ignoring unfixed findings.
3. Builds the experimental image locally, without a registry login or push.
4. Scans the candidate using the same scanner/database, even if a later runtime check fails.
5. Starts one disposable container with three new test volumes, only a loopback HTTP port,
   no host devices/socket, and the same desktop/upload restrictions as the deployed setup.
6. Checks a stable unprivileged OSCAR process, HTTP, nested upload/list/download, automatic
   restart after SIGTERM, and synthetic data retained across a container restart.
7. Retains JSON/log evidence on success or failure.

Only owned, randomly named test resources are removed. No real SD card, patient profile
or existing volume is used. Runtime and scanner entry points reject non-GitHub-hosted
execution and refs other than this experimental branch.

The probes do **not** prove visual browser rendering, real CPAP import fidelity, full
backup/restore or application compatibility with every Qt6 behavior. Those remain
separate acceptance work before any production migration. There is no zero-CVE promise:
the Alpine Selkies base also contains Docker, OpenSSH and a substantial desktop stack.
OS package repositories are live, so this is not a bit-reproducible release recipe.

The candidate refreshes the three Python packages flagged in the initial Alpine
scan: msgpack, setuptools and urllib3. Exact stable versions observed on PyPI
2026-11-18 are recorded in `inputs.json` and SHA256-locked CPython 3.14 wheels
in `python-requirements.txt`. They are installed only into Selkies' `/lsiopy`
environment, followed by `pip check`; native runtime evidence verifies the
installed versions. This is not a blanket upgrade of every desktop dependency.
The original pinned Alpine base remains a scan reference.

Storage checks use `/proc/self/mountinfo` to recognize Docker named-volume bind
mounts on the same filesystem, and separately enforce mount flags and actual
unprivileged write/read probes. Diagnostics retain ownership and mount details;
failure never triggers ownership changes or a skipped acceptance check.

Artifacts are diagnostic JSON/logs only; no application image or binary is published.
OSCAR and dependency licensing/corresponding-source obligations must be addressed for
any future distribution. This branch must not be merged as a production migration.

## Local checks

With the existing project test environment:

```sh
python -m pytest -q spike/alpine/test_probe.py
python -m ci.check --static-only --out-dir artifacts/alpine-static
```

The actual native build/runtime/scan runs only in the explicitly approved GitHub
experiment. Results and limitations are recorded in [ledger.md](ledger.md).
