# Production Alpine Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for primary-led execution, or superpowers:subagent-driven-development when selected. Steps use checkbox (`- [ ]`) syntax for tracking. The controller's adaptive routing, single-writer and review limits take precedence over universal per-task reviewer dispatch.

**Goal:** Publish a verified source-built Alpine OSCAR release and then update the existing K3s `oscar2` application without replacing its data.

**Architecture:** Promote the proven build recipe, not the experimental branch wholesale. Keep the existing tested-OCI-artifact release path; perform native image checks once in the release workflow, then publish those same archives. Protect current K3s volumes before switching the pinned chart/image.

**Tech Stack:** Docker multi-stage builds, Alpine/Selkies, Qt6/qmake, Python 3.14, pytest, Trivy, GitHub Actions, Helm 3/4, Argo CD and Longhorn.

**Spec:** `docs/superpowers/specs/2026-11-18-oscar-alpine-production-design.md`

## Global Constraints

- OSCAR stays **2.1.1**, source commit `4f14624616d62c6986788417bc5c519c807a7ade`, archive SHA256 `063b4b6e797d40f8d060453f865fb0e5f48c71cbb72adee0387e76e844313dad`, no source patches.
- Base: `ghcr.io/linuxserver/baseimage-selkies:alpine324@sha256:f2820b8df78eb020785850492c2b6547de2c762fcfcd644b11d4f7e211f5a987`.
- Release/chart/project **1.1.0**; image **2.1.1-r8**; no existing tag, release or registry version is overwritten.
- Keep `/config`, `/config/Documents/OSCAR20_Data`, `/config/SDCARD`; the SD mount remains read-only.
- Keep existing authentication, hardening, UID/GID behavior, source-first publication and final anonymous distribution checks.
- Preserve unrelated dirty files in both repositories; no new credentials, paid services, provider settings or production GUI/CPAP-data tests.
- Native checks cover startup, unprivileged identity, synthetic upload/download, watchdog recovery and synthetic files retained after restart. No Playwright/OCR/real-card-import campaign.
- Each implementation unit has at most two attempts, including review corrections. Real permission/infrastructure failures stop without retries or fallback.

## Review Focus

1. A valid archive name with wrong source bytes must fail before extraction/build; AP1 executes a checksum-failure regression.
2. Source-built receipts must not claim Debian binaries or accept mismatched base/recipe provenance; AP1 mutates real receipt fixtures.
3. Skipping duplicate main-push native builds must never skip native jobs for a release tag; AP1 checks both event contexts and the release dependency closure.
4. A scan for a different image or new critical/unaccepted high findings must not authorize publication; AP1 tests the image-bound security receipt and failed gates.
5. A partial recovery point or changed PVC identity must block K3s cutover/acceptance; AP4 checks captured native snapshot/PVC evidence, including rejected incomplete fixtures.

## Ownership, location and gates

| ID | Owner / mode | Attempts | Acceptance |
|---|---|---|---|
| AP1 | High primary, write | 0/2 | Production source build, provenance, minimal CI and security gates locally verified and independently reviewed |
| AP2 | High primary, operational | 0/2 | New release passes both native paths and publishes the tested archives |
| AP3 | `coding-standard` if ACTIVE, bounded write | 0/2 | Compose pins the verified new published image; native Compose parser tests pass |
| AP4 | High primary, data-sensitive write/operations | 0/2 | Protected existing volumes; GitOps rollout and scoped live verification pass |

Execution is pending approval of this plan and an execution choice.
Create an isolated native worktree named `oscar-alpine-production`, branch
`feat/alpine-production`, from the freshly verified current `origin/main`.
Use the actual directory returned by the worktree tool as cwd for AP1–AP3.
Do not merge/cherry-pick all experiment commits. Carry over the approved
specification/plan and only the explicitly selected recipe/check logic.
Use a small execution ledger in `docs/oscar-alpine-production-ledger.md`.

Observed main is `d6ce76a151439c5209b865aeb4c301a65875c0b0`; recheck it.
Experimental inputs are at commit `3e0a144db3bbd4dfe72a94d2c2759e67514145b2`.
The original upstream checkout has six unrelated dirty documents; the K3s
checkout has three dirty ledgers plus unrelated untracked files. Preserve them.

