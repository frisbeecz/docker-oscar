# OSCAR-DISTRIBUTION

- Location: `/Users/ondrejvala/projects/oscar`.
- Base: `08d48f053b323df00c3a4d11152adefa56590777`, branch `main`.
- Owner: high primary; exclusive writer. STANDARD remains ACTIVE.
- State: DONE locally, implementation attempt 1/2; independent review PASS.
- Approval: user approved preserving GHCR, mirroring the tested multi-platform
  image to `frisbeecz24/frisbeecz`, and adding Artifact Hub metadata and
  registration instructions. The `DOCKERHUB_TOKEN` repository secret exists;
  its value was not read. No commit, push or release is authorized by this unit.

## Scope and acceptance

Allowed writes: `.github/workflows/release.yaml`, `ci/release.py`,
`tests/ci/test_release.py`, `tests/ci/test_policy.py`,
`charts/oscar/Chart.yaml`, `docs/releasing.md`, `docs/distribution.md`,
this ledger, ignored `artifacts/distribution-a1/` and verification outputs,
and generated graph updates.

1. Keep the existing CI dependency, source-first publication, tested image
   identities and GHCR chart/image distribution.
2. Use existing pinned Skopeo to copy the complete index from its GHCR digest
   to Docker Hub with `--all --preserve-digests`; never rebuild, use `latest`,
   disable TLS or add automatic retries/recovery.
3. Expose the Docker Hub token only to the publish step, pass it on stdin,
   and keep registry credentials within the existing temporary auth directory.
4. Record the mirror repository in the release manifest and anonymously check
   its tagged index against the same digest before finalizing the release.
   Saved pre-mirror manifests remain verifiable.
5. Supply valid chart discovery metadata and accurate instructions for a
   one-time Artifact Hub OCI registration. Do not claim registration,
   verified-publisher status or live Docker Hub publication.
6. Preserve existing dirty documents, deployed K3s state, Compose image pins,
   chart/project/image versions, registry settings and all existing releases.

## Validation and stops

Use TDD at the actual subprocess/workflow boundaries, run the full native
static/test command and validate packaged chart metadata with both installed
Helm versions. Independent review covers acceptance and security.

Stop on real permission, quota or infrastructure failure, unexpected changes,
or a final verification failure; no hidden third attempt. Context7 previously
exhausted its quota; following the user's explicit alternative-documentation
request, official GitHub CLI, Skopeo and Artifact Hub documentation is used
without retrying Context7 or changing providers/settings.

References:
- https://github.com/containers/skopeo/blob/main/docs/skopeo-copy.1.md
- https://artifacthub.io/docs/topics/repositories/helm-charts/
- https://artifacthub.io/docs/topics/annotations/helm/

## Attempt 1 evidence

All commands ran in the location above:

- Targeted TDD RED: `.venv/bin/python -m pytest -q
  tests/ci/test_release.py tests/ci/test_policy.py -k 'dockerhub or
  unapproved_mirror or saved_ghcr'
  --basetemp=artifacts/pytest-distribution-red`, exit 1; eight expected failures,
  including no mirror, no missing-token rejection and no scoped workflow secret.
  `artifacts/distribution-a1/red.log`.
- Targeted GREEN: `.venv/bin/python -m pytest -q tests/ci/test_release.py
  tests/ci/test_policy.py --basetemp=artifacts/pytest-distribution-green`,
  exit 0, 93 passed. `artifacts/distribution-a1/green.log`.
- Full native gate: `.venv/bin/python -m ci.check --static-only
  --out-dir artifacts/distribution-static-a1`, exit 0; all six static groups
  succeeded, full pytest **367 passed** in 32.89 seconds.
  `artifacts/distribution-static-a1/{check.json,pytest.log}` records base
  `08d48f053b323df00c3a4d11152adefa56590777` and dirty diff
  `ea5676ba873ebf9f21b81aa883bda55c231aaa890affad8999d5a2ca55cc2a5e`.
- Both installed native Helm versions, 3.19.0 and 4.3.2: `version --short`,
  `lint charts/oscar --strict`, `package charts/oscar`, `show chart` on the
  resulting archive, and `template` of that archive with Kubernetes 1.36.4,
  all exit 0. Actual packaged annotations parse as valid YAML links and the
  rendered image remains unchanged. Exact commands/output are represented by
  `artifacts/distribution-a1/helm-*/` and `helm-results.json`.
- `git diff --check` and `graphify update .`, exit 0. Graph update used AST only;
  existing symbol-free pyproject/community-label warnings were informational.
- All four pre-existing dirty documents match
  `artifacts/readme-pro-a1/integration-untouched.json`.

No live login/push, token read, account/visibility change, new release,
Artifact Hub registration or Docker/K3s runtime operation was performed.
Native subprocess doubles cover Docker Hub success/failure and do not prove
the token's push permissions or a successful live publication.

## Independent review and handoff

Read-only reviewer `ses_e148e1499ffeXjsWsQ1jkpl5J9` returned DONE:
acceptance PASS and quality/security PASS, no material findings or blocking
local evidence gaps. It inspected the completed diff, native receipts and
both packaged Helm outputs without rerunning commands. Seven frozen source
identities are recorded in `artifacts/distribution-a1/review-state.json`;
the actual reviewed diff is `review.diff`, SHA256
`5538f1e693e9fce5f42de99c5365972edb9c8e400f6f05737d1d1beef9acb9d8`.

No product/test changes followed verification or review. Only this ledger was
updated with the result. Commit/push authorization remains pending. A future
fresh version/release is required for live publication; the already published
chart version must not be replaced. Docker Hub permissions/public visibility
and Artifact Hub registration remain operator/live-release acceptance items.

## Integration authorization

The user explicitly approved commit and push, then paused to clarify Artifact
Hub registration. After receiving the exact OCI registration URL, the user
confirmed completing that one-time step with “hotovo”. Registration is
user-reported, not independently verified. Resume the approved commit/push of
only the eight scoped files; do not create a tag or run a new release.

Before integration, the seven reviewed source identities, successful native
367-test receipt, all four unrelated dirty document identities, clean Git
index and unchanged remote `main` were verified. No product/test files changed
after their recorded verification and review.
