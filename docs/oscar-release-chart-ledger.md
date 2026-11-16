# OSCAR-CHART-PUBLISH

- Owner: high primary, session `ses_e1a0097b2ffe2E6AFmEXhmFxg2`.
- State: DONE locally, attempt 1 of 2. Standard ACTIVE, not dispatched:
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