## File structure

AP1 allowed upstream paths:

- Build/locks: `Dockerfile`, `.dockerignore`, new `python-requirements.txt`,
  `versions.lock.json`, `ci/tools.lock.json`, `pyproject.toml`.
- Receipts/checks: `ci/source_bundle.py`, `ci/runtime.py`, new
  `ci/runtime_checks.py`, new `ci/security.py`, `ci/release.py`.
- Workflows: `.github/workflows/ci.yaml`, `.github/workflows/release.yaml`.
- Version metadata: `charts/oscar/Chart.yaml`, `charts/oscar/values.yaml`.
- Covering tests: `tests/image/test_contracts.py`, `test_integrity.py`,
  `test_debian.py` (replace relevant tests with `test_alpine.py`),
  `test_startup_smoke.py`, new `test_runtime_checks.py`;
  `tests/ci/test_release.py`, `test_policy.py`, new `test_security.py`;
  `tests/chart/test_render.py`.
- Documentation: `README.md`, `NOTICE.md`, `docs/container.md`,
  `docs/acceptance.md`, `docs/releasing.md`, `docs/chart.md`,
  `docs/distribution.md`, approved spec/plan and execution ledger.

AP3 additionally allows only `compose.yaml`, `tests/image/test_compose.py`,
`docs/compose.md` and the ledger.
AP4 cwd is `/Users/ondrejvala/projects/k3s`; allowed tracked changes are
`charts/gitops-apps/templates/oscar2.yaml`,
`charts/gitops-apps/values/{DEV,PROD}/oscar2.yaml`,
`scripts/test-oscar2.sh`, new `docs/oscar2-alpine-upgrade.md` and its ledger.
Ignored `artifacts/`, `.cache/` evidence and AST-only graph updates are allowed.
New scope or other files require a controller decision before edits.

### AP1: Production build, proof and non-duplicated CI

**Interfaces**

- `source_provenance(locked: dict) -> dict` in `ci/source_bundle.py`.
  New `oscar.build` is exactly
  `{"type":"source","recipe":"Dockerfile","pythonRequirements":"python-requirements.txt"}`.
  New provenance contains `type`, `sourceCommit`, `sourceSha256`, `recipe`,
  `pythonRequirements`; no fictional Debian `binaryProvenance`.
- Keep `build_bundle(...)` arguments and source asset names. Emit
  `sourceProvenance` and `checks.sourceProvenance` for the new lock; preserve
  historical Debian receipt handling and saved `verify_published()` behavior.
- `ci.runtime_checks.exercise(container: str, *, phase: str, uid: int, gid: int,
  expected_python: dict, run_id: str, artifacts: Path) -> dict` performs only
  the selected synthetic checks inside the caller's owned CI container.
- Runtime scope becomes `container-functional-v1`. Required checks:
  `containerRunning`, `httpReady`, `oscarStable`, `unprivileged`,
  `uploadRoundTrip`, `watchdogRestart`, `dataRetained`, `sdcardReadOnly`.
  All must be true; no GUI/profile/import acceptance claim.
- `ci.security.scan(image: str, arch: str, out_dir: Path) -> dict` writes the
  full Trivy JSON and an image-bound receipt. `validate_report(report: dict,
  accepted_high: set[str]) -> dict` rejects any critical or unaccepted high
  finding, retaining all findings in the report, not ignoring them.
  The security receipt uses the existing common receipt fields plus `arch`,
  `image`, `configDigest`, `manifestDigest`, `archiveSha256`, `reportSha256`,
  and `checks: {"noCritical": true, "acceptedHigh": true}` on success.
  Require Trivy's observed `Metadata.ImageID` to equal that build's config
  digest. Release verification checks the report hash and matching build
  identity before any publication; do not invent a second digest hierarchy.

- [ ] **1. Prepare isolated production work and freeze reference evidence.**
  Verify main/branch/dirty states, copy the approved documents, preserve original
  checkout hashes and record the successful experimental run `44268476981`.
  Resolve runtime requirements only from the tested files; no new PyPI update.

