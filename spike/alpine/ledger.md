# OSCAR-ALPINE-SPIKE

Experimental feasibility probe only. Not a production migration or release.

- Owner: high primary; baseline `d6ce76a151439c5209b865aeb4c301a65875c0b0`.
- Location: `/Users/ondrejvala/.local/share/opencode/worktree/b0fea1/oscar-alpine-spike`.
- Branch: `spike/oscar-alpine`; original checkout and its six dirty documents untouched.
- Approval: user approved an Alpine source-build spike, then explicitly approved an isolated
  worktree, GitHub branch, native AMD64/ARM64 CI builds and security scans without publication.
- Write scope: `spike/alpine/**`, `.github/workflows/alpine-spike.yaml`, ignored `artifacts/`
  and generated graph outputs. No changes to production Dockerfile, chart, versions, workflows,
  releases, registry tags, credentials, or K3s.
- Attempts: implementation 2/2 in progress; source research delegated read-only to
  `ses_e1447af47ffepnjIBgLbMDzNHt`, not another implementer.

## Acceptance

1. Exact existing OSCAR 2.1.1 source SHA verified; native source build on musl/Qt6 for both CPUs.
2. Digest-pinned LinuxServer Alpine 3.24 base, separate builder/runtime stages.
3. Disposable, unprivileged desktop application with loopback-only port, no host socket/devices,
   test-only volumes; native checks for startup, nested web upload, watchdog and retained data.
4. Trivy reports for released Debian image, Alpine base and experimental final image using the
   same scanner/database per runner. Report findings honestly; do not require or promise zero.
5. Secret-free CI with contents-read permissions, pinned actions, artifacts only, no image push.

## Stop conditions

Stop on permission/account/quota/infra failure, unexpected external effects or need for
production changes. No automatic retry, model fallback, source patches, release or migration.
At most two implementation attempts; feasibility failure is a useful result, not permission
to silently change the architecture.

## Baseline / references

- Native worktree created and session moved with harness tools; initially detached and clean,
  then branch created explicitly.
- First baseline invocation had test-harness setup errors: missing `artifacts/` parent and
  absent pinned Helm binaries from PATH. No production defect or product edits.
- After creating ignored artifacts directory and exposing existing project-local tools:
  `PATH="/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH"
  /Users/ondrejvala/projects/oscar/.venv/bin/python -m pytest -q
  --basetemp=artifacts/pytest-alpine-baseline-ready`: exit 0, **387 passed**, 30.40s,
  `artifacts/baseline.log`.
- Public base index read successfully: `ghcr.io/linuxserver/baseimage-selkies:alpine324`
  digest `sha256:f2820b8df78eb020785850492c2b6547de2c762fcfcd644b11d4f7e211f5a987`;
  AMD64 `sha256:42c1a97cc56d2481c0d99bccebf99b4c0bb708ebffa60a2c188f69473bcd33f2`,
  ARM64 `sha256:3b11b11c53f206ab53c86846bb8f993ea07b9fb76a56306c4b4a2a3bb57d0191`.
  Receipt: `artifacts/alpine-base.json`.
- Upstream Alpine branch source reference: `4acbc9ebc23dfdc0ed6f815223f13412bd3735f5`.
  Its base still includes Docker/OpenSSH and many desktop components; an Alpine switch alone
  does not prove a minimal or vulnerability-free runtime.
- Trivy 0.76.2 official release checksums read: Linux-64bit
  `bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf`;
  Linux-ARM64 `ab9d51f86e6a5fb936f605faff6b593ac51bc378fff4d3e8b9d58358b9c367c3`.
- Local Docker daemon known unavailable; not retried. Context7 quota not retried; official
  public upstream docs/source and registry used instead. No secrets read.

## Source research and local verification

- Read-only expert completed SHA-verified inspection of the 14,428,909-byte archive:
  qmake/`OSCAR_QT.pro`, Qt6, C++17, mandatory lrelease, X11/zlib/GLU, output
  `/build/oscar/OSCAR20`; no supported `make install`. Resources must retain
  `/usr/share/OSCAR20/{Html,Translations}`. No demonstrated glibc-only blocker, but no
  musl build success inferred. Keep upstream graphics and warning policy unchanged.
- Parent independently checked Alpine **3.24** community APKINDEX for **both** CPU
  architectures: Qt6 base/dev/serialport/tools/SQLite/Wayland packages are present,
  currently Qt 6.11.1. The expert's 3.23 package findings are not substituted as
  evidence for this selected 3.24 base.
