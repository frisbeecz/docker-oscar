# OSCAR runtime pip removal

- ID: OSCAR-PIP-REMOVAL; owner high primary, single writer; attempt 1/2.
- State: DONE locally; independent review PASS, integration/native build pending.
- cwd: `/Users/ondrejvala/.local/share/opencode/worktree/b0fea1/oscar-alpine-production`
- Baseline: `9234afe7e4e9cc5a80ea49d8898fcc9e8aeb71a3`.
- Preserve the pre-existing dirty `docs/oscar-alpine-production-ledger.md`
  and all other checkouts. No local Docker daemon retry, K3s modification,
  commit/push, new release or registry operation is authorized in this unit.
- Allowed paths: `Dockerfile`, `ci/runtime_checks.py`, `ci/security.py`,
  `tests/image/test_alpine.py`, `tests/ci/test_security.py`,
  `docs/{container,acceptance,releasing}.md`, this ledger and ignored artifacts/
  graph output.
- Acceptance: retain Python and the three current pinned runtime packages;
  uninstall pip (including its vendored old copies) after build-time dependency
  checks; generate accurate inventory without pip; native runtime validation
  rejects a reintroduced installer; no HIGH/CRITICAL exceptions for new images.
  Preserve ordinary OSCAR/Selkies/upload behavior and all publication gates.
- Unsupported after removal: DEV_MODE and pip-based Docker Mods installation.
  No live-development dependency installation is needed for ordinary OSCAR.
- Stop on real permission/infra/account errors, need for unapproved scope,
  failed final verification or unresolved significant review findings.

## Diagnosis

Read-only live inspection established that active versions already are
msgpack 1.2.4, setuptools 84.2.1 and urllib3 2.8.0. The eight remaining findings
match older vendored copies listed in pip 26.2.2's `_vendor/vendor.txt`.
Even latest pip 26.3 still bundles setuptools 70.3.0; upgrading pip alone
does not remove all findings. Normal Selkies needs Python, not its installer.
Actual removal and a fresh image scan remain to be demonstrated.

## Checklist

- [x] Regression RED → GREEN using real isolated Python/pip, no network.
- [x] Minimal image/runtime/security policy changes and documentation.
- [x] Full static suite and independent review.
- [x] Report local result and remaining native-image validation gate.

## Attempt 1 evidence

All commands used the cwd above and the existing interpreter
`/Users/ondrejvala/projects/oscar/.venv/bin/python`, with
`PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH`.

- Targeted RED: `python -m pytest -q
  tests/image/test_alpine.py::test_final_recipe_removes_installer_without_removing_runtime
  tests/ci/test_security.py::test_former_vendored_high_findings_no_longer_have_runtime_exceptions
  --basetemp=artifacts/pytest-pip-removal-red`, exit 1, six expected failures:
  no actual installer-removal recipe and five retained HIGH exceptions.
  Native output: `artifacts/pip-removal-a1/red.log`.
- Targeted GREEN: `python -m pytest -q tests/image/test_alpine.py
  tests/image/test_runtime_checks.py tests/ci/test_security.py
  --basetemp=artifacts/pytest-pip-removal-green`, exit 0, 55 passed.
  The new offline test creates a real temporary Python venv with bundled pip,
  runs the actual Docker recipe's uninstall and inventory commands, proves
  pip and its vendor directory disappear while Python/a retained runtime module
  remain usable, and executes the actual native child package check before and
  after removal. Wrong required versions still fail.
- Full `python -m ci.check --static-only --out-dir artifacts/pip-removal-static-a1`:
  exit 0, all six groups passed, **454 pytest tests passed in 53.32 s**.
  Receipt `artifacts/pip-removal-static-a1/check.json`; complete `pytest.log`.
- `git diff --check` and `graphify update .`: exit 0. Only documentation/ledger
  bookkeeping after this verification; no executable changes.
- No image build, new vulnerability scan, publication or K3s mutation has run.
  Native startup/functionality plus full image scan are still required to
  establish the final image result.

## Independent review

- Reviewer `ses_e1128b799ffeknR7pvj7dA93S1`: DONE/PASS for bounded local
  acceptance and quality/security; no significant findings or corrections.
  Inspected the real nine-file diff, actual offline uninstall/retention tests,
  all six static checks and the full 454-test log.
- Live/native-image claims remain blocked until a fresh native build, existing
  functional checks and a complete candidate scan. No assertion that all
  vulnerabilities have disappeared or that actual Selkies startup passed yet.
- Attempt 1/2 completed without a correction pass. Commit/push/new release and
  K3s changes have not been performed and require explicit next authorization.

## Integration authorization

- User explicitly approved committing/pushing the reviewed fix and preparing
  release `1.1.1` / image `2.1.1-r9` with fresh native functional checks and
  complete candidate scans. The earlier local-only boundary is superseded for
  that release operation, not for K3s changes.
- Reviewed executable identities remain unchanged; the existing six-group
  static receipt and 454-test result apply. No claim of native-image success
  before that new run finishes.
