# Acceptance evidence

## Current approved scope: `startup-smoke-v1`

On 2026-11-15 the user explicitly approved startup-only native smoke, replacing
the historical design/plan's mandatory GUI/OCR, wizard/profile, import,
persistence and Kubernetes functional acceptance. Those earlier documents are
historical; removed coverage is **not** a PASS. No native run of this new scope
is established by local static tests. The first release still needs joint
independent review before tagging.

Each native job must start the exact imported image, require a running container
and loopback HTTP200 within 90 seconds (startup connection resets may be polled),
then wait up to 90 seconds for exactly one OSCAR20 process. A nonempty invalid
inventory fails immediately. The process must have UID1234/GID2345, executable
`/usr/bin/OSCAR20`, and launcher arguments
`OSCAR20 --legacy --datadir /config/Documents/OSCAR20_Data`.
The same `(pid,start)` must survive at least 10 monotonic seconds, polled every
second with container-running checks. Exit, replacement, duplicates or wrong
identity fail; the observation never restarts its countdown.

The runtime receipt records `testScope: "startup-smoke-v1"`, exactly three
strict boolean checks (`containerRunning`, `httpReady`, `oscarStable`),
`process`, and numeric `durationSeconds >= 10`. Source/platform/image/archive/
config/layer identities must match the build. Cleanup is owner-checked and
mandatory; its failure invalidates even an otherwise successful smoke.
Receipts are not overwritten. There is no browser, OCR, GUI interaction,
database audit, restart/recreation or import/profile scenario on the normal path.

| Gate | Required evidence |
| --- | --- |
| Local policy | Bare pytest includes image, chart and CI regression tests; explicit native runtime tests are not selected locally |
| Workflow/tool checks | `ci.check` receipt and real actionlint/yamllint/hadolint/ShellCheck/Python lint logs; missing tools fail |
| Chart | Helm 3.19.0 and 4.3.2, eight strict-schema variants, negative schema/capability cases; exact packaged tarballs retested |
| Native AMD64 | GitHub-owned `ubuntu-24.04`; exact source/build/import and current startup-smoke receipt |
| Native ARM64 | GitHub-owned `ubuntu-24.04-arm`; identical gates, never QEMU |
| Sources | Checksum-locked OSCAR sources/license, official binary provenance, packaging inputs and exact public-project git archive at the tested clean commit |
| GitHub run | Exact repository, head SHA, attempt, completed/success required jobs and URLs; missing/failed/skipped jobs reject release |
| Distribution | Public source assets first, platform digests preserved, correct image index and unmodified OCI chart; public retrieval verified |

Release accepts only the explicit current scope, not legacy GUI receipts or
missing/mistyped/short/dirty/failed/mismatched/cleanup-error evidence. It no
longer requires negative-base GUI or Kubernetes receipts. The verified manifest
and `release-manifest.json` record `testScope` without claiming removed coverage.
`ci.gui`/`ci.kubernetes` and legacy negative helpers remain non-gating historical
utilities, not evidence that their scenarios pass or instructions to run them.

## Unverified coverage

Remote GUI usability and decoded media, import, profile/data persistence,
watchdog recovery, actual Kubernetes installation/storage retention/routing,
proxy TLS/authentication and medical functionality are **unverified** by this
scope. Helm rendering/schema success is not deployment success. No production,
private-infrastructure, real-medical-data or migration test is authorized here.
Keep the separate [backup/migration cautions](migration.md). Official-binary
corresponding-source obligations remain unresolved; source provenance is not
proof of complete binary-to-source correspondence or redistribution compliance
(see [NOTICE](../NOTICE.md)).

## Inspect evidence

See [releasing](releasing.md) for tooling. After a separately approved push:

```sh
gh run list --repo frisbeecz/docker-oscar --workflow ci.yaml --branch main
gh run watch RUN_ID --repo frisbeecz/docker-oscar --exit-status
gh run view RUN_ID --repo frisbeecz/docker-oscar --json url,headSha,status,conclusion,jobs
gh api repos/frisbeecz/docker-oscar/actions/runs/RUN_ID/artifacts
gh run download RUN_ID --repo frisbeecz/docker-oscar --dir artifacts/downloaded
```

Record command/cwd/exit, exact commit/tree, run/attempt, platform jobs and artifact
SHA256 digests. GitHub ZIP digests do not replace receipt/OCI/archive validation.
Release assembles `artifacts/{static,sources,chart,native,evidence}` from the
same run; unrelated historical/local evidence is not a substitute.

A missing runner, unsupported tool, permission denial or infrastructure failure
means **BLOCKED / NOTRUN**, never substitution, silent skip or PASS.
