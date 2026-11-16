# OSCAR-RELEASE-V012

- Approval: user approved committing/pushing the reviewed GHCR correction and
  launching a new release pipeline. Prepare new chart/project `0.1.2`, image
  `2.1.1-r3`, tag `v0.1.2`; keep OSCAR/appVersion `2.1.1`. No overwrite of
  partial releases `v0.1.0`/`v0.1.1`, their tags or existing images.
- Location: `/Users/ondrejvala/projects/oscar`; base
  `b7ec923c5c8ca0ea5d765fe4880434ceddab8a46` (reviewed correction pushed).
- State: local preparation DONE, attempt 1 of 2; STANDARD ACTIVE.
- Owner: primary owns integration, remote preflights and new-tag trigger;
  coding-standard receives the single writer slot for local mechanical
  version preparation and native verification only.
- Allowed writes: `Dockerfile`, `README.md`, `pyproject.toml`,
  `versions.lock.json`, `charts/oscar/Chart.yaml`, `charts/oscar/values.yaml`,
  `ci/release.py` (image-tag literal only), `tests/ci/test_release.py`,
  `tests/chart/test_render.py`, `docs/chart.md`, `docs/releasing.md`,
  this ledger, verification outputs under `artifacts/`, generated
  `graphify-out/` updates. No publication/auth behavior changes.
- Preserve dirty `docs/superpowers/specs/2026-11-15-oscar-selkies-design.md`
  SHA256 `5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7`.
- Acceptance: all current project/chart/image labels, defaults and release
  literals agree on new versions. Preserve historical receipts/ledgers and
  synthetic older package fixtures. Use existing v0.1.1 preparation pattern;
  update real-version consistency test first and observe expected RED.
  Full project static checks/pytest pass, native Helm 3.19.0 and 4.3.2
  lint/render/package agree on new versions and expected route/Longhorn PVCs.
- Verification: `.venv/bin/python -m ci.check --static-only --out-dir
  artifacts/release-v012-static-a1`, native Helm commands recorded with exits,
  `git diff --check`, `graphify update .` (AST only). No installs required.
- Stop: scope expansion, unexpected dirty state, account/permission/infra/
  unsupported failure; no helpers, remote access, commit/push/tag/registry
  changes or retry. Publisher correction budget remains 2 of 2, exhausted;
  this unit only changes version literals and verifies existing behavior.
- Remote gate: primary inspects actual diff/evidence and unchanged dirty doc,
  checks remote main/new-tag state, then commits/pushes prepared versions,
  creates and pushes only fresh `v0.1.2` at that exact commit. Record actual
  Release run/status. Failure means stop/report partial state, not recovery.

## Local preparation attempt 1

- Cwd for every command below: `/Users/ondrejvala/projects/oscar`. Initial
  `git status --short --untracked-files=all`, `git rev-parse HEAD` and
  `shasum -a 256 docs/superpowers/specs/2026-11-15-oscar-selkies-design.md`
  exited 0: only the expected dirty design and untracked ledger; HEAD and
  design SHA256 matched the contract.
- Updated the real current-version assertion first.
  `.venv/bin/python -m pytest -q tests/ci/test_release.py::test_current_release_versions_are_consistent`
  exited 1 with five expected old project/chart/image values, then exited 0
  after literal updates, 1 passed. Synthetic older chart fixtures and generic
  version validation remain unchanged.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-v012-static-a1`
  exited 0: six static groups passed, including full pytest, 355 passed in
  28.41s. Receipt/logs are in that directory; receipt identifies base HEAD and
  dirtyDiffSha256 `9d553ab511096a48d13c129e2b5b9f5d83d0c69cf6d4fe9f5ad13fb2ff09595e`.
  The ledger and generated graph were updated after that check. Hadolint
  warnings remain in its log.
- The following complete Helm command exited 0. Both strict lints passed;
  lint logged an informational Gateway API capability message. Both real
  templates supplied the API explicitly and verified image r3, route host and
  parent, and three longhorn PVCs. `show chart` reported chart 0.1.2 and
  appVersion 2.1.1 for both packages. Artifacts are retained at the paths below.

```sh
mkdir -p artifacts/release-v012-helm-a1/helm-3.19.0 artifacts/release-v012-helm-a1/helm-4.3.2
cat > artifacts/release-v012-helm-a1/values.yaml <<'VALUES'
gateway:
  enabled: true
  parentRefs:
    - name: public
      namespace: gateway-system
  hostnames:
    - oscar2.homelab-vala.org
persistence:
  config:
    storageClass: longhorn
  data:
    storageClass: longhorn
  sdcard:
    storageClass: longhorn
VALUES
set -e
for version in 3.19.0 4.3.2; do
  helm=".venv/tools/bin/helm-$version"
  dir="artifacts/release-v012-helm-a1/helm-$version"
  "$helm" lint --strict charts/oscar -f artifacts/release-v012-helm-a1/values.yaml
  "$helm" template oscar charts/oscar -f artifacts/release-v012-helm-a1/values.yaml --api-versions gateway.networking.k8s.io/v1/HTTPRoute > "$dir/rendered.yaml"
  "$helm" package charts/oscar --destination "$dir"
  "$helm" show chart "$dir/oscar-0.1.2.tgz"
  VERSION="$version" .venv/bin/python - <<'PY'
