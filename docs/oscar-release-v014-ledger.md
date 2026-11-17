# OSCAR-RELEASE-V014

- Owner: coding-standard local version preparation; primary remote integration.
- State: locally verified and reviewed, attempt 1 of 2. Standard ACTIVE.
- Location/cwd: `/Users/ondrejvala/projects/oscar`, local write mode only.
- Approval: user `ano ,pak push a release` approves policy-test correction,
  integration and a fresh release; announced v0.1.4 and image 2.1.1-r5.
- Acceptance: current chart/project 0.1.4, image 2.1.1-r5, OSCAR/appVersion
  unchanged 2.1.1; consistency regression, full native static/pytest suite,
  native Helm 3.19.0/4.3.2 lint/render/package metadata, graph update.
- Allowed local scope: Dockerfile, README.md, pyproject.toml, versions.lock.json,
  charts/oscar/{Chart.yaml,values.yaml}, ci/release.py image literal only,
  tests/ci/test_release.py current-version assertions/fixture literal only,
  tests/chart/test_render.py current-image assertion only, docs/chart.md,
  docs/releasing.md current-version examples only, this ledger, artifacts/,
  generated graphify-out/. No other production behavior changes.
- Preserve all primary simplification/policy changes and dirty historical
  ledgers; never touch unrelated dirty design specification.
- No worker commit/push/tag/gh/auth/dependency installation/helpers.
- Stop on unexpected scope or real account/permission/infra/unsupported
  failures. Primary must review simplification before remote integration.
- Remote acceptance: new tag v0.1.4 at verified pushed commit, pipeline started
  and outcome reported, no existing release/tag/image changes.

## Local preparation attempt 1 — handed back

- Cwd for all commands: `/Users/ondrejvala/projects/oscar`. Initial HEAD
  `7bd835d9d033ded070883a522f03df5340a92051`; existing primary changes and
  unrelated dirty design retained.
- Updated current-version assertion first.
  `.venv/bin/python -m pytest -q tests/ci/test_release.py::test_current_release_versions_are_consistent`
  exited 1: the expected five old project/chart/image values differed.
  After minimal current literals, the identical command exited 0, 1 passed.
  OSCAR and appVersion remain 2.1.1; synthetic historical fixtures remain.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/release-v014-static-a1`
  exited 0, all six groups true, pytest 355 passed in 27.63s. Receipt
  `artifacts/release-v014-static-a1/check.json` identifies HEAD above and
  dirtyDiffSha256 `dc5a31a04d36de1ae98817da86a6cec3472ede890d01b17197e7c595aeeeea49`;
  receipt SHA256 `5a5b95c71d81d170fa0db0ceb2f95365621e97d93c52042011add164f021b539`.
  Ledger and graph updates followed. Existing Hadolint DL3008/DL4006 warnings remain.
- Native Helm command below exited 0; both strict lints passed with informational
  Gateway capability messages. Render supplies the capability explicitly.
  Chart metadata, default image, route and three Longhorn PVCs were asserted.
  Helm 3 package SHA256 `470d1fde5be632ca13a13d9b3493b16b9db08aa0be3bf54cca5598affb5210df`;
  Helm 4 package SHA256 `a64c62797dbdc96d624c84b6e1d89a0373f44b650444205b952b5f25231363d4`.

```sh
set -e
mkdir -p artifacts/release-v014-helm-a1/helm-3.19.0 artifacts/release-v014-helm-a1/helm-4.3.2
cp artifacts/release-v013-helm-a1/values.yaml artifacts/release-v014-helm-a1/values.yaml
for version in 3.19.0 4.3.2; do
  helm=".venv/tools/bin/helm-$version"
  dir="artifacts/release-v014-helm-a1/helm-$version"
  "$helm" version --short
  "$helm" lint --strict charts/oscar -f artifacts/release-v014-helm-a1/values.yaml
  "$helm" template oscar charts/oscar -f artifacts/release-v014-helm-a1/values.yaml --api-versions gateway.networking.k8s.io/v1/HTTPRoute > "$dir/rendered.yaml"
  "$helm" package charts/oscar --destination "$dir"
  "$helm" show chart "$dir/oscar-0.1.4.tgz"
  VERSION="$version" .venv/bin/python - <<'PY'
import os, tarfile
from pathlib import Path
import yaml
p = Path('artifacts/release-v014-helm-a1') / ('helm-' + os.environ['VERSION'])
with tarfile.open(p / 'oscar-0.1.4.tgz') as package:
    chart = yaml.safe_load(package.extractfile('oscar/Chart.yaml'))
    values = yaml.safe_load(package.extractfile('oscar/values.yaml'))
assert chart['version'] == '0.1.4' and chart['appVersion'] == '2.1.1'
assert values['image']['tag'] == '2.1.1-r5'
docs = list(yaml.safe_load_all((p / 'rendered.yaml').read_text()))
dep = next(d for d in docs if d and d.get('kind') == 'Deployment')
assert dep['spec']['template']['spec']['containers'][0]['image'] == 'ghcr.io/frisbeecz/docker-oscar:2.1.1-r5'
route = next(d for d in docs if d and d.get('kind') == 'HTTPRoute')
assert route['spec']['parentRefs'][0]['name'] == 'public'
assert route['spec']['parentRefs'][0]['namespace'] == 'gateway-system'
assert route['spec']['hostnames'] == ['oscar2.homelab-vala.org']
pvcs = [d for d in docs if d and d.get('kind') == 'PersistentVolumeClaim']
assert len(pvcs) == 3 and all(d['spec']['storageClassName'] == 'longhorn' for d in pvcs)
print('verified chart 0.1.4, app 2.1.1, default image r5, route and 3 Longhorn PVCs')
PY
done
```

- `graphify update .` exited 0, AST-only: 675 nodes, 1715 edges; warnings
  for unsupported files, symbol-free `pyproject.toml` and stale labels.
- `git diff --check` exited 0; unrelated design SHA256 remained
  `5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7`.
  Primary owns independent review, integration and remote actions. No worker
  remote actions, commit, push or tag; local verification is not live publication.

## Primary integration gate

- Combined simplification review: coding-review session
  `ses_e16e497f8ffejrrshiuXoSh6mt`, DONE/PASS, no substantive findings.
- Primary inspected actual packages/renders for both Helm versions; matching
  metadata/default image/route/three Longhorn PVCs. Native static result above
  remains valid: no source/test modifications since verification.
- User-approved commit/push and new v0.1.4 tag follow preflight: expected HEAD,
  reviewed file hashes, unchanged unrelated design, remote main and absent tag.
  Existing partial releases and all older tags remain untouched.
