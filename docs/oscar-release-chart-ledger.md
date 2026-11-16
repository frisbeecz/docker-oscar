# OSCAR-CHART-PUBLISH

- Owner: high primary, session `ses_e1a0097b2ffe2E6AFmEXhmFxg2`.
- State: local correction DONE, live publication unverified, attempt 2 of 2.
  Standard ACTIVE, not dispatched:
  publication credentials and artifact integrity require high ownership.
- Approval: user approved direct version-tag manifest upload, a regression
  test and exact downloaded-package verification. No automatic retry,
  release/image deletion, remote publication, push or tag movement.
- Location: `/Users/ondrejvala/projects/oscar`; local write mode.
- Allowed scope: `ci/chart_registry.py`, `ci/release.py`,
  `tests/ci/test_chart_registry.py`, `tests/ci/test_release.py`,
  `docs/releasing.md`, this ledger, verification output under `artifacts/`,
  generated `graphify-out/` updates.
- Preserve existing dirty
  `docs/superpowers/specs/2026-11-15-oscar-selkies-design.md`.
- Acceptance: unchanged tested chart bytes; correct Helm config/layer media
  types; publish manifest directly by version tag (no untagged-manifest GET);
  authenticated tag/config/layer digest verification and exact chart
  download; retain source-first, same-run gates, isolated credentials and
  fail-closed behavior. No retries or credential-bearing redirects.
- Verification: RED/GREEN regression; actual Helm pull against local registry
  fixture; full pytest suite; project static checks; independent read-only
  review with diff and native evidence; graphify update.
- Stop: unexpected scope, account/permission/infra failure; no publication
  recovery without separate approval. Maximum two implementation attempts.
- Diagnosis: Release 43951305732 attempt 2, `ci/release.py:281`:
  Helm 4.3.2/ORAS ExtendedCopy tags by fetching the just-uploaded digest;
  fetch returned `not found`. GHCR's server-side reason is not established.
- Evidence (cwd above): `.venv/bin/python -m ci.check --static-only --out-dir
  artifacts/chart-publish-static-a1`, exit 0; full pytest 343 passed, including
  native Helm 3.19.0 and 4.3.2 pulls. All six static check groups passed.
  Receipts: `artifacts/chart-publish-static-a1/check.json`, `pytest.log`.
  Base commit `24b5a47d99f7522b1cc8202912900049948ae804`;
  check receipt dirtyDiffSha256
  `9d3b3a5b2fba1f7b268a7e17d28bcde3585ea6a6f9c36982b70e7d8387374399`.
- Review 1: read-only `coding-review`, session
  `ses_e19c10578ffe0kV5R0zJVe1Bsb`; complete relevant diff and per-file hashes in
  `artifacts/chart-publish-static-a1/review.diff` and `review-state.sha256`.
- Graph maintenance: `graphify update .`, cwd above, exit 0; AST-only graph
  rebuilt to 648 nodes / 1699 edges. Community names may need relabeling;
  no LLM labeling or provider settings changed.
- Review 1 result: DONE / PASS; no blocking acceptance, correctness,
  regression or security findings. Reviewer inspected supplied diff, native
  receipts and related workflow without executing commands.
- Remaining limits: no live GHCR verification or publication/recovery;
  existing-tag refusal is a preflight check, not atomic against out-of-band
  writers (same-tag workflow runs are serialized). Historical RED runs were
  observed by primary, not independently evidenced in review logs.
- No commit, push, tag movement, release rerun or cluster mutation performed
  for this local implementation unit. Original K3s deployment is not complete.
- Follow-up approval: user explicitly approved committing and pushing this
  reviewed fix to the existing `main` branch. Scope remains these six files;
  existing partial release and tags must remain unchanged. Before integration,
  all five reviewed source/doc file hashes matched the tested state and remote
   `main` still matched base `24b5a47d99f7522b1cc8202912900049948ae804`.

## Attempt 2: GHCR upload Location compatibility

- User requested correction after live run `43963535729` failed in the
  Location validator. High primary owns this final correction; original
  acceptance, local paths and stop conditions above remain in force.
- Base `23bb0f97e2bfc20cc900f15e065f3bfe5d2e3655`. Preserve the dirty
  v0.1.1 outcome ledger and unrelated design document.
- Evidence: GHCR's published HTTP transcript at
  https://gist.github.com/shizhMSFT/b77f2d7f993268a1bdd45a7462866906
  shows POST `/blobs/uploads/` returning Location `/blobs/upload/<uuid>`
  (singular). OCI Distribution v1.1.1 POST-then-PUT requires using the
  returned Location. Current validator rejects this documented GHCR shape.
  The failing run did not log its Location, so its exact response is unknown.
