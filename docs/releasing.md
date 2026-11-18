# Releasing OSCAR

Project: **frisbeecz/docker-oscar**. Current versions: chart/project **1.1.1**,
OSCAR **2.1.1**, image **2.1.1-r9**. Existing tags, releases and published
artifacts must not be overwritten as a recovery mechanism.

## Flow

1. Push a fresh stable `v<chart-version>` tag.
2. GitHub runs the normal CI: static checks, both Helm versions, and native
   AMD64/ARM64 source build, one candidate scan and one functional pass. `publish` has `needs: [tests]`; failed or
   skipped CI blocks publication without a separate job-result API audit.
3. The publish job downloads this run's immutable artifacts. It validates the
   tested files once, before logging in or making external writes.
4. Create a prerelease containing the corresponding-source/license files.
   Verify their public availability/checksums before distributing binaries.
5. Copy both tested OCI archives with Skopeo `--preserve-digests`, create the
   GHCR image index with Buildx, mirror that exact index and both platforms to
   Docker Hub using Skopeo `--all --preserve-digests`, and upload the already
   tested chart package to GHCR.
   Nothing is rebuilt or repackaged during publication.
6. Save/upload `release-manifest.json`, then perform one final distribution
   check using Skopeo and `helm pull`. Only success makes the prerelease final.

Main/PR CI does not publish. Only the trusted tag publish job has
`contents: write` and `packages: write`. Tokens are passed through environment
or stdin, never command-line arguments. Temporary registry credentials are
isolated and cleaned up.

Main pushes run static and Helm checks only, avoiding duplicate image builds.
PRs and the reusable CI called by a release tag retain both native jobs. The
release builds each architecture once and publishes those exact tested archives.

The publish step also requires repository secret `DOCKERHUB_TOKEN`, with push
access as `frisbeecz24` to `frisbeecz24/docker-oscar` and permission to manage
that repository's information. It is not exposed to CI,
checkout or dependency installation. See [distribution setup](distribution.md)
for Docker Hub prerequisites and one-time Artifact Hub registration.

## What is checked

The single local publication gate checks the clean tag commit, canonical
source bundle, native image/runtime/security receipts and archives, and both tested
Helm packages. Native receipts must identify the tested bytes, successful
cleanup and the current `container-functional-v1` scope. A full Trivy report
must match the same image configuration, architecture and archive; any critical
or high advisory blocks publication. `ci.security.ACCEPTED_HIGH` is empty for
new images; no entries are hidden. Python remains available but pip is removed
after dependency installation/checks, and native runtime checks enforce that
separation. Downloaded artifact digests are also checked by GitHub's artifact
action.

CI success is enforced by GitHub's dependency graph, not collected and
revalidated via the Actions API. There is no separate evidence job or
`evidence` CLI command. The release manifest retains the run URL, ID and attempt
from the trusted job environment, plus artifact/source/platform digests.
`jobUrls` remains an empty object for format compatibility; individual job
results are available through the linked GitHub run.

The final check reads the GHCR image index/platform manifests with Skopeo and
checks them against the tested identities. It also anonymously reads the
Docker Hub version tag: its raw index digest must be identical to GHCR,
including both platform descriptors. Helm downloads the chart, handles registry
CDN redirects itself, and the package checksum must match the tested archive.
Skopeo checks the tagged chart manifest digest. Source downloads are checked
once, before the binary uploads, rather than downloaded again at the end.
New manifests record `dockerHubRepository`; the same `imageIndexDigest` applies
to both registries. Saved older manifests without this optional field still
verify GHCR only. Artifact Hub indexing is asynchronous and is not a release
publication gate.

The small `ci.chart_registry` uploader remains because the original Helm push
failed while reading an untagged manifest. It uploads the Helm config/chart
blobs and PUTs the local manifest directly under the version tag. It refuses
an existing chart tag and only sends credentials to the approved HTTPS GHCR
repository. Upload session suffixes are opaque. **It does not download blobs,
implement CDN redirects or duplicate the final Helm verification.**

## Commands

Use Python 3.14 and a project-local venv with `requirements-ci.lock`.
Project-local tool versions/checksums are in `ci/tools.lock.json`.

```sh
# Local checks; no publication:
python3 -m ci.check
python3 -m ci.release verify --artifacts artifacts --commit "$(git rev-parse HEAD)"

# Only inside the trusted tag job, after successful CI:
python3 -m ci.release publish --artifacts artifacts \
  --commit "$GITHUB_SHA" --registry ghcr.io/frisbeecz

# Explicit read-back verification of a saved release manifest:
python3 -m ci.release verify-published \
  --release-manifest artifacts/release-manifest.json
```

## Limits and failure handling

The functional scope covers startup/HTTP, the same unprivileged OSCAR process
for ten seconds, synthetic nested upload/download, watchdog replacement and
synthetic files retained after one container restart. It does **not** prove
GUI/media usability, real CPAP imports, profile migration/restore or a working
Kubernetes deployment.

OSCAR is built from the checksum-locked, unpatched source archive on pinned
Alpine/Selkies, not installed from Debian binaries. Preserve corresponding-source
and license material and resolve remaining obligations in `NOTICE.md`.
OS/base packages are not claimed to be bit-reproducible. Existing Hadolint
warnings remain visible.

Publication is not atomic. A failure may leave images, a chart tag or a
prerelease already uploaded. Stop and report the partial state; do not
automatically retry, overwrite, delete or change package visibility/auth.
Local tests are not proof of a successful live release.

After a verified release, pin deployments to the recorded image/chart digests.
