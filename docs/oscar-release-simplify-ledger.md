# OSCAR-RELEASE-SIMPLIFY

- Approval: user requested overall simplification and answered `ok` to the
  in-chat design: GitHub `needs` gates publication, publish tested artifacts
  and corresponding sources, remove duplicate checks/CDN handling, retain one
  final standard-tool verification. No commit, push, tag or release authorized.
- Location/cwd: `/Users/ondrejvala/projects/oscar`, base
  `7bd835d9d033ded070883a522f03df5340a92051`.
- Owner: high primary (release credentials/artifact integrity). STANDARD ACTIVE.
  Single writer; no active workers. This is one explicitly approved additional
  implementation attempt after the previous publisher budget was exhausted;
  no automatic extra correction/release attempt.
- Allowed write scope: `.github/workflows/{ci,release}.yaml`,
  `ci/{release,chart_registry}.py`, `tests/ci/{test_release,test_chart_registry}.py`,
  `docs/releasing.md`, this ledger, verification `artifacts/`, generated
  `graphify-out/`. Preserve dirty v013 outcome ledger and unrelated design.
- Acceptance: normal CI jobs unchanged; publication depends on successful CI;
  no API-based job-result audit/evidence job; validate local tested artifacts
  once before mutation; sources public before binary publication; no rebuild,
  credential leak, overwrite recovery, auth changes or custom CDN downloads.
  Retain final image identity and native Helm pull/package checksum verification.
  Preserve release-manifest artifact identities/run reference; per-job URLs are
  no longer collected (document this).
- Verification: behavior RED/GREEN; full native `ci.check --static-only`;
  real Helm compatibility tests; actual diff review covering acceptance/security;
  `git diff --check`; AST-only `graphify update .`.
- Stop: scope mismatch, account/permission/infra failure, significant unresolved
  review finding or failed final verification. No live publication proof claimed.

## Progress

- Read actual workflows, publisher and tests; checked GitHub Actions docs:
  `needs` skips dependents on failure/skip and artifact downloads default to the
  current run. Existing checkout has only dirty v013 ledger and design document.
- Attempt: additional approved attempt in progress.

## Implementation and verification — BLOCKED

- Removed Actions API job audit/evidence job and its artifact/CLI command,
  redundant pre-publish workflow verification step, duplicate registry readbacks,
  repeated source bundle validation and second source download. CI build/smoke
  jobs are unchanged. Publish now validates local inputs once and uses one final
  Skopeo/Helm verification. Chart uploader no longer downloads blobs or handles
  CDN redirects. Simplified current release documentation.
- Native cwd for all commands: location above.
  `.venv/bin/python -m pytest -q tests/ci/test_chart_registry.py::test_publish_leaves_blob_downloads_to_the_helm_consumer tests/ci/test_release.py::test_publish_uses_workflow_gate_without_separate_job_evidence --basetemp=artifacts/pytest-release-simplify-red`
  exited 1: two expected RED failures (custom blob GET and required job evidence).
  Log: `artifacts/release-simplify-a1/red.log`.
- `.venv/bin/python -m pytest -q tests/ci/test_chart_registry.py tests/ci/test_release.py --basetemp=artifacts/pytest-release-simplify-green`
  exited 0: 117 passed, including native Helm 3.19.0/4.3.2 pulls and checks that
  failed Helm pulls, modified packages or changed chart manifests prevent finalization.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-simplify-static-a1`
  exited 1: full pytest had 352 passed, 3 failed. The failures are outdated policy
  expectations in `tests/ci/test_policy.py`, not uploader failures:
  `test_minimal_job_permissions` still requires now-unused actions:read;
  `test_release_dependency_closure` still requires removed evidence job;
  `test_publication_inputs_are_data` still requires duplicate verify workflow step.
  Exact evidence: `artifacts/release-simplify-static-a1/pytest.log`.
- Stop after failed full verification; no hidden correction attempt. Updating
  these policy assertions requires extending the allowed test path and explicit
  approval to continue. Independent review has NOT run; no PASS/completion claim.
- `git diff --check` exited 0. `graphify update .` exited 0, AST 671 nodes/1709
  edges; symbol-free file and stale-label warnings only, no LLM relabel.
  Unrelated dirty design SHA256 unchanged:
  `5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7`.
- No versions changed, commits/push/tags/releases/registry/auth/cluster actions.

## Authorized continuation

- User: `ano ,pak push a release` explicitly approves the policy-test
  correction after failed verification, then commit/push/new release.
- Extend scope to `tests/ci/test_policy.py`. Primary owns this one authorized
  correction attempt; existing three failures are its RED evidence.
- Prepare fresh chart/project v0.1.4 and image 2.1.1-r5 in the established
  version files only after corrected verification. Existing published versions
  remain unchanged. Review the complete simplification before integration.
- Corrected policy expectations retain minimal permissions, mandatory native
  and Helm/static jobs, success-gated publication and three same-run artifact
  downloads before publishing. No production changes in this correction.
- `.venv/bin/python -m ci.check --static-only --out-dir
  artifacts/release-simplify-static-a2`, cwd above, exit 0: all six groups pass;
  full pytest 355 passed. Base 7bd835d, receipt dirtyDiffSha256
  8b4a594c076fbe82a11cdde8527015e6cc0c4ddea474cfe3f4eece2bd716f09b.
  Local simplification ready for combined version verification and review;
  previous BLOCKED result above is superseded locally, not live publication.

## Integration gate

- Combined version verification: `.venv/bin/python -m ci.check --static-only
  --out-dir artifacts/release-v014-static-a1`, cwd above, exit 0; all six
  groups and full pytest 355 passed. Base 7bd835d, dirtyDiffSha256
  dc5a31a04d36de1ae98817da86a6cec3472ede890d01b17197e7c595aeeeea49.
- Complete relevant diff (including new ledgers):
  `artifacts/release-simplify-review/review.diff`, SHA256
  6e0f28511a853143193c7e8b3601bdc5a3ffc54461ae5ecb545b57212d8c2b74;
  source/workflow/test/doc identities in adjacent `review-state.sha256`.
- Independent coding-review session `ses_e16e497f8ffejrrshiuXoSh6mt`:
  DONE/PASS, no substantive acceptance, quality or security findings.
  Live release acceptance remains pending, not inferred from local checks.
- Primary independently inspected both native Helm packages/renders and
  verified chart/app/image versions, requested route and three Longhorn PVCs.
- No source/test changes after final native checks and review. Only own
  ledgers/evidence updated. User's unrelated dirty design remains excluded.
- User approved push and fresh release. Integration will preserve all older
  partial releases, tags and images; no auth settings or cluster mutation.