import os
from pathlib import Path
import yaml
p = Path('artifacts/release-v012-helm-a1') / ('helm-' + os.environ['VERSION']) / 'rendered.yaml'
docs = list(yaml.safe_load_all(p.read_text()))
dep = next(d for d in docs if d and d.get('kind') == 'Deployment')
assert dep['spec']['template']['spec']['containers'][0]['image'] == 'ghcr.io/frisbeecz/docker-oscar:2.1.1-r3'
route = next(d for d in docs if d and d.get('kind') == 'HTTPRoute')
assert route['spec']['parentRefs'][0]['name'] == 'public'
assert route['spec']['parentRefs'][0]['namespace'] == 'gateway-system'
assert route['spec']['hostnames'] == ['oscar2.homelab-vala.org']
pvcs = [d for d in docs if d and d.get('kind') == 'PersistentVolumeClaim']
assert len(pvcs) == 3 and all(d['spec']['storageClassName'] == 'longhorn' for d in pvcs)
print('render verified: image r3, HTTPRoute parent/host, 3 longhorn PVCs')
PY
done
```

- `graphify update .` exited 0, AST-only: 657 nodes, 1712 edges; it warned
  about skipped unsupported files, symbol-free `pyproject.toml`, and stale
  community labels. No LLM labeling was performed.
- `git diff --check` exited 0. Remote checks, commit, tag, publication and
  live pipeline remain with primary; no remote access was performed here.

## Primary integration gate

- Worker `ses_e199aedb6ffe1w3lXaQ0LGsdOZ` returned writer slot with
  DONE_WITH_CONCERNS limited to outstanding remote publication. Primary accepted
  local preparation after inspecting actual complete version-only diff,
  check.json and pytest log (355 passed, all six check groups true).
- Primary read both native Helm packages and rendered resources with
  `.venv/bin/python -` (tarfile and YAML assertions), cwd above, exit 0:
  chart 0.1.2/app 2.1.1, default image r3, requested HTTPRoute and three
  Longhorn PVCs all match. No unchanged native suite rerun.
- Existing hadolint DL3008/DL4006 warnings concern unchanged Dockerfile line 15;
  no new lint errors. Helm capability and graph-label warnings remain recorded.
- Primary `git diff --check`, clean-index check, dirty-design SHA256 and
  `git ls-remote origin refs/heads/main refs/tags/v0.1.2` exited 0:
  main is expected base b7ec923, new tag absent, unrelated design unchanged.
- Approved next remote operations: commit only this unit's twelve named files,
  fast-forward push main, create new local v0.1.2 at that exact commit and push
  only that new tag. Observe corresponding Release run; never rerun old runs,
  move tags, overwrite/delete partial releases or alter credentials/settings.

## Integration and new pipeline

- Primary committed the twelve approved unit files:
  `ea853e4bd55ddb01cf0025457f3dea0070e981e4`, then
  `git push origin HEAD:refs/heads/main`, `git tag v0.1.2 <commit>` and
  `git push origin refs/tags/v0.1.2:refs/tags/v0.1.2` all exited 0, cwd above.
- Read-back `git ls-remote` confirms main and new v0.1.2 at ea853e4;
  v0.1.0 remains 24b5a47, v0.1.1 remains 23bb0f9. Only unrelated design
  document was dirty after integration (before this outcome note).
- `gh run list --repo frisbeecz/docker-oscar --workflow release.yaml
  --branch v0.1.2 --commit ea853e4bd55ddb01cf0025457f3dea0070e981e4
  --event push --limit 5 --json databaseId,status,conclusion,headSha,headBranch,url,attempt`
  exited 0: fresh run 43967243767, attempt 1, queued at the expected commit.
  https://github.com/frisbeecz/docker-oscar/actions/runs/43967243767
- Pipeline outcome/public publication remains unverified until run completion.

## Remote outcome: BLOCKED

- Watch `gh run watch 43967243767 --repo frisbeecz/docker-oscar
  --exit-status --interval 30` completed exit 1; no watcher remains active.
  All six static/Helm/native/evidence jobs succeeded; publish failed.
- Primary read-only `gh run view 43967243767 --repo frisbeecz/docker-oscar
  --log-failed` and `gh release view v0.1.2 --repo frisbeecz/docker-oscar
  --json tagName,isPrerelease,isDraft,publishedAt,url,assets` exited 0, cwd above.
  At 2026-11-16T22:17:30Z `ci/chart_registry.py:110` rejected the returned
  upload Location even with the singular/plural correction:
  `ValueError: unsafe registry upload location`. Actual Location still was
  not logged; no precise rejected URL component can be established.
- Before failure both platform image pushes and index push succeeded in logs;
  image 2.1.1-r3 index digest
  `sha256:dc64796dbd893bff3dde2bace1010772802b02fdb03930195a162c581757b2e2`.
  Anonymous image availability has not been independently verified.
- Prerelease v0.1.2 exists, non-draft, with six source assets; no
  release-manifest.json. Failure occurs before chart blob PUT/manifest PUT,
  so this run did not publish the chart manifest; upload session may remain.
- Publisher attempt 2 of 2 has failed live acceptance: BLOCKED. No third
  implementation, rerun, new version/tag, release deletion or registry/auth
  changes performed. K3s deployment remains pending.