- TDD: `python -m pytest -q spike/alpine/test_probe.py` initially failed three missing
  experiment-file contracts (`artifacts/probe-red.log`); final exit 0, **3 passed**
  (`artifacts/probe-green.log`).
- Full native local verification:
  `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH
  /Users/ondrejvala/projects/oscar/.venv/bin/python -m ci.check --static-only
  --out-dir artifacts/alpine-static-a1`: exit 0; all six groups including actual
  actionlint/hadolint and full project pytest passed: **387 passed**, 31.71s.
  Receipt: `artifacts/alpine-static-a1/check.json`, baseline d6ce76a,
  dirty diff SHA256 `9a9a7b6667a139ccb39a8db467d872de9539848de00689c04856fec2fd972659`.
- No runtime/container/image build or scan has yet been executed; those require
  the explicitly approved experimental branch push and GitHub runners.
- Local implementation ready for independent pre-push review. No production files
  changed; no experimental image publication or release is authorized.

## Independent review correction — attempt 2/2

- Review `ses_e1439a23dffez9hB5SN6xOimQl` found one substantive P2: candidate scanning
  followed runtime testing, so a compatibility failure would lose the third scan.
- Regression test observed RED (`artifacts/scan-order-red.log`, exit 1, `6 < 5`).
  Corrected only step order: scan immediately after a successful build, before runtime.
  No failure masking, retry, privilege, source, package or runtime behavior changes.
- Sequential cleanup remains a disclosed runner-local limitation: an inspection/logging
  failure can prevent later cleanup; the disposable hosted runner is then discarded.
- Reviewer also requested read access to unchanged CI/release triggers before certifying
  whole-branch-push safety. Supply those unchanged workflows with scoped re-review.
- Correction verification: explicit spike contracts **4 passed**, exit 0,
  `artifacts/probe-green-a2.log`; full `ci.check --static-only --out-dir
  artifacts/alpine-static-a2` with the same interpreter/PATH/cwd above, exit 0,
  all six groups and **387 project tests passed**, 34.45s. Current receipt diff SHA256
  `31a483247d71ec3355ed004595806113fc83754f577d566910a0ba2e7a1fb62f`.
  `graphify update .` and `git diff --check` exit 0.
- Scoped correction diff `artifacts/alpine-review/correction.diff` SHA256
  `a64be43be9c6fc79da7240024ae91e0ec334c9be0412375ee16f6e026e243104`;
  frozen executable/doc identities `artifacts/alpine-review/state-a2.json`.
- Scoped re-review `ses_e1439a23dffez9hB5SN6xOimQl`: **DONE/PASS**; P2 and
  trigger-context gap closed. Safe to push only this experimental branch; no live
  success or production migration inferred. No further source corrections permitted
  within the two-attempt budget.
- Pre-push check: remote main remains d6ce76a, experimental branch absent, original
  checkout retains exactly its six pre-existing dirty documents. Snapshot:
  `artifacts/original-checkout-state.json`. Frozen seven reviewed files unchanged.
- Proceeding with the user-approved commit and push **only**
  `refs/heads/spike/oscar-alpine`; no PR, tag, merge or publication.

## Experimental integration

- Commit `ba47b163a3a04bd0731e59742ff4f1bae803e2a3` contains exactly the eight
  approved experiment files. `git push origin HEAD:refs/heads/spike/oscar-alpine`
  exited 0; remote read-back matched. Main remains d6ce76a.
- First filtered run discovery returned an empty list (event registration pending);
  no workflow dispatch, retry or extra push was issued.
- Native build/runtime/scan outcome is still pending. This local ledger append is
  intentionally not another CI-triggering commit.
- GitHub registered run **44197765386**, `Alpine feasibility spike`, correct commit
  ba47b163 and branch, status in progress:
  https://github.com/frisbeecz/docker-oscar/actions/runs/44197765386 .
  Owned `gh run watch ... --exit-status --interval 30` is running in the background;
  await completion notification, do not poll or submit another run.

## Remote outcome: build and scans complete, runtime blocked

- Run 44197765386 completed with failure on both architectures; the owned watcher
  exited 1 and is no longer running. Both native source builds and all three
  scanner steps succeeded. No image was published.
- Read-only diagnosis: `gh run view 44197765386 --repo frisbeecz/docker-oscar
  --log-failed` and `gh run download 44197765386 --repo frisbeecz/docker-oscar
  --dir artifacts/alpine-remote-44197765386` completed successfully, cwd this
  worktree. Downloaded evidence is under `alpine-failure-{amd64,arm64}/<arch>/`.
