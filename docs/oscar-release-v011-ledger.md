# OSCAR-RELEASE-V011

- Approval: user approved preparing chart/project `0.1.1`, image `2.1.1-r2`,
  committing/pushing the versions and starting a fresh release by tag `v0.1.1`.
  Preserve partial `v0.1.0`, its tag and all existing registry artifacts.
- Location: `/Users/ondrejvala/projects/oscar`; base
  `295bb2f8550391bd379b883988cfa314635d0373`.
- State: local preparation accepted, attempt 1 of 2; STANDARD ACTIVE.
- Owner: primary controls final integration and remote publication trigger;
  coding-standard owns only the bounded local version-preparation unit.
- Local write scope: `Dockerfile`, `README.md`, `pyproject.toml`,
  `versions.lock.json`, `charts/oscar/Chart.yaml`, `charts/oscar/values.yaml`,
  `ci/release.py` (image-tag literal only), `tests/ci/test_release.py`,
  `tests/chart/test_render.py`, `docs/chart.md`, `docs/releasing.md`,
  this ledger, verification artifacts under `artifacts/`, generated
  `graphify-out/` updates. No auth/publication behavior changes.
- Preserve dirty `docs/superpowers/specs/2026-11-15-oscar-selkies-design.md`,
  SHA256 `5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7`.
- Acceptance: all current release/default/version labels agree on chart/project
  `0.1.1` and image `2.1.1-r2`, OSCAR remains `2.1.1`; synthetic older chart
  fixtures may remain generic. Existing safety gates unchanged. Full pytest
  and native static checks pass; both installed Helm versions lint/render/package
  the updated chart. No tool installation or live registry operation.
- Stop: unsupported/account/permission/infra failure, scope expansion,
  unexpected dirty state, remote main movement or existing new release tag.
  No overwrite, automatic rerun, old-tag movement, release deletion or settings
  changes. At most two implementation attempts; primary owns any correction.
- Remote acceptance after local verification: push the reviewed version commit
  to main, create a new `v0.1.1` at exactly that commit, push only that new tag,
  record the matching Release workflow run and its actual status.

## Local preparation attempt 1

- Cwd for all commands: `/Users/ondrejvala/projects/oscar`. Base HEAD and dirty
  design SHA256 matched the values above; local `v0.1.1` tag absent. Remote
  gates remain with primary; no remote access was performed here.
- TDD: `.venv/bin/python -m pytest -q tests/ci/test_release.py::test_current_release_versions_are_consistent`
  exited 1 before changes (five expected old project/chart/image values), then
  exited 0 after changes (1 passed). Synthetic chart fixtures remain `0.1.0`.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-v011-static-a1`
  exited 0: actionlint, yamllint, hadolint, shellcheck, Python lint and pytest
  passed; pytest 344 passed. Receipt and logs are in that directory. Receipt
  identifies base HEAD and dirtyDiffSha256
  `9a6cb6723acf407cb4e69b0453de910f10e48a33591b23c772c37c1626d07637`;
  ledger and graph changes followed this check. Hadolint warnings remain in log.
- Helm verification command below exited 0. Both strict lints passed (Helm
  logs an informational gateway API failure during lint, whose capabilities
  do not include that API); both actual templates with the supplied API rendered
  the expected route, image and three PVCs. Both packages report chart `0.1.1`,
  app `2.1.1`. Renderings, values and packages are retained under artifacts.

```sh
mkdir -p artifacts/release-v011-helm-a1/helm-3.19.0 artifacts/release-v011-helm-a1/helm-4.3.2
cat > artifacts/release-v011-helm-a1/values.yaml <<'VALUES'
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
  dir="artifacts/release-v011-helm-a1/helm-$version"
  "$helm" lint --strict charts/oscar -f artifacts/release-v011-helm-a1/values.yaml
  "$helm" template oscar charts/oscar -f artifacts/release-v011-helm-a1/values.yaml --api-versions gateway.networking.k8s.io/v1/HTTPRoute > "$dir/rendered.yaml"
  "$helm" package charts/oscar --destination "$dir"
  "$helm" show chart "$dir/oscar-0.1.1.tgz"
  VERSION="$version" .venv/bin/python - <<'PY'
import os
from pathlib import Path
import yaml
p = Path('artifacts/release-v011-helm-a1') / ('helm-' + os.environ['VERSION']) / 'rendered.yaml'
docs = list(yaml.safe_load_all(p.read_text()))
dep = next(d for d in docs if d and d.get('kind') == 'Deployment')
assert dep['spec']['template']['spec']['containers'][0]['image'] == 'ghcr.io/frisbeecz/docker-oscar:2.1.1-r2'
route = next(d for d in docs if d and d.get('kind') == 'HTTPRoute')
assert route['spec']['parentRefs'][0]['name'] == 'public'
assert route['spec']['parentRefs'][0]['namespace'] == 'gateway-system'
assert route['spec']['hostnames'] == ['oscar2.homelab-vala.org']
pvcs = [d for d in docs if d and d.get('kind') == 'PersistentVolumeClaim']
assert len(pvcs) == 3 and all(d['spec']['storageClassName'] == 'longhorn' for d in pvcs)
print('render verified: image r2, HTTPRoute parent/host, 3 longhorn PVCs')
PY
done
```

- `graphify update .`: AST-only graph refresh after edits; result and final
  state identity are supplied in handoff. Full remote strict-schema matrices,
  runtime and release publication remain outside local preparation.
- Worker: `coding-standard`, session `ses_e19b2a439ffeJzvvEPie9dw1GU`,
  DONE_WITH_CONCERNS only for the outstanding remote gates, not local failures.
  Final handoff dirtyDiffSha256
  `f7efdafa79ef0a2392a38e7c4f632f8f826679ecf73a28c664f50d6c833c9f65`.
- Primary inspected the complete relevant diff, native check receipt and pytest
  log, both actual packaged charts and gateway renderings. Acceptance confirmed;
  production logic differs only in version literals. No independent second
  review required for this mechanical bump; prior publisher review stands.
- Primary verification: receipt/package/rendering assertions and
  `git diff --check`, cwd above, exit 0. All six native static groups and 344
  tests passed; no production/test edits after that run. User's dirty document
  hash unchanged. Remote main remained the base SHA, old tag remained
  `24b5a47d99f7522b1cc8202912900049948ae804`, new tag/release absent.
- Integration is explicitly approved: stage only this unit's 12 named paths,
  commit and fast-forward push main, then create/push only new `v0.1.1`.
  No old release/tag/registry modification or automatic recovery is authorized.