- [ ] **2. Write source-build/provenance RED tests.**
  Update existing lock/bundle tests rather than duplicating them. Assert the
  pinned two-stage base, checksum failure before extraction/build, unpatched
  qmake recipe, binary/resource/license paths and hash-enforced wheels.
  Extend the fresh-checkout bundle test to require exact wheel-file bytes/hashes.
  Mutate missing/wrong `sourceProvenance` and `origin.base`: release verification
  must reject each; historical saved manifests must still verify.
  Name the executable ordering regression
  `test_wrong_source_hash_stops_before_unpack`; it must assert a nonzero result
  and that inert extraction/qmake tools were never invoked. Add
  `test_release_rejects_source_provenance_mismatch` to the existing real
  receipt fixture. The positive provenance test pins this exact result:

  ```python
  def test_source_provenance_matches_locked_source():
      locked = load_lock()
      assert source_provenance(locked) == {
          "type": "source",
          "sourceCommit": locked["oscar"]["commit"],
          "sourceSha256": locked["oscar"]["sha256"],
          "recipe": "Dockerfile",
          "pythonRequirements": "python-requirements.txt",
      }
      assert "binaries" not in locked["oscar"]
  ```

  Run the named tests in `tests/image` and `tests/ci/test_release.py`;
  retain expected RED evidence before implementation.

- [ ] **3. Promote the tested recipe and provenance.**
  Move the tested wheel file to `python-requirements.txt`; explicitly allow it
  in `.dockerignore` and `SOURCE_FILES`. Keep msgpack 1.2.4, setuptools 84.2.1,
  urllib3 2.8.0 and the tested hashes. Build with qmake6/make and copy runtime
  resources/licenses; keep APK/package inventories and linkage checks.
  Update the base repository/tag/digest, Qt distribution and source-build lock.
  Both pinned base configs independently identify source revision
  `4acbc9ebc23dfdc0ed6f815223f13412bd3735f5`; architecture manifests are
  AMD64 `sha256:42c1a97cc56d2481c0d99bccebf99b4c0bb708ebffa60a2c188f69473bcd33f2`
  and ARM64 `sha256:3b11b11c53f206ab53c86846bb8f993ea07b9fb76a56306c4b4a2a3bb57d0191`.
  Keep archive/base integrity checks and source-first publication.
  Do not claim APK repositories make builds fully reproducible.

- [ ] **4. Write minimal runtime/security/gating RED tests.**
  Exercise real mount-info parsing (including same-device bind mounts),
  diagnostics for missing/inaccessible data, wrong UID/GID, synthetic upload
  round trip, missing retained marker and watchdog replacement.
  Preserve foreign-resource cleanup rejection and receipt/image identity tests.
  Security fixtures: the eight accepted experiment findings pass; a critical,
  unknown high ID, wrong architecture or wrong image identity fails.
  Workflow tests must assert main push skips native builds, tag push and PR
  retain native builds, release still depends on successful tests, no secrets
  reach test jobs and GUI/negative-base helpers remain outside release gates.
  Concrete new names are `test_scan_rejects_wrong_image_identity`,
  `test_runtime_rejects_missing_retained_marker`,
  `test_runtime_rejects_wrong_uid`, and
  `test_native_runs_for_release_but_not_duplicate_main_push`.
  The report gate includes this executable case, plus an unknown-high fixture
  and the full eight-finding positive fixture:

  ```python
  def test_new_critical_report_is_rejected():
      report = {"Results": [{"Vulnerabilities": [{
          "VulnerabilityID": "CVE-SYNTHETIC-CRITICAL",
          "Severity": "CRITICAL",
      }]}]}
      with pytest.raises(ValueError):
          validate_report(report, accepted_high=set())
  ```

- [ ] **5. Integrate one functional pass and one scan per release architecture.**
  Reuse `Resources`, imported OCI identity, startup observation and owned
  cleanup from `ci.runtime`; adapt selected experimental checks for the existing
  test UID/GID **1234:2345**. Do not duplicate the initial startup wait.
  Check restart retention before overwriting a marker/upload. Keep real
  filesystem checks; never restore `os.path.ismount` as the bind-mount gate.
  Keep stdout diagnostics on failure and do not invoke historical GUI routines.
  Pin Trivy 0.76.2 and its two verified binary hashes in the tool lock, using
  the tested download/checksum approach in `ci.security`.
  Accepted high IDs are `CVE-2026-114613`, `GHSA-6v7p-g79w-8964`,
  `CVE-2025-47273`, `CVE-2026-97687`, `CVE-2026-97689`.
  No finding is suppressed; medium/low changes remain visible.
  Tie `security-<arch>.json` to the build's config/manifest identity and require
  it in release verification. Scan only the final candidate, before runtime;
  do not repeat the experiment's Debian/base comparisons.
  Native job condition:
  `github.event_name != 'push' || github.ref != 'refs/heads/main'`.
  Thus main push runs static/Helm checks; the tag release builds/tests each
  architecture once and publishes those exact archives, without another build.