- Both probes stopped at embedded Python line 13:
  `assert os.path.ismount(data) and os.access(data, os.W_OK)`.
  The log does not distinguish the two operands. Application stability, uploads,
  watchdog and retained-data checks were not reached and remain unverified.
- The probe has a demonstrated portability weakness: Python's documented
  `os.path.ismount` cannot reliably identify bind mounts on the same filesystem.
  Docker named volumes can have that topology. This is a plausible explanation,
  not proof that writability or the application itself is correct. A subsequent
  authorized correction should inspect mount information and write access
  separately rather than weaken or skip the storage check.
  Reference: https://docs.python.org/3/library/os.path.html#os.path.ismount .
- Trivy 0.76.2 used the same database UpdatedAt
  `2026-11-17T19:04:24.303581049Z` for the comparisons on both runners:
  candidate and Alpine base each have 0 critical, 5 high, 2 medium, 1 low
  findings (8 distinct advisory identifiers, all with FixedVersion).
  Released Debian has 4 critical and 400 high findings on each architecture;
  other severities differ between architectures. Findings are scanner results,
  not proof of equivalent cross-distribution coverage or absence of risk.
- All eight candidate findings are inherited from the Alpine base's Python
  packages: msgpack 1.1.2, setuptools 70.3.0 and urllib3 2.7.0. No dependency
  update, exception or suppression was made.
- Status: **BLOCKED for runtime acceptance**, two implementation attempts exhausted.
  No further implementation or CI run without explicit additional user approval.
  Production main, releases, registries and K3s remain untouched.

## Explicitly authorized additional attempt (3 total)

- User: “podivej se proc to failnulo a taky pouzi nejnovejsi pyrhon balicky
  aby jsme odstranili co nejvice zranitelnosti”. This authorizes one additional
  correction and dependency-refresh attempt in this same isolated experiment,
  including another experimental branch push/native run, not a production release.
- Scope remains `spike/alpine/**`, experimental workflow if necessary, ignored
  artifacts and graph updates. Existing production files and the original dirty
  checkout remain untouched; primary retains the only writer slot.
- Correct bind-mount detection using Linux mount information, keep separate
  read/write checks and log UID/GID, ownership, mount flags and writable status.
  Do not silently skip a failing storage acceptance check or chown data.
- Refresh all three Python packages implicated by the candidate scan to the
  newest stable PyPI versions observed 2026-11-18: msgpack 1.2.4, setuptools
  84.2.1, urllib3 2.8.0. Use exact versions and SHA256-verified wheels for both
  musl architectures in the existing `/lsiopy` environment; require `pip check`.
  Selkies 2.2.1 wheel metadata imposes no conflicting msgpack version constraint.
- Acceptance: local regression tests/full native project checks, wheel hash
  validation, scoped independent review, then one native AMD64/ARM64 build/scan/
  runtime run. No assertion of zero vulnerabilities before scanning. A further
  substantive defect or failed final verification is BLOCKED, not another repair.

### Attempt 3 local verification and scope blocker

- Implemented mountinfo parsing with separate diagnostics/flags/write checks and
  preserved failure stdout in `runtime-<phase>.log`. The original remote failure
  does not yet prove which operand failed; only another authorized native run can
  close that ambiguity. No ownership or application changes were made.
- Added SHA256-locked latest-stable wheels for the three affected packages into
  `/lsiopy`, `pip check`, installed-version runtime assertions and a narrowly
  allowlisted experimental `Dockerfile.dockerignore` to include those requirements
  without changing the production build context.
- Local RED: explicit spike tests, exit 1, six expected missing-feature failures,
  `artifacts/alpine-a3-red.log`. GREEN: same ten tests, exit 0,
  `artifacts/alpine-a3-green.log`. Embedded runtime code compilation passed.
- Native `pip download --only-binary=:all: --no-deps --require-hashes` for CPython
  3.14 musllinux x86_64 and aarch64 both exited 0; artifacts and logs are under
  `artifacts/alpine-a3-wheels*`. This downloads/verifies wheels, does not install
  them into the workstation.
- Full `ci.check --static-only --out-dir artifacts/alpine-static-a3` exited 1:
  existing `ci/check.py:42` classifies *every* `Dockerfile.*` as a Dockerfile,
  incorrectly passing the standard Dockerfile-specific ignore file to hadolint.
  `hadolint.log:5` reports its first `**` as invalid Dockerfile syntax.
  This is not a failed native build or evidence against the dependency versions.
