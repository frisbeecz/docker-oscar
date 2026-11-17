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
