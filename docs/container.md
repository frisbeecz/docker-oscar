# Container, sources and native acceptance

## Operating boundary

The image keeps the upstream `/init`, unprivileged `abc` desktop and watchdog.
`PIXELFLUX_WAYLAND=true`, `RESTART_APP=true`, `HARDEN_DESKTOP=true`,
`START_DOCKER=false`. Do not turn off hardening to make a test pass.
The Wayland autostart shell stays alive while the launcher runs, matching
the base watchdog's process contract.

Set PUID/PGID to the required application ownership (chart defaults 1000:1000;
the base alone defaults to 911:911), TZ to a valid IANA zone. Base init can require root to establish
ownership; this is not a promise of Pod Security Restricted / runAsNonRoot
compatibility. The application is unprivileged. Do not use privileged,
host networking, host data mounts, Docker socket, or GPU passthrough.
Disable privilege escalation; restrict capabilities only as supported by
verified init requirements. Native tests set no-new-privileges and drop NET_RAW.

Use three separate volumes, with SD read-only. The data and SD mounts are
**nested inside** config: backing up the config volume does **not** back up
the mounted data or SD volume. One writer only. Kubernetes must use singleton
and Recreate, stable generation-v2 claims and no ephemeral data fallback.

The image's ordered `init-oscar-data` oneshot runs after base UID/GID/custom
initialization and before desktop services. Base `lsiown` owns `/config` itself,
not the nested data volume. The hook creates missing managed directories and
sets only their own ownership; for an existing data directory it changes only
an **empty root:root directory root** to the actual remapped `abc` UID/GID.
It never recursively chowns/chmods, copies, imports or migrates data. Existing
nonempty directories (including hidden entries or `lost+found`), custom owners,
parent ownership/modes and read-only data mounts are left untouched. Symlinks
at `/config`, `Documents` or `OSCAR20_Data` are rejected using no-follow
descriptor-relative traversal; unexpected ownership errors fail init.
One volume writer and no concurrent external path replacement are required.
Provision existing/nonempty volumes with the intended UID/GID yourself under
your storage policy; the image will not repair their permissions or use a
fallback data location. This hook does not make a read-only data mount writable.

## Browser access

Port3000 is internal HTTP. Native smoke tests publish only
`127.0.0.1:<ephemeral-port>:3000`. Production/public access requires HTTPS,
authentication at an existing proxy or supported secret-backed Selkies auth,
WebSocket upgrades and suitably long proxy timeouts. There is no embedded
password, identity provider, public listener or turnkey Internet exposure.

Default streaming is WebSocket/WebCodecs in a secure context (HTTPS or
localhost). Optional Selkies WebRTC is a different transport: no required UDP,
STUN/TURN setup is part of this packaging. No VNC service is supplied.
Software rendering/encoding must work without a GPU.

## Build interface

```sh
python3 -m ci.build_image --arch amd64 --out-dir artifacts/native/amd64
```

The host kernel, Docker daemon and image must all be native Linux of that
architecture; emulated builds cannot replace native acceptance. The CLI
refuses foreign hosts before Docker probes or output creation.
Privileged BuildKit bootstrap additionally requires GitHub's
`GITHUB_ACTIONS=true`, `RUNNER_ENVIRONMENT=github-hosted`; these are an
operational guard, **not** a security sandbox or authorization to forge them.

Install the exact Buildx/Skopeo versions in `ci/tools.lock.json`. Buildx uses
its own unique docker-container builder with the locked BuildKit image,
`--platform linux/<arch>`, `--provenance=false`, a gzip OCI exporter and no
registry push. Outputs:

- `image-<arch>.oci.tar`, exactly one platform image manifest;
- `build-<arch>.json`, schemaVersion1, source-state identity, archive hash,
  exact OCI manifest/config/compressed-layer digests and uncompressed DiffIDs;
- imported local `oscar-under-test:<arch>`.

Skopeo imports the same OCI archive. Docker's config digest and layer DiffIDs
must match the verified archive. Docker may change compressed representations
or manifest media types on import; config bytes and uncompressed layer bytes
are the identity boundary, not an invented equal registry manifest.
Source provenance JSON is **not a signed BuildKit attestation**.
No development HEAD or unverified OSCAR download is used.

The pinned Selkies base is Alpine 3.24 `alpine324`. A native compiler stage
verifies the locked OSCAR 2.1.1 source SHA256 before extraction, then uses
qmake6/make without source patches. Only the compiled binary, resources and
COPYING are copied to the runtime stage. The unchanged launcher resolves
`/usr/bin/OSCAR20`; translations/HTML are in `/usr/share/OSCAR20/`.
SQLite, Wayland, Qt translations and software Mesa are installed explicitly.
The three tested Python upgrades are hash-locked in `python-requirements.txt`
and installed only in the existing `/lsiopy` environment, followed by `pip check`.
Alpine dependencies come from distribution repositories; their exact installed
versions are retained in `/usr/share/oscar/runtime-packages.txt`, not claimed
as a reproducible package snapshot. A missing/incompatible package is a visible
build failure, never a silent OS fallback.

