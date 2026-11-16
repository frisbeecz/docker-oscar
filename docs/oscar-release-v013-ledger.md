# OSCAR-RELEASE-V013

- Approval: user approved one additional publisher correction (opaque upload
  Location) and committing/pushing it followed by a new release pipeline.
  Use fresh project/chart 0.1.3, image 2.1.1-r4, tag v0.1.3; app stays 2.1.1.
  Existing tags, partial releases and images are immutable for this task.
- Location: /Users/ondrejvala/projects/oscar; base
  ea853e4bd55ddb01cf0025457f3dea0070e981e4. STANDARD ACTIVE.
- Unit attempt 1 of 2: local mechanical version preparation only. Primary
  retains ownership of publisher attempt 3 (one explicitly authorized extra
  attempt, no further corrections), review, integration and remote actions.
- Allowed writes: Dockerfile, README.md, pyproject.toml, versions.lock.json,
  charts/oscar/Chart.yaml, charts/oscar/values.yaml, ci/release.py (image
  literal only), tests/ci/test_release.py, tests/chart/test_render.py,
  docs/chart.md, docs/releasing.md (current version examples only), this
  ledger, artifacts/ verification outputs, graphify-out/ generated updates.
- Preserve in-progress primary correction in ci/chart_registry.py,
  tests/ci/test_chart_registry.py, docs/releasing.md, publisher ledger and
  v012 ledger. Preserve unrelated dirty design document SHA256
  5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7.
- Acceptance: all current versions agree on 0.1.3 / 2.1.1-r4. Historical
  ledgers and synthetic older fixtures stay unchanged. Real-version test
  RED/GREEN; full static checks/pytest; both native Helm 3.19.0 and 4.3.2
  strict lint/template/package with gateway and three Longhorn PVCs.
- Required verification: .venv/bin/python -m ci.check --static-only
  --out-dir artifacts/release-v013-static-a1; native Helm commands and
  exact cwd/exits recorded; git diff --check; graphify update . (AST only).
- Single writer slot; no helpers, remote access, installs, commits, push,
  tags, publication, auth changes or retries for worker. Stop on unexpected
  scope/state, permission/account/infra/unsupported failure.
- Primary remote gate: inspect actual diff and native receipts, review new
  security-boundary relaxation, preserve dirty design, preflight remote
  main/new tag, commit only named task files and push fast-forward main,
  then create/push only new v0.1.3 at verified commit and watch its run.
  Any failure stops; do not overwrite/recover earlier releases automatically.

## Local preparation attempt 1

- Cwd for all commands: `/Users/ondrejvala/projects/oscar`. Initial
  `git status --short; git rev-parse HEAD; shasum -a 256 docs/superpowers/specs/2026-11-15-oscar-selkies-design.md; if test -f graphify-out/graph.json; then graphify query 'release version consistency chart image preparation' ; fi`
  exited 0; dirty files matched the contract, HEAD was
  `ea853e4bd55ddb01cf0025457f3dea0070e981e4` and design SHA256 matched.
- Updated the real-version consistency assertion first.
  `.venv/bin/python -m pytest -q tests/ci/test_release.py::test_current_release_versions_are_consistent`
  exited 1 with five expected old values, then after the version literals
  were updated exited 0, 1 passed. Synthetic old package fixtures remain;
  the publication test's current image-tag matching literal followed the bump.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-v013-static-a1`
  exited 0: all six groups passed, including full pytest, 363 passed in
  30.11s. `artifacts/release-v013-static-a1/check.json` records HEAD above
  and dirtyDiffSha256 `ba3b6677aae05f870d6cb1c557b25d7cb1094db0660c56e0a624709710669e12`;
  it includes the primary publisher correction. Ledger and graph were updated
  after this check. Hadolint logged pre-existing DL3008 and DL4006 warnings.
- The following complete native Helm command exited 0. Both strict lints
  passed, with informational Gateway capability messages; both templates
  supplied that capability. Both package metadata, default image, route and
  three Longhorn PVCs were asserted. Outputs remain in the named artifacts.

```sh
mkdir -p artifacts/release-v013-helm-a1/helm-3.19.0 artifacts/release-v013-helm-a1/helm-4.3.2
cat > artifacts/release-v013-helm-a1/values.yaml <<'VALUES'
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
  dir="artifacts/release-v013-helm-a1/helm-$version"
  "$helm" version --short
  "$helm" lint --strict charts/oscar -f artifacts/release-v013-helm-a1/values.yaml
  "$helm" template oscar charts/oscar -f artifacts/release-v013-helm-a1/values.yaml --api-versions gateway.networking.k8s.io/v1/HTTPRoute > "$dir/rendered.yaml"
  "$helm" package charts/oscar --destination "$dir"
  "$helm" show chart "$dir/oscar-0.1.3.tgz"
  VERSION="$version" .venv/bin/python - <<'PY'
import os, tarfile
from pathlib import Path
import yaml
p = Path('artifacts/release-v013-helm-a1') / ('helm-' + os.environ['VERSION'])
with tarfile.open(p / 'oscar-0.1.3.tgz') as package:
    chart = yaml.safe_load(package.extractfile('oscar/Chart.yaml'))
    values = yaml.safe_load(package.extractfile('oscar/values.yaml'))
assert chart['version'] == '0.1.3' and chart['appVersion'] == '2.1.1'
assert values['image']['tag'] == '2.1.1-r4'
docs = list(yaml.safe_load_all((p / 'rendered.yaml').read_text()))
dep = next(d for d in docs if d and d.get('kind') == 'Deployment')
assert dep['spec']['template']['spec']['containers'][0]['image'] == 'ghcr.io/frisbeecz/docker-oscar:2.1.1-r4'
route = next(d for d in docs if d and d.get('kind') == 'HTTPRoute')
assert route['spec']['parentRefs'][0]['name'] == 'public'
assert route['spec']['parentRefs'][0]['namespace'] == 'gateway-system'
assert route['spec']['hostnames'] == ['oscar2.homelab-vala.org']
pvcs = [d for d in docs if d and d.get('kind') == 'PersistentVolumeClaim']
assert len(pvcs) == 3 and all(d['spec']['storageClassName'] == 'longhorn' for d in pvcs)
print('verified chart 0.1.3, app 2.1.1, default image r4, route and 3 Longhorn PVCs')
PY
done
```

- `graphify update .` exited 0, AST-only: 665 nodes, 1722 edges. It warned
  about unsupported files, symbol-free `pyproject.toml` and stale community
  labels; no semantic relabel performed.
- `git diff --check` exited 0; final design SHA256 remained
  `5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7`.
  Remote publication, correction review and integration remain with primary.

## Primary integration gate

- Worker ses_e1973734bffe1kCFKnbwnHCuM2 returned writer slot, local preparation
  accepted after primary inspected actual diff, full native check receipt and
  pytest log: 363 passed/all six groups true. Primary independently read both
  actual Helm packages and render artifacts and asserted chart/app/image,
  expected route and three Longhorn PVCs; command cwd above, exit 0.
- Publisher relaxation received DONE/PASS read-only review in session
  ses_e19c10578ffe0kV5R0zJVe1Bsb. Local PASS is not evidence of live GHCR
  success; actual previous Location is still unknown.
- Primary review-state SHA256 validation and git diff --check exited 0;
  unrelated design SHA256 unchanged. Existing hadolint warnings are unchanged.
- Approved integration: commit only the named version/correction/own-ledger
  files, fast-forward push main, tag that exact commit with fresh v0.1.3 and
  push only that new tag. Preserve all earlier tags/releases/images.
