# Release procedure and trust boundary

The approved public project is **frisbeecz/docker-oscar**, not a fork.
The first intended release is `v0.1.0`: OSCAR **2.1.1**, image **2.1.1-r1**,
chart **0.1.0**. No release/tag is created merely by merging or running main CI.
Create the first tag only after the joint acceptance review.

## Checks and artifacts

Use a project-local venv, Python 3.14 and the hashed `requirements-ci.lock`.
This is the current interpreter requirement, superseding the historical plan's
Python 3.13 selection.
`python3 -m ci.check --install-tools` downloads checksum-verified tools into
`.venv/`, using `ci/tools.lock.json`; it never configures an account.
Existing download caches are rehashed; corrupt caches fail instead of refreshing.
Action commit pins were verified against upstream tag and commit objects.
Tool hashes come from upstream release asset metadata, Helm/Kubernetes checksum
files and PyPI distribution metadata.

```sh
python3 -m ci.check
python3 -m ci.release verify --artifacts artifacts --commit "$(git rev-parse HEAD)"
```

The common check runs actionlint (including workflow ShellCheck), yamllint,
hadolint, ShellCheck, Ruff's fatal Python checks, bare pytest and both actual
Helm 3.19.0 / 4.3.2 strict-schema matrices. Every lint input class must be nonempty;
missing tools fail. Go-template files are linted/rendered by Helm, not treated
as plain YAML. The two current shell entrypoints use POSIX sh, including the
sourced Wayland autostart file without a shebang.
Hadolint errors block; warnings remain visible in its log. In particular,
unversioned Debian dependencies and the Dockerfile pipefail recommendation remain
warnings: the base/OS packages are not claimed to be bit-reproducible.
The application image uses pinned Selkies Debian13 and hash-checked official
OSCAR2.1.1 Debian13 packages, not a local OSCAR compilation. The source manifest
records binary URLs/hashes and package version/architecture alongside the
unchanged exact source archive, COPYING and empty patch list. Matching version
and embedded short commit are evidence of alignment, not proof of reproducible
upstream binaries or complete corresponding source. Resolve remaining upstream
source/build-input obligations before redistribution; see NOTICE. Native
startup-only verification of this Debian image is still pending.
The explicitly user-approved 2026-11-15 `startup-smoke-v1` scope supersedes
historical mandatory GUI/OCR/profile/persistence/Kubernetes acceptance.

The second command is read-only. Incomplete local receipts, dirty state,
different commits, missing architectures, skipped/failed jobs and changed bytes
are errors, **not a successful partial verification**.

`ci.yaml` is also the reusable exact-tag test workflow. The jobs produce:

* `static-sources`: `static/check.json`, logs, `sources/origin.json`,
  checksum-verified upstream sources, packaging/license material, plus an exact
  `git archive` containing the entire public project (including chart/workflows);
* `helm-3.19.0`, `helm-4.3.2`: real chart matrix receipts and separately tested,
  immutable `oscar-0.1.0.tgz` packages;
* `native-amd64`, `native-arm64`: single-platform OCI archive, exact build/import
  and `startup-smoke-v1` runtime receipts plus corresponding source provenance;
* `evidence`: GitHub's run, exact attempt and successful required job URLs.

The same-run artifact download uses immutable artifacts with digest mismatch
errors; receipt, source, OCI and package digests are checked independently.
No prior workflow run is used as a substitute. Main/PR CI never logs in or pushes.
Native acceptance uses only GitHub-owned disposable Ubuntu 24.04 AMD64/ARM64
runners. BuildKit needs privileged **infrastructure** containers there;
this does not authorize a privileged OSCAR workload or local bootstrap.
Skopeo 1.25.1 is built from checksum-locked source on those runners. Host build
prerequisites come from the runner's Ubuntu repositories, not the app image.
Bootstrap no longer acquires/builds Tesseract, traineddata, Chromium, kind or
kubectl. Existing lock entries and historical helper unit tests may remain.

