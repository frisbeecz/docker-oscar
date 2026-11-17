# OSCAR-REL-V101

- Location: `/Users/ondrejvala/projects/oscar`.
- Base: `03c4b1b119a164660e02af2bc37a52dbc8df8769`, main.
- Owner: high primary for integration/publication/deletion; coding-standard for
  the bounded mechanical version preparation.
- State: version preparation complete locally, publication pending primary.
  Attempts: 1/2.
- Approval: user accepted `v1.0.1`, image `2.1.1-r6`, tests, push and a fresh
  release pipeline. User explicitly chose deletion rather than deprecation of
  older GitHub releases. Delete only after successful new publication.

## Scope and acceptance

- Prepare chart/project 1.0.1 and container revision 2.1.1-r6; OSCAR/appVersion
  stays 2.1.1. No release-script behavior/security changes.
- Version writer may modify Dockerfile, README.md, pyproject.toml,
  versions.lock.json, charts/oscar/{Chart.yaml,values.yaml}, the image literal
  in ci/release.py, tests/ci/test_release.py, tests/chart/test_render.py,
  docs/{chart.md,releasing.md}, this ledger, ignored artifacts and graph output.
- Keep Compose pinned to its already published r5 digest. Document that
  intentional distinction; do not invent a new image digest.
- Preserve all three pre-existing dirty documents: release simplify ledger,
  v014 ledger, and Selkies design spec.
- Observe version-test RED then GREEN. Run the complete static check suite,
  real Helm 3.19.0/4.3.2 lint/render/package checks, diff check and graph update.
- Primary inspects actual diff/evidence before a scoped commit/push and a NEW
  v1.0.1 tag. Never move or delete a Git tag or overwrite r5.
- Require the new release run to succeed and release-manifest.json plus final
  distribution verification before cleanup. No success claim from local tests.

## Cleanup contract

- Snapshot metadata and download/hash assets of exactly these older releases
  before deleting their release records: v1.0.0, v0.1.4, v0.1.3, v0.1.2,
  v0.1.1, v0.1.0. Keep backups under ignored artifacts/release-v101/.
- Deletion includes release attachments and breaks their old download URLs;
  it does not revoke GHCR images/charts or delete Git tags/commits.
- Do not use --cleanup-tag. Verify tags unchanged and new release retained.
- No K3s changes, auth/provider changes, Docker daemon startup, image overwrites,
  automatic retries, or removal of unrelated work.
- Stop on actual permission/account/infra failure, unexpected remote movement,
  new release failure, or an unapproved destructive change. Report partial state.

## Attempt 1 local evidence

- CWD for all commands: `/Users/ondrejvala/projects/oscar`; base HEAD remains
  `03c4b1b119a164660e02af2bc37a52dbc8df8769` on `main`.
- Updated the current-version assertion first.
  `.venv/bin/python -m pytest -q tests/ci/test_release.py::test_current_release_versions_are_consistent`
  exited 1 with the five expected old metadata/image values; after the bounded
  updates it exited 0, 1 passed.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-v101-static-a1`
  exited 0; receipt and individual logs are in that directory. Full pytest:
  359 passed; all six static checks passed. Hadolint records existing DL3008
  and DL4006 warnings (threshold is error).
- The static receipt identifies the tested pre-ledger-update state with
  `gitCommit` above and `dirtyDiffSha256`
  `92ced9f81b184c21005faa7cb4a3fed5623676c268f44caa289c3538c7b220bb`.
  This ledger evidence was added afterward, so the final dirty identity differs.
- `.venv/tools/bin/helm-3.19.0` and `helm-4.3.2`: strict lint on source
  and packaged chart, template source and package with
  `--api-versions gateway.networking.k8s.io/v1/HTTPRoute` and enabled Gateway,
  package, `show chart` and `show values` all exited 0. YAML assertions
  confirmed chart 1.0.1, app 2.1.1, default/rendered image 2.1.1-r6 and
  HTTPRoute in both templates. Outputs under
  `artifacts/release-v101-helm-a1/{3.19.0,4.3.2}/`.
- `git diff --check` exited 0; `graphify update .` exited 0 with an existing
  community-label drift warning and unsupported-file notices. Code graph
  refreshed; semantic documentation extraction was not run.
- Compose remains pinned to the already released r5 digest. No daemon, cluster,
  remote publication, push, tag or release operation was performed. The new
  release has not been verified remotely.
