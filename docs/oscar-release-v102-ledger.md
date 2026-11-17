# OSCAR-REL-V102

- Location: `/Users/ondrejvala/projects/oscar`.
- Base: `8ec43dff226060f1fdb9cd81a5ec6a3229ded75f`, branch `main`.
- Approval: user explicitly approved preparing and launching a fresh release
  after the Docker Hub/Artifact Hub integration was pushed.
- Decision: chart/project `1.0.2`, image `2.1.1-r7`, OSCAR/app `2.1.1`.
- State: LOCAL VERIFIED; publication pending; implementation attempt 1/2.
- Owner: high primary controls integration and remote publication; bounded
  mechanical version preparation is delegated to coding-standard (ACTIVE).

## Scope and acceptance

Allowed local writes: `Dockerfile`, `pyproject.toml`, `versions.lock.json`,
`charts/oscar/Chart.yaml`, `charts/oscar/values.yaml`,
`ci/release.py` (image-version literal only), `tests/ci/test_release.py`,
`tests/chart/test_render.py`, `docs/chart.md`, `docs/releasing.md`,
this ledger, ignored verification artifacts and generated graph updates.

Preserve the reviewed Docker Hub implementation, chart discovery annotations,
all four pre-existing dirty documents, existing tags/releases, Compose pins,
registry/account settings and K3s. No release behavior changes or new builds
outside the existing release workflow.

Use the existing current-version regression test for RED/GREEN, the full native
static/test gate, and both installed Helm versions for strict lint, render,
package and metadata validation. Parent inspects actual diff and evidence
before committing only scoped files, pushing main, creating the new `v1.0.2`
tag and triggering its release workflow.

Live completion requires successful CI/publish, final non-prerelease status,
and a release manifest recording both architectures, image `2.1.1-r7`,
chart `1.0.2`, the approved Docker Hub repository and verified distribution.
Artifact Hub registration is user-reported; catalog indexing is asynchronous,
not guaranteed merely by a Git push.

Stop on unexpected dirty scope, concurrent remote movement, actual permission,
quota or infrastructure failure, unsupported worker, or final verification
failure. No automatic retry, tag replacement, old-release deletion or hidden
third implementation attempt. Context7 remains unavailable from its earlier
quota failure; use already retrieved official documentation as needed.

## Attempt 1 local evidence — BLOCKED

- CWD `/Users/ondrejvala/projects/oscar`; HEAD
  `8ec43dff226060f1fdb9cd81a5ec6a3229ded75f`. Initial dirty state was
  exactly the four documented files and this untracked ledger.
- Updated current-version assertion first; `.venv/bin/python -m pytest -q
  tests/ci/test_release.py::test_current_release_versions_are_consistent`
  exited 1 with five expected old version values. After the scoped mechanical
  changes, the same command exited 0, one test passed.
- `.venv/bin/python -m ci.check --static-only --out-dir
  artifacts/release-v102-static-a1` exited 0, all six checks passed and full
  pytest reported 367 passed. Hadolint has pre-existing DL3008/DL4006 warnings.
  Receipt `dirtyDiffSha256` is
  `9eeb90741d19885d11fbdc54024e7e5bc5cf712c9782555b0fb37a2720d7b7c9`,
  before this ledger update.
- Helm verification command stopped with exit 1 at Helm 3.19.0 route render:
  `template oscar charts/oscar --kube-version 1.36.4 --api-versions
  gateway.networking.k8s.io/v1/HTTPRoute --set gateway.enabled=true --set
  'gateway.parentRefs[0].name=test-gateway'`. The supplied route values omit
  required `gateway.hostnames`; schema reports `minItems: got 0, want 1`.
  Source strict lint and default render succeeded before the failure. Logs and
  partial renders are in `artifacts/release-v102-helm-a1/3.19.0/`. No retry,
  package, Helm 4 verification, or graph update was performed.
- `git diff --check` exited 0 before this ledger append. No commit, push, tag,
  live publication, daemon or cluster operation was performed.

## Controller verification closure

The worker returned its writer slot. Inspection of the actual full version
diff and schema failure confirmed an incomplete verification command, not a
production defect. No further implementation or product/test edit was needed.
The full 367-test receipt therefore remains applicable to the unchanged code.

Controller verification, same CWD, all exit 0:

- For each `.venv/tools/bin/helm-3.19.0` and `helm-4.3.2`: `version --short`,
  `lint charts/oscar --strict`, default `template` with namespace `oscar` and
  kube version `1.36.4`; route `template` additionally supplies
  `--api-versions gateway.networking.k8s.io/v1/HTTPRoute`,
  `--set gateway.enabled=true`,
  `--set 'gateway.parentRefs[0].name=test-gateway'` and
  `--set 'gateway.hostnames[0]=oscar.example.test'`.
- `package charts/oscar`, strict lint of the resulting `oscar-1.0.2.tgz`,
  `show chart`, and default template from the actual package.
- Python parsed both actual archives and all six manifests: chart `1.0.2`,
  app `2.1.1`, image `2.1.1-r7`, preserved Artifact Hub annotations, expected
  default absence/explicit presence of HTTPRoute all passed.
- `graphify update .` and `git diff --check`.

Artifacts: `artifacts/release-v102-helm-verified/<helm-version>/`,
`result.json` and `graphify.log`. Initial incomplete command evidence is kept,
not overwritten. Mechanical version-only self-review found no additional
scope or behavior changes; the independent Docker Hub/security review of the
previous commit still applies. User approval covers scoped commit, push and a
fresh `v1.0.2` tag; existing tags/releases and deployments remain untouched.