- [ ] **6. Align versions and truthful documentation, then verify locally.**
  Set 1.1.0 / 2.1.1-r8 in the existing version locations and tests. Leave the old
  Compose digest until the new published digest exists. Document source-built
  Alpine, exact automated scope, accepted residual findings and no reproducible
  build/real CPAP-import guarantee.
  Do not change the fixed historical `migrate-v102` tag/digest in
  `ci/dockerhub.py`; it is not the current release version.
  Run in the new production worktree:

  ```bash
  PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH \
    /Users/ondrejvala/projects/oscar/.venv/bin/python -m ci.check \
    --static-only --out-dir artifacts/alpine-production-static
  ```

  Require all six groups and the full pytest suite to pass. Run the existing
  native Helm 3.19.0/4.3.2 lint/template/package validators, `git diff --check`
  and `graphify update .`; no local Docker daemon retry or local native build.

- [ ] **7. Independently review the completed AP1 diff once and integrate.**
  Supply the real diff including new files, frozen source identities, exact
  commands/cwd/exits and acceptance to `coding-review`. Correct significant
  findings only within AP1's two-attempt budget; one scoped re-review at most.
  After PASS and unchanged evidence, commit/push only approved files to main.
  Wait for that exact main CI run once; no release tag if static/Helm fails.

### AP2: Release the tested production images

**Interfaces:** Consumes AP1's integrated main commit and version 1.1.0.
Produces a final release manifest with the published image index digest and
chart identity; AP3/AP4 consume those values, never a guessed digest.

- [ ] **1. Preflight the exact main commit and absence of `v1.1.0`.**
  Confirm version agreement, clean staged state, approved reviewed identity,
  main CI success and no concurrent remote movement. Do not move a tag.
- [ ] **2. Create/push only `v1.1.0` and watch its single release run.**
  Native AMD64/ARM64 each build one OCI archive, scan it once and run the
  minimal functional pass once. Existing release publication consumes these
  same-run artifacts; no new workflow-run API audit or artifact-reuse subsystem.
- [ ] **3. Verify publication before allowing deployment.**
  Require both native jobs, static/Helm and publish success; final non-draft,
  non-prerelease GitHub release; published source assets and manifest;
  anonymous GHCR/Docker Hub matching index digests and chart verification.
  Read full scan receipts. New critical/unaccepted high findings block
  publication; report other security changes rather than hide them.
  Record chart/version/digest and image digest in the ledger.
  Publication failure stops: no delete/retry/overwrite of partial releases.

### AP3: Point Compose at the published Alpine image

**Interfaces:** Consumes AP2's verified index digest and tag 2.1.1-r8.
Produces the same Compose configuration with only its immutable image pin
updated; no new volumes, host bindings, credentials or environment behavior.

- [ ] **1. Update the existing image-pin contract test and observe RED.**
  Require `ghcr.io/frisbeecz/docker-oscar:2.1.1-r8@<verified-index-digest>`;
  retain upload, kiosk, loopback and three-volume assertions.
- [ ] **2. Change only the Compose pin and obsolete guide/version assertions.**
  Use the existing Compose CLI parser; do not pull/run Docker locally.
- [ ] **3. Verify and integrate the bounded change.**
  Run the four Compose parser tests and full native project static suite on
  the changed state; self-review the mechanical diff and preserve other edits.
  Commit/push after PASS. Main CI does not rebuild the unchanged image.

### AP4: Protect current data and update only OSCAR2 through GitOps