- Independent verification without altering the classifier: full project
  `python -m pytest -q --basetemp=artifacts/pytest-alpine-a3-project` exited 0,
  **387 passed**, 31.69s (`artifacts/alpine-a3-project-tests.log`); native hadolint
  on both actual Dockerfiles exited 0 (`artifacts/alpine-a3-dockerfiles.log`).
  All commands use the existing original checkout's interpreter/tools and this
  worktree cwd. `git diff --check` exited 0.
- **BLOCKED**: changing `ci/check.py` and its regression test is outside the
  approved experimental-only scope and follows a failed final validator.
  No hidden repair, independent review, commit, push or new remote run performed.
  Request explicit permission for the small classifier correction and completion
  of verification before any further implementation.

## Authorized classifier correction and completion (attempt 4 total)

- User explicitly answered “ano” to correcting Dockerfile classification and
  running the new CI. Scope extended only to `ci/check.py` and
  `tests/ci/test_check.py`, in addition to the existing experiment changes.
- One additional correction/verification attempt, no reset of prior attempts.
  Primary owns the writer slot. Real Git fixture test must retain ordinary and
  variant Dockerfiles while excluding Dockerfile-specific ignore files.
  After local checks and scoped review, push only the existing experiment branch
  for one more native run. No main, release, registry, auth or K3s mutation.

- Regression RED: real temporary Git fixture exercises ordinary/variant/nested
  Dockerfiles and their standard ignore files. Expected failure before the
  classifier change, exit 1, `artifacts/alpine-classifier-red.log`.
- Fix excludes only names ending `.dockerignore`; real Dockerfile variants remain
  lint inputs. Targeted classifier and experiment tests: **19 passed**, exit 0,
  `artifacts/alpine-a4-green.log`.
- Final combined verification, cwd this worktree, existing interpreter and tools:
  `python -m ci.check --static-only --out-dir artifacts/alpine-static-a4`,
  exit 0, all six groups including hadolint and **388 project tests passed**,
  31.18s. `git diff --check` and `graphify update .` also exited 0.
- Independent review is limited to the newly authorized follow-up diff since
  ba47b163: dependency refresh, corrected runtime storage diagnostics and the
  classifier integration. Earlier experiment design/scan-order review is not
  repeated; implementation budget remains four total, not reset.

### Review outcome: BLOCKED, no new remote execution

- Reviewer `ses_e123b654dffeNwqeT6oVzvFfP8` identified one substantive P2:
  `data.stat()` at check-runtime.py:53 may raise before emitting UID/mount
  diagnostics if the data directory is missing or inaccessible.
- Primary reproduced this read-only by executing those actual embedded CHECK
  statements against an absent path: FileNotFoundError, empty diagnostic stdout.
  Finding accepted; 388 passing tests do not cover this failure mode.
- No source correction, commit, push, new CI or production mutation performed.
  Attempt 4 is blocked after review; request explicit authorization for one
  narrowly scoped diagnostics correction and regression test before continuing.

## Authorized single diagnostics correction (attempt 5 total)

- User explicitly answered “ano” to correcting only the accepted diagnostic
  finding, adding regression coverage, then pushing the experiment branch and
  starting CI. Prior budgets are not reset.
- Scope: diagnostics statements in `spike/alpine/check-runtime.py`, regression
  tests in `spike/alpine/test_probe.py`, this ledger and ignored evidence.
  Preserve all acceptance assertions, dependencies and prior verified changes.

- RED: tests execute actual embedded diagnostic statements. Present-path case
  passed; missing real path and deterministic stat permission denial failed
  before correction (2 expected failures, exit 1,
  `artifacts/alpine-diagnostics-red.log`).
- Diagnostic metadata now survives OSError from stat, including error type and
  errno, and is flushed before the unchanged storage acceptance assertions.
- GREEN: classifier plus experiment tests **22 passed**, exit 0,
  `artifacts/alpine-a5-green.log`.
- Final full command uses existing project interpreter/tools, cwd this worktree:
  `python -m ci.check --static-only --out-dir artifacts/alpine-static-a5`,
  exit 0, all six groups and **388 project tests passed**, 32.36s.
  Embedded CHECK compiled; graphify update and diff check exited 0.
- Correction diff `artifacts/alpine-followup-review/correction-a5.diff` and
  `state-a5.json` identify the verified state. Prior reviewed source identities
  matched after reconstructing the two changed files before this correction.
- Scoped re-review session `ses_e123b654dffeNwqeT6oVzvFfP8` returned DONE/PASS:
  accepted P2 closed, assertions retained, no blocker to the already-authorized
  experimental push/native rerun. This does not establish native runtime or
  updated vulnerability results.
- Proceeding with the user's explicit experimental-branch push/CI authorization;
  main, releases, registries and K3s remain outside the execution scope.
