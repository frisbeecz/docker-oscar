# Production Alpine migration

Status: approved in conversation on 2026-11-18, with the clarification below.

## Intent and approval boundary

The user accepts the experiment's remaining security findings and requests:
promote the tested Alpine build to main; if verification succeeds, publish a
new release; only after successful publication, deploy it to K3s.

This specification covers that production migration, not further vulnerability
remediation. The user approved the proposal after clarifying that native checks
mean minimal checks of the final image on real AMD64/ARM64, not repeating the
whole experiment or testing patient data. The implementation plan and execution
selection still require approval. Existing unrelated edits must remain untouched.

Design gates:

- [x] Review the experiment, production build/provenance and current K3s state.
- [x] Write and self-review this proposed specification.
- [x] User approval of the written specification and minimal-test clarification.
- [ ] Write the implementation plan; obtain approval and execution selection.
- [ ] Execute the approved migration with recorded verification.

## Evidence and limits

Experiment commit `3e0a144db3bbd4dfe72a94d2c2759e67514145b2`, Actions run
https://github.com/frisbeecz/docker-oscar/actions/runs/44268476981:

- Native AMD64 and ARM64 source builds succeeded.
- Both runtime probes passed: unprivileged OSCAR, HTTP, nested web uploads,
  watchdog relaunch and synthetic files retained across container restart.
- Trivy 0.76.2, DB updated 2026-11-18T07:15:21Z, reports 0 critical,
  5 high, 2 medium and 1 low findings for each Alpine candidate.
- The active application environment uses msgpack 1.2.4, setuptools 84.2.1 and
  urllib3 2.8.0. The scanner still detects older versions elsewhere in the image;
  their exact paths have not been established. Do not suppress these findings
  or describe the image as vulnerability-free.
- Automated checks do not establish browser visual correctness, real CPAP
  import correctness or production-data restore compatibility.

## Chosen design

Promote the experimentally verified LinuxServer Alpine/Selkies base and native
OSCAR source build. Do not replace Selkies with a newly designed desktop stack,
run Debian binaries through compatibility shims or apply OSCAR source patches.

### Image and provenance

- Pin the tested Alpine base index:
  `sha256:f2820b8df78eb020785850492c2b6547de2c762fcfcd644b11d4f7e211f5a987`.
- Keep OSCAR 2.1.1 and source commit
  `4f14624616d62c6986788417bc5c519c807a7ade`, archive SHA256
  `063b4b6e797d40f8d060453f865fb0e5f48c71cbb72adee0387e76e844313dad`.
- Use a multi-stage native musl/Qt6 build, copying only the compiled application,
  required application resources and licenses into the runtime stage.
- Keep the tested hash-pinned Python wheel refresh in `/lsiopy`; do not introduce
  an unbounded package upgrade or claim that it removes all scan findings.
- Update lock validation, source bundles, provenance checks and tests to describe
  a source-built Alpine image honestly instead of official Debian binary inputs.
  Include the exact build recipe and dependency inputs in corresponding-source
  publication. Keep existing published-release verification compatible.
- Preserve paths `/config`, `/config/Documents/OSCAR20_Data` and `/config/SDCARD`,
  UID/GID handling, non-recursive data ownership safeguards and runtime hardening.

### CI and release

- Proposed release/chart/project version: **1.1.0**.
  Proposed image tag: **2.1.1-r8**. OSCAR/appVersion stays **2.1.1**.
- Adapt existing production CI and artifact/provenance gates; do not merge the
  experiment wholesale or bypass a failing check.
- Require native AMD64 and ARM64 builds and runtime checks, full project tests,
  Helm validation and a retained security report before publication.
- Report security changes relative to the accepted experiment. Material new
  deterioration, particularly new critical findings, requires renewed approval.
- Exercise web uploads, single-process watchdog recovery and synthetic retained
  data on disposable CI volumes. Preserve least-privilege workflow permissions
  and secret isolation.
- Preserve source-first release publication and publish the tested images/chart,
  without another image rebuild, to GHCR and the existing Docker Hub target
  `frisbeecz24/docker-oscar`. Synchronize existing repository documentation.
- Final anonymous image/chart verification must pass before considering the
  release successful. Artifact Hub discovers the new chart asynchronously;
  indexing is not equivalent to an immediate new audit.
- Update main's Compose immutable image pin after the new published index digest
  is known. Never substitute an invented digest, move an old tag or overwrite an
  existing release.

### K3s deployment and data

- Current preflight: `oscar2` is Synced/Healthy, one instance is available and
  its existing config/data/SD claims are Bound at 1/5/2 GiB. A supported recovery
  mechanism has not yet been established; do not assume a backup is configured.
- Update only the existing `oscar2` GitOps application to the successfully
  published chart and exact image digest. Leave legacy `oscar` unchanged.
- Preserve all three existing PVCs, names, UIDs, capacities and mount roles.
  Preserve the hostname, Cloudflare Access boundary, upload directory and kiosk
  settings. Do not change authentication, providers or storage ownership.
- Before switching, establish and record a consistent recovery point for config
  and data. Prefer supported existing storage backup/snapshot facilities; a local
  snapshot must not be described as an independent backup. If recovery protection
  cannot be established safely, stop before workload cutover.
- Record the old image/chart/Git revisions. Allow a controlled brief outage for
  singleton `Recreate` deployment and consistency protection; never run two
  OSCAR instances concurrently against the same writable data.
- Verify Argo Synced/Healthy, rollout, unchanged PVC identities, unprivileged
  process, data write permissions, HTTP, synthetic upload/download and public
  authentication boundary. Do not inspect patient records or simulate a crash
  against live user data.
- On failed live acceptance, stop and report the exact state. Any rollback must
  use the recorded old image and protected data state, not assume that reverting
  an image reverses application data changes.

## Acceptance

1. Production source build, lock, receipts, licenses and documentation agree.
2. Full local validation and both native CI paths pass on the integrated state.
3. Recorded scan findings remain visible; accepted residual risk is not hidden.
4. New release publication and anonymous distribution verification succeed.
5. Only then is `oscar2` updated; existing data and legacy OSCAR are preserved.
6. Deployment verification passes, or an explicit blocker/failed state is reported.

## Execution boundaries

Use isolated production work based on current main, preserving the experiment
and unrelated dirty checkouts. Track implementation, release and deployment as
bounded units with explicit acceptance and at most two implementation attempts
per unit. Significant findings or failed final verification stop the unit;
additional attempts require user authorization.

Do not start paid services, change credentials/permissions, delete old images,
remove PVCs or alter unrelated applications. Do not continue from experiment
success directly to production without the approved implementation plan.
