# Acceptance evidence

## Current scope: `container-functional-v1`

Each native release job builds the production Alpine image from the locked,
checksum-verified, unpatched OSCAR source. The same OCI archive is imported,
scanned, exercised and ultimately published; there is no publication rebuild.
Local tests validate the harness, not a native container execution.

Main pushes run static/Helm checks without duplicate native builds. Release tags
and PRs retain both native architectures: GitHub-owned `ubuntu-24.04` for AMD64
and `ubuntu-24.04-arm` for ARM64, never emulation.

### One functional pass

The harness owns one uniquely named container and three fresh named volumes,
with UID1234/GID2345, loopback-only HTTP, software rendering, no host data mounts,
no Docker socket, no privilege escalation and NET_RAW dropped. It checks:

1. Running container and HTTP200 within the bounded readiness period.
2. Exactly one unprivileged `/usr/bin/OSCAR20` process with the intended data
   directory, unchanged `(pid,start)` for at least ten monotonic seconds.
3. Actual config/data read-write and SD read-only mounts through Linux mountinfo,
   including same-filesystem bind mounts; writable data for the application UID.
4. One uniquely owned nested synthetic browser upload, exact downloaded bytes
   and file listing. Commands/application launch APIs remain disabled.
5. Controlled termination of only that CI-owned OSCAR process, followed by one
   stable watchdog replacement.
6. One container restart and both synthetic files still present with exact bytes,
   checked before any overwrite.

The runtime receipt requires eight strict booleans: `containerRunning`,
`httpReady`, `oscarStable`, `unprivileged`, `uploadRoundTrip`, `watchdogRestart`,
`dataRetained`, `sdcardReadOnly`. Process identity, initial observation duration,
source state and OCI/archive identity must match the build. Diagnostics survive
missing/inaccessible data paths. Owner-checked cleanup is mandatory; cleanup
failure invalidates success. Existing receipts are never overwritten.

### One full security scan

Before functional checks, Trivy 0.76.2 scans the final candidate once per native
architecture. The complete JSON report and DB metadata are retained; the receipt
binds its SHA256, image configuration, manifest, archive and architecture.
Publication revalidates the report before any external mutation.

All critical and new/unaccepted high advisory IDs block publication. The user
accepted these inherited high IDs, without suppressing their report entries:

- `CVE-2026-114613`
- `GHSA-6v7p-g79w-8964`
- `CVE-2025-47273`
- `CVE-2026-97687`
- `CVE-2026-97689`

The successful exploratory Alpine run still reported five high, two medium and
one low finding, even though the active Python environment used newer pinned
packages. Do not call those findings false positives or claim all vulnerable
copies were removed. Counts change with DB updates and are not equivalent
coverage across distributions.

### Other release gates

| Gate | Required evidence |
| --- | --- |
| Local contracts | Full pytest image/chart/CI suite, real lint tools and native receipt |
| Helm | 3.19.0 and 4.3.2 strict render/schema matrix and exact packaged archives |
| Sources | Exact upstream archive/COPYING, source-build recipe and Python requirements, pinned base and packaging-input hashes |
| GitHub | Successful dependency graph in the same release run; no independent job-result API audit |
| Publication | Public source assets first; tested platform digests preserved; final anonymous image/mirror/chart verification |

Release accepts only the current functional runtime scope. Read-back verification
of previously published `startup-smoke-v1` manifests remains supported, without
relabeling those old checks as new coverage.

## Not proven by this scope

No decoded GUI/media, real SD-card/CPAP import, medical correctness, patient
profile/database migration, backup restore or Kubernetes installation/routing
is proven by these receipts. Retaining synthetic files after restart is not a
complete application-data migration or restore test. No private medical data
belongs in CI. Legacy GUI/negative/Kubernetes helpers remain non-gating utilities.

Keep the separate [backup/migration cautions](migration.md), [container guide](container.md)
and [license/source obligations](../NOTICE.md). A pinned base and source hash do
not make live APK repositories bit-reproducible or prove redistribution compliance.

## Inspect evidence

See [releasing](releasing.md) for commands. Record exact commit, run/attempt,
architecture, command/cwd/exit and file digests. Downloaded GitHub artifacts are
under `artifacts/{static,sources,chart,native}`; ZIP digests do not replace
receipt/OCI/archive validation. Missing runners, unsupported tools or genuine
permission/infrastructure failure mean BLOCKED, never substitution or PASS.
