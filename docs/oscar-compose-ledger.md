# OSCAR-COMPOSE

- Location: `/Users/ondrejvala/projects/oscar`
- Base: `551e0397fcca4f268c563a8846a3cb254b1c2b2e`
- Owner: high primary; single writer.
- Approval: user approved a loopback-only Compose example with published image,
  persistent volumes, browser uploads and window recovery, README Quick Start,
  and explicitly requested a separate Compose guide.
- Scope: `compose.yaml`, `README.md`, `docs/compose.md`,
  `tests/image/test_compose.py`, this ledger; ignored `artifacts/` and generated
  graph updates for verification.
- Preserve: existing dirty release ledgers and design document. No K3s, image,
  chart, authentication, provider, Docker plugin/settings, release or tag changes.
- Attempts: 1/2, DONE locally; scoped integration subsequently authorized below.

## Acceptance and checks

- Use the released multi-platform `2.1.1-r5` image, pinned by index digest.
- One OSCAR service, loopback TCP port 3000, three fresh named volumes with
  SD read-only, 512 MiB shared memory, no privileged/host/socket/device access.
- Preserve unprivileged desktop/root init, hardening, automatic application
  restart, hidden window buttons, middle-click recovery and working keyboard
  configuration. Confine browser upload/download to `/config/Uploads`.
- Explain prerequisites, Quick Start, SD directory import, ownership,
  persistence/capacity, stopping, backup/restore precautions, upgrades and
  authenticated HTTPS for any remote access.
- TDD against real Compose normalization, then the project's complete static
  checks/full pytest suite, documentation link checks and independent review.
- No container startup or host-volume mutation is needed for this configuration
  and documentation task. Do not claim fresh Compose runtime/GUI acceptance.

## Environment

- `docker compose` is not registered in this local Docker CLI.
- Existing standalone `docker-compose` is available, version 5.7.1; use its
  equivalent native `config` command without installing/configuring a plugin.

## Stop conditions

Stop on actual account/permission/infrastructure errors, unsafe side effects,
unrelated concurrent changes or a failed final verification requiring a new
strategy; report evidence rather than silently broadening scope.

## Attempt 1 verification

All commands used the Location above.

- RED: `.venv/bin/python -m pytest -q tests/image/test_compose.py
  --basetemp=artifacts/pytest-compose-red`, exit 1, four expected missing-Compose
  failures; `artifacts/compose-a1/red.log`.
- GREEN: the same four real-parser tests with
  `--basetemp=artifacts/pytest-compose-green`, exit 0, four passed;
  `artifacts/compose-a1/green.log`.
- `.venv/bin/python -m ci.check --static-only --out-dir
  artifacts/compose-static-a1`, exit 0: all six lint/test groups succeeded,
  full pytest **359 passed in 29.29s**. Receipt base matches this ledger;
  dirty identity `c40b349ddf07e7a8ddf9b53657e5bac286ed29bd2292273add0f8355625b7c6a`.
- `docker-compose --env-file /dev/null --project-name oscar-compose-check
  --file compose.yaml config --quiet`, exit 0. Equivalent JSON rendering
  retained in `artifacts/compose-a1/config.json`; standalone CLI 5.7.1.
- `git diff --check`, exit 0.
- `graphify update .`, exit 0, AST graph refreshed; harmless symbol-free
  `pyproject.toml` and stale community-label notices. No LLM relabeling/settings.

No container, image download/build, volume, cluster or authentication mutation
was performed.

## Acceptance closure

- Independent read-only review `ses_e15c36ab1ffeyJ6vWJdmNMozYw`: DONE,
  acceptance PASS and quality/security PASS; no actionable findings or fixes.
- The reviewer inspected the actual complete diff
  `artifacts/compose-a1/review.diff` (SHA256
  `0402c7285d9a23ba9228d052d566c8e9dad87596b806c1ef42c36504c7e9c066`),
  native Compose model and test receipts.
- README/Compose-guide relative links and anchors passed validation. The
  one-off validator initially mistook the valid `charts/oscar` directory link
  for a required file; allowing directory links resolved the validator error
  without changing source.
- Source hashes in `artifacts/compose-a1/review-state.sha256` remain the
  tested/reviewed state. No source or test changes after the green full suite.
- Existing dirty design SHA256 remains
  `5e3bba2c09fc67623d1ef0ad1b593b6483de517514fc802cab26982489d79be7`;
  pre-existing release-ledger changes were not included or modified.
- Remaining limitations: localhost is unauthenticated, storage is finite,
  watchdog recovery does not handle a still-running hung application, and no
  fresh Compose runtime/import/persistence/restore acceptance was performed.
- Files remain local and uncommitted; no push, release or K3s change.

## User-requested parity and integration gate

User subsequently requested verification against the deployed Helm behavior
(browser uploads, single-application window controls/recovery), then push.
This authorizes the scoped commit/push after verification. No new product
behavior or image/chart changes are proposed; implementation remains attempt 1.

- Compare the real Compose model with the actual Helm rendering using the K3s
  PROD OSCAR2 overrides, including image, upload path/permissions, kiosk flags,
  storage targets and shared memory.
- Check local Docker availability before any isolated runtime probe. If it is
  available, use only a unique test project and fresh test volumes; never touch
  existing containers/volumes or K3s data.
- Respect the existing failure stop conditions; do not start/reconfigure Docker
  or install a plugin to bypass unavailable infrastructure.
- Do not claim literal unclosability: keyboard shortcuts remain intentionally
  enabled, window buttons are hidden and the watchdog relaunches an exited app.

### Gate results and explicit continuation

- Real Helm render: `.venv/tools/bin/helm-4.3.2 template oscar2 charts/oscar
  --namespace oscar2 --kube-version 1.36.4 --api-versions
  gateway.networking.k8s.io/v1/HTTPRoute --values
  /Users/ondrejvala/projects/k3s/charts/gitops-apps/values/PROD/oscar2.yaml`,
  exit 0; output `artifacts/compose-a1/parity-helm.yaml`.
- Real Compose JSON normalization, exit 0; comparison of image digest,
  PUID/PGID, 9 desktop/upload flags, mount targets/read-only modes and 512 MiB
  shared memory PASS in `artifacts/compose-a1/parity-result.json`.
- Intentional differences: UTC default vs Prague override, Docker named volumes
  vs Longhorn PVCs, local unauthenticated loopback vs authenticated HTTPS gateway.
  Compose explicitly disables commands/Apps; Helm uses the same hardened image's
  defaults. Single-instance behavior is one Compose service vs Helm replica 1
  with Recreate.
- `docker info --format '{{.ServerVersion}}'`, exit 1: local
  `/var/run/docker.sock` is absent. Stopped without retry, Docker startup,
  configuration changes or alternate runtime.
- After being told the blocker and asked whether to push without local runtime
  verification, user explicitly answered **"push"**. Resume scoped integration
  only; do not retry the failed Docker availability check.
- Integration preflight: correct repository/main/base, unchanged remote main,
  clean index, exact scoped dirty-file set, reviewed source hashes unchanged,
  full passing test receipt and parity result checked. Preserve all three
  pre-existing dirty documents.
