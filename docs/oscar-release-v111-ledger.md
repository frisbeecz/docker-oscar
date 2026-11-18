# OSCAR release v1.1.1

- ID: OSCAR-REL-V111; owner high primary; version-preparation worker when ACTIVE.
- State: preparation DONE 1/2; integration authorized, remote publication pending.
- cwd: `/Users/ondrejvala/.local/share/opencode/worktree/b0fea1/oscar-alpine-production`
- Local base: `3bcb497` (reviewed pip-removal fix committed locally).
- Remote main baseline: `9234afe7e4e9cc5a80ea49d8898fcc9e8aeb71a3`.
- User explicitly approved push plus fresh `1.1.1` / image `2.1.1-r9` release.
  OSCAR/appVersion remains `2.1.1`.
- Allowed preparation paths: Dockerfile version label, pyproject.toml,
  versions.lock.json imageVersion, charts/oscar/{Chart.yaml,values.yaml},
  ci/release.py imageTag literal, tests/ci/test_release.py current-version
  fixtures/assertions, tests/chart/test_render.py image literal,
  docs/{chart,releasing}.md current-version references, this ledger,
  ignored artifacts and generated graph output.
- Keep the reviewed installer-removal/runtime/security code unchanged.
  Preserve pre-existing dirty `docs/oscar-alpine-production-ledger.md`.
  Compose, K3s, historical tags/releases/images and fixed migrate-v102 inputs
  are outside this unit; no authentication/provider/settings changes.
- Preparation acceptance: current versions consistent, existing version test
  RED then GREEN, full static suite and both native Helm package/render
  validations pass. Primary self-reviews the mechanical version diff.
- Publication acceptance: push reviewed fixes/versions, create only fresh
  `v1.1.1`; native AMD64/ARM64 build/functional/full scan gates succeed,
  final non-prerelease and same tested images published to GHCR/Docker Hub.
  Report actual findings; no HIGH/CRITICAL exception or scan suppression.
- Stop on actual permission/account/infra failure, unexpected remote movement,
  failed final verification or partial publication. No retry, overwrite,
  deletion of partial releases or automatic K3s upgrade.

## Preparation attempt 1 evidence

- Mechanical versions prepared: project/chart `1.1.1`, image `2.1.1-r9`;
  OSCAR/appVersion `2.1.1` unchanged. Compose and historical migration
  inputs unchanged. Pre-existing production ledger SHA-256 before and after:
  `cca5b45a50fb50103eb8c47eb9cce641299e09e2e3853a00b31863e5fb3d0731`.
- Existing consistency test failed as expected with old versions (exit 1),
  then passed after the version edits (exit 0, 1 passed):
  `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH /Users/ondrejvala/projects/oscar/.venv/bin/python -m pytest tests/ci/test_release.py::test_current_release_versions_are_consistent -q`.
- Full static command exit 0, all six checks true, pytest 454 passed:
  `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH /Users/ondrejvala/projects/oscar/.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-v111-static-a1`.
- Helm 3.19.0 and 4.3.2 `ci.check --chart` runs exit 0 using kubeconform
  0.8.0; source and packaged strict lint/render/schema matrices and negative
  packaged cases passed. Each packaged chart was inspected with its native
  `helm show chart` and `helm show values`: chart 1.1.1, app 2.1.1, tag
  2.1.1-r9. Artifacts: `artifacts/release-v111-helm-3-a1/` and
  `artifacts/release-v111-helm-4-a1/`; archives SHA-256 respectively
  `5e31d3c0c6ef8124bde2380dee3881922ddb52b47740e77237f777ca5b1fb346` and
  `255b11b88813954cf93f1cabcfe227237d014c4602e8ab9afdeddf33ad8df575`.
- All receipts identify HEAD `3bcb4974ee8fe3db66ec2b50905027578d9f7186`
  and dirty state `f67168d9e1e77aa4cf6a97c4e5ff01236524deede9c5d303734481796df5fb29`
  before this evidence was appended. They are preparation evidence, not
  clean-commit publication receipts; publication gates must run afresh.
- `graphify update .` exit 0: 890 nodes, 2107 edges; warning that community
  labels need refreshing and documentation semantic graph was not refreshed.

## Primary integration gate

- Inspected the complete actual mechanical version diff and all six static
  groups/full 454-test log (50.91 s). Read both native Helm chart/package
  receipts and parsed both actual archives: all exit 0, chart `1.1.1`,
  app `2.1.1`, image tag `2.1.1-r9`.
- Normalizing only the two reviewed version-text substitutions reproduces
  every original pip-removal review hash. Other reviewed source/test files
  and the unrelated dirty production ledger remain byte-identical.
- No source changes after verification. User authorized push and a fresh
  release; preserve previous releases/tags and do not modify K3s or Compose.