- Correction stays within approved design: accept singular and plural upload
  endpoints only within the same HTTPS host and exact chart repository;
  preserve the returned Location and query, no authenticated redirect/retry.
  Add full-protocol regression and negative destination tests. No live
  diagnostic upload, release rerun, commit/push, tag or version change yet.
- Native verification, cwd above:
  - `.venv/bin/python -m pytest -q tests/ci/test_chart_registry.py::test_ghcr_singular_upload_location_preserves_tested_chart --basetemp=artifacts/pytest-chart-publish-a2-red`
    exited 1 before correction: four expected `unsafe registry upload location`
    failures, preserved in `artifacts/chart-publish-a2/red.log`.
  - `.venv/bin/python -m pytest -q tests/ci/test_chart_registry.py --basetemp=artifacts/pytest-chart-publish-a2-green`
    exited 0 after correction: 38 passed (`green.log` beside RED log).
  - `.venv/bin/python -m ci.check --static-only --out-dir artifacts/chart-publish-static-a2`
    exited 0: all six groups passed, full pytest 355 passed; includes native
    Helm 3.19.0 and 4.3.2 compatibility pulls. Receipt dirtyDiffSha256
    `fc6b5500dbca118682aded838e913c9ffd5b0ac67a02af649f587ed6988e2cba`.
  - `git diff --check` exited 0. `graphify update .` exited 0, AST-only
    rebuild to 655 nodes / 1711 edges; no semantic relabel or API changes.
- Scoped re-review: `coding-review`, session `ses_e19c10578ffe0kV5R0zJVe1Bsb`,
  DONE / PASS, no substantive findings. Full correction diff and verified
  source/doc hashes: `artifacts/chart-publish-a2/review.diff` and
  `review-state.sha256`. No production/test changes after native verification.
- Remaining limitation: documented GHCR compatibility is corrected locally,
  but the failing live response is unavailable and publication is not verified.
  Existing partial releases, tags, image versions and cluster remain unchanged.
- Integration approval: user explicitly approved committing/pushing this
  reviewed correction to main and launching a new release pipeline. Preserve
  partial v0.1.0/v0.1.1 releases and old tags/images; prepare a fresh chart/project
  0.1.2 with image 2.1.1-r3 before the new v0.1.2 tag. The approved correction
  is not further modified; publisher attempt budget remains 2 of 2.
- Final live acceptance FAILED: Release 43967243767 (v0.1.2 at ea853e4)
  still rejects upload Location in ci/chart_registry.py:110. All six
  test/evidence jobs pass, but actual Location remains absent from log.
  State BLOCKED, attempt budget 2/2 exhausted. No third implementation or
  remote retry/recovery. Full outcome/partial publication is recorded in
  docs/oscar-release-v012-ledger.md.

## User-authorized additional attempt 3 (one additional attempt only)

- User explicitly approved removing guessed upload-path/identifier formatting
  and requested committing the correction and launching a fresh release.
  Owner remains high primary, same cwd and local scope; no budget reset.
- New acceptance: treat registry-provided upload suffix and query as opaque;
  keep HTTPS, same GHCR origin, exact repository blob subtree, no traversal,
  no credential redirects, unchanged bytes/digests and no retries.
  Add safe rejection reasons without printing signed URLs or credentials.
- Current live Location is still unavailable; do not claim its exact shape.
  Reproduce the known overconstraint using opaque IDs, trailing slashes and
  request-relative Locations, and preserve all existing negative checks.
- Verify RED/GREEN, full native static/pytest checks and inspect relevant diff.
  A further failure is BLOCKED, not permission for another correction.
- New publication will use a fresh v0.1.3 / image 2.1.1-r4, preserving every
  existing tag, partial release and image. Version preparation is separate
  mechanical scope; remote actions only after native checks pass.
- Attempt 3 local verification (same cwd): four expected RED cases for opaque
  suffix/relative Locations, then 46 targeted passes. Artifacts:
  artifacts/chart-publish-a3/red.log and green-final.log. An old negative
  fixture's path was corrected to actually escape the blob subtree; internal
  request-relative normalization within the same subtree is intentionally valid.
- Full integrated `.venv/bin/python -m ci.check --static-only --out-dir
  artifacts/release-v013-static-a1` exited 0: all six groups passed, full
  pytest 363 passed. Receipt base ea853e4, dirtyDiffSha256
  ba3b6677aae05f870d6cb1c557b25d7cb1094db0660c56e0a624709710669e12.
- Review of the newly approved opaque-URL acceptance: coding-review session
  ses_e19c10578ffe0kV5R0zJVe1Bsb, DONE/PASS; no substantive findings.
  Relevant complete diff artifacts/chart-publish-a3/review.diff SHA256
  86cc012e42dde88bfae0871a1e5c33624fc4f6a2a69fe08ff205d2980bc24015;
  all review-state.sha256 entries matched after review. No source/test changes
  after verification/review. Live publication remains unverified.