**Interfaces:** Consumes AP2's final chart 1.1.0 and exact image digest.
Existing claims are `oscar2-config-v2` (1 GiB), `oscar2-data-v2` (5 GiB),
`oscar2-sdcard-v2` (2 GiB); record fresh UIDs/PV names, never assume old IDs.

- [ ] **1. Read-only deployment preflight and recovery evidence.**
  Verify context, current main/dirty state, Argo Synced/Healthy/no active sync,
  pinned old chart/image, pod count, PVC identities and healthy Longhorn volumes.
  Save manifests and rollback revisions under `.cache/oscar2-alpine-upgrade/`.
  Current Longhorn 1.13.0 supports Snapshot/SnapshotGroup CRs, but neither
  configured backup target is available and these volumes have no last backup.
  Do not repair credentials or call a local snapshot an off-site backup.
  Write the scoped runbook, including abort/recovery actions, before downtime.

- [ ] **2. Prepare and locally verify the GitOps version/digest change.**
  Update the existing OSCAR2 render-test expected version/digest; observe RED.
  Change only upstream chart revision and DEV/PROD image digest. Preserve
  ServerSideDiff, gateway, uploads, kiosk flags, all PVCs and legacy OSCAR.
  Run `HELM_KUBE_VERSION=1.36.4 bash scripts/verify.sh`, server dry-run of the
  rendered Application and diff checks; record a frozen relevant diff.
  Obtain one independent review covering this diff and the data-protection
  runbook. Keep the deployment commit local until the recovery point is ready.

- [ ] **3. Quiesce only OSCAR2 and establish a recovery point.**
  With no active sync, temporarily annotate Application `oscar2`
  `argocd.argoproj.io/skip-reconcile=true`, verify the pause remains effective,
  and gracefully scale only Deployment `oscar2` to zero. Wait for its pods to
  disappear and verify no other pod writes those claims.
  Create a uniquely named Longhorn SnapshotGroup for the freshly resolved
  three exact volume names, `deadlineSeconds: 300`, with migration labels.
  Wait for group `Ready`/`readyToUse: true` and verify all three member snapshots
  reference the expected volumes and are ready with creation times in this
  stopped interval. SnapshotGroup fan-out is not itself atomic/quiescing;
  stopping the only writer is what makes this a consistent recovery set.
  Retain snapshots; do not delete/revert existing storage.
  An evidence check must reject a missing/unready member or a changed PVC UID;
  exercise these rejections on in-memory copies of captured JSON, not the cluster.
  If protection fails before cutover, restore only the recorded replica/pause
  state with the old image, report the blocker and do not deploy Alpine.

- [ ] **4. Push the verified GitOps commit and resume reconciliation.**
  Recheck remote/index/unchanged PVC identities and snapshot readiness.
  Push only the reviewed deployment files; refresh root. Verify the child
  Application now requests the new chart while its reconciliation remains
  paused, then remove only our pause annotation and refresh OSCAR2.
  Stop on unexpected parent reconciliation or concurrent source changes;
  never force-push or apply workload manifests behind GitOps.

- [ ] **5. Perform scoped live acceptance and report.**
  Wait for Synced/Healthy and one available replica with the exact image;
  verify PVC UIDs/specs unchanged, UID/GID, data write access, HTTP, a uniquely
  owned synthetic upload/download and anonymous public authentication denial.
  Remove only the synthetic probe. Do not SIGTERM the live user application,
  read patient records or claim GUI/CPAP/restore tests.
  Verify legacy OSCAR UID/spec/PVCs unchanged and available.
  Record local recovery snapshot IDs, release/deployment revisions, commands,
  exits and remaining security/runtime limits. On failure, stop and report;
  do not blindly restore snapshots or assume an image rollback undoes data.

## Plan self-review

- Spec coverage: source/provenance, minimal native checks, retained scans and
  publication are AP1/AP2; Compose is AP3; recovery, GitOps and live checks AP4.
- No duplicate experiment scans or main-push image builds. Release verifies
  distribution after publishing; that is not a second native application run.
- Source/runtime/security interfaces and new receipt checks are defined above;
  existing public publication fields and historical verification remain usable.
- Recovery protection is explicitly local and conditional; broken unrelated
  backup credentials are neither hidden nor changed.
- Only the approved experimental logic is promoted; original dirty work and
  all old registry/release versions remain intact.