## Native runtime interface and receipts

The approved `container-functional-v1` scope extends the previous startup-only
check with synthetic upload, watchdog and retained-file checks. The normal runtime
needs Docker and Python, not a browser, OCR or GUI controller. Native bootstrap
builds checksum-locked Skopeo for image import/publication; it no longer acquires
Tesseract, traineddata or Chromium. Tool locks/dependencies retained for legacy
helpers do not make those helpers mandatory. No tool installation is implicit
in the runtime harness.

```sh
python3 -m ci.runtime --image oscar-under-test:amd64 --arch amd64 \
  --run-id image01-amd64 --artifacts artifacts/native/amd64
OSCAR_NATIVE_ARCH=amd64 python3 -m pytest tests/runtime -q
```

The explicit pytest suite executes its own run; use a fresh artifact directory
or remove only your own previous **completed test receipts** first. The CLI
refuses to overwrite a runtime receipt. Do not count a skipped or fake run.
`runtime-<arch>.json` must match the corresponding successful build receipt,
source state and archive hash. Failed runs have exitCode1 and explicit error,
never a manufactured PASS.
Owned loopback HTTP readiness polling tolerates a direct connection reset during
startup, still requires HTTP200, and keeps its 90s deadline/3s socket timeout.
It does not retry unrelated errors or any image/tool/infrastructure acquisition.

The harness uses one unique container and three fresh named volumes, PUID1234 /
PGID2345, loopback HTTP, 512MiB shm, no host mounts or socket, and software
encoding/rendering settings. It waits up to 90s for exactly one OSCAR20 process
with UID1234/GID2345, executable `/usr/bin/OSCAR20` and arguments
`OSCAR20 --legacy --datadir /config/Documents/OSCAR20_Data`.
An initially absent process may wait; invalid nonempty inventory fails.
Once observed, the same `(pid,start)` must survive at least 10 monotonic seconds,
polled every second. Replacement/exit/duplicates/wrong identity or a stopped
container fail, never reset the observation. Container state is also checked
during HTTP readiness. No profile is created and no database is inspected.

The receipt declares `testScope: "container-functional-v1"` and eight strict
checks: `containerRunning`, `httpReady`, `oscarStable`, `unprivileged`,
`uploadRoundTrip`, `watchdogRestart`, `dataRetained`, `sdcardReadOnly`.
After the initial process observation it verifies actual mount flags and
unprivileged writes, round-trips a uniquely owned nested synthetic upload,
terminates only its owned OSCAR process and verifies watchdog replacement.
One container restart must retain both synthetic files, checked before any
overwrite. Same-filesystem bind mounts are checked through Linux mountinfo,
not the unreliable `os.path.ismount` predicate.
This proves neither a usable/decoded GUI nor CPAP import, real profile/database
migration, restoration or actual Kubernetes routing. See [acceptance](acceptance.md).

Each release architecture also produces one full image-bound Trivy report.
Any critical or unaccepted high advisory blocks publication. The five accepted
inherited high IDs remain visible; updates in the active Python environment do
not prove older scanned copies have disappeared. The original experiment still
reported five high, two medium and one low finding after those upgrades.

Failures retain JSON and owned container logs with synthetic startup content
only. Cleanup removes only exact names with matching ownership labels; no prune
or broad host cleanup. Cleanup failure sets exitCode1 and `cleanupError` even
after successful smoke. Legacy GUI/negative/Kubernetes helpers may remain but
are neither normal CI/release gates nor verified by this receipt.

## Shared state identity

`ci.state_identity(project)` returns `gitCommit` (null for unborn) and
`dirtyDiffSha256`. Its canonical UTF-8 JSON hashes a sorted list of changed
paths, staged index records, working file modes/content hashes, symlink target
strings or deletions. It includes **nonignored untracked** files; never follows
symlinks into private host data. A clean tree hashes `[]` (`CLEAN_DIFF_SHA256`).
Receipts also include command, cwd, exitCode, platform and explicit checks.
Release must require a clean exact commit and matching archive digests.

## Sources, licensing and backup

```sh
python3 -m ci.source_bundle --out-dir artifacts/sources
```

An optional `--source-archive PATH` uses an offline cache but never bypasses
the source checksum. Use an empty output directory. Bundle includes the exact
OSCAR archive and COPYING, explicit applied-patch list (empty here), our
packaging/build/launcher/harness/tests/licences and per-file checksum manifest.
It includes source-build provenance, the exact Python requirements and actual
packaging-input hashes. Historical Debian receipts remain readable, but the
new build makes no Debian binary correspondence claim (see NOTICE).
Upstream notices remain unmodified. See [NOTICE](../NOTICE.md) for base,
Qt, package source and licensing obligations; our Apache-2.0 does not relicense
dependencies.

For backups: stop application writes, back up **all three volumes** and their
ownership/Qt configuration, retain the exact image/source identity, and test
restoration to isolated new volumes. Copying a live SQLite main file without
its WAL is not a consistent backup. Never restore over originals during an
unproven upgrade; follow the separate [migration checklist](migration.md).