Normal runtime starts one owned container and fresh synthetic volumes, requires
loopback HTTP200 and at least 10 seconds of the same UID1234/GID2345 OSCAR20
process with exact executable/arguments. See [container](container.md) for
deadlines and receipt fields. No browser, profile creation, restart, database
audit or kind deployment is invoked. Success artifacts upload only after smoke
and owner-checked cleanup; failures retain JSON/container logs without credentials.
Release rejects legacy/missing/mistyped/short/dirty/mismatched/cleanup-error
runtime receipts. Negative GUI and Kubernetes receipts are no longer required.
All other source/static/Helm/OCI/same-run job gates stay mandatory.

Remote GUI usability/media, import, profile/data persistence, watchdog and actual
Kubernetes installation/routing remain **unverified**, not silently passed.
Backup/migration and official-binary corresponding-source obligations remain;
source evidence does not establish redistribution compliance.

## Publication

`release.yaml` handles `v*` tag pushes, but the publication gate accepts only
stable project SemVer matching the chart version. Every required gate runs anew
at the tag commit. A successful reusable workflow is a mandatory dependency.
There is no `always()` or `continue-on-error` escape into publication.

The publish job alone receives job-scoped `packages: write` and `contents: write`
(plus read access to Actions evidence). **Those permissions exist from job start,
not after validation.** It checks out only the trusted tag state, never PR code.
All receipt verification occurs before the first publication/login mutation;
the publisher repeats verification and re-reads live GitHub job results.
Secrets are provided through stdin/environment, never shell source or argv.

```sh
# Invoked only by the trusted exact-tag GitHub job:
python3 -m ci.release publish --artifacts artifacts \
  --commit "$GITHUB_SHA" --registry ghcr.io/frisbeecz
python3 -m ci.release verify-published \
  --release-manifest artifacts/release-manifest.json
```

Order:

1. Create a public **prerelease with corresponding source assets first**.
   Anonymous HTTPS downloads must match their checksums before any binary upload.
2. Copy both tested OCI archives with Skopeo `--preserve-digests`.
   Digest-preservation failure blocks; no layer conversion or rebuild fallback.
3. Create the image index from those exact platform manifest digests.
4. Publish the already packaged/tested chart through `ci.chart_registry`, without
   editing defaults or repacking. Upload its Helm config/chart blobs, then PUT the
   locally held OCI manifest **directly under the version tag**. Do not use Helm
   ExtendedCopy/Tag's untagged-manifest read-back, which failed during the initial
   release. Refuse an existing chart tag. Read back the tagged manifest, config
   and exact chart bytes and check their digests before recording publication.
5. Upload `release-manifest.json`: `testScope: "startup-smoke-v1"`, source checksums, platform config/manifest/layer
   digests, index digest, chart digest/version and exact run/job URLs.
6. Verify anonymously retrievable image/platform bytes and chart tarball, as well
   as source assets. Only then mark the prerelease final.

GitHub and GHCR are not an atomic transaction. A network/permission/quota failure
after the first write may leave a prerelease or partial registry content.
**Stop and report that state; do not rerun, overwrite, delete or change account
settings as an automatic recovery.** Public pull denial is a blocker, not
permission to change package visibility, tokens, runner billing or auth scopes.

The chart publisher uses the same job-scoped token in memory, with only the
approved `frisbeecz/charts/oscar` GHCR scope. It does not save another registry
credential file, follow authenticated redirects or retry failures. GHCR blob
downloads may follow one HTTPS redirect to its approved
`pkg-containers.githubusercontent.com/ghcr1/blobs/` CDN, **without Authorization**;
the downloaded content must still match its expected size and SHA256. Other
redirects fail closed. Protocol regression tests cover a registry where
untagged manifests cannot be read, and a real local Helm pull checks package
compatibility. These local checks do not establish that a subsequent live GHCR
publication has succeeded.

After a successful release, pin installations using the manifest's
`imageRepository@imageIndexDigest` and chart OCI digest. Do not guess digests from
documentation examples or use mutable tags as the sole provenance.
