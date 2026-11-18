# OSCAR Alpine production execution ledger

Plan: `docs/superpowers/plans/2026-11-18-oscar-alpine-production.md`
Spec: `docs/superpowers/specs/2026-11-18-oscar-alpine-production-design.md`

## Approval and scope

- User requested main Alpine migration, successful release, then K3s deployment.
- User approved minimal native checks and explicitly instructed not to address
  Longhorn. No further Longhorn queries, snapshots, backup repair or credentials
  changes; no verified data-recovery claim.
- Primary-led execution approved. Existing GHCR/Docker Hub destinations remain.
- New native worktree:
  `/Users/ondrejvala/.local/share/opencode/worktree/b0fea1/oscar-alpine-production`.
  Branch `feat/alpine-production`, production base
  `d6ce76a151439c5209b865aeb4c301a65875c0b0`.
- Only the two documentation commits were cherry-picked from the experiment.
  Do not merge its files wholesale. Old worktree and its dirty ledger remain.
- Scope and acceptance are the approved plan's AP1–AP4 units and file lists.
  The primary currently owns the sole writer slot.

## Units

| ID | Owner/session | Status | Attempts |
|---|---|---|---|
| AP1 | high primary / current session | DONE and pushed main | 2/2 |
| AP2 | high primary | DONE — release verified | 1/2 |
| AP3 | coding-standard when ACTIVE | DONE local; integration authorized | 1/2 |
| AP4 | high primary | PENDING AP2 | 0/2 |

## Rulings and interface preflight

- Ruling: create the separately approved production worktree from main, despite
  existing experimental isolation — preserves the dirty experiment and prevents
  accidental promotion of experimental workflows — cost if wrong: another
  local worktree, no production side effect.
- AP1 → AP2: source/runtime/security receipts must describe the same native OCI
  archives consumed by existing publication. No second image build after tests.
- AP2 → AP3/AP4: only final successfully published index/chart identities may be
  used for Compose and K3s pins; no guessed digest or old tag overwrite.
- AP3 → AP4: same published image, independent repositories; serialize writers.
- Ruling: exclude all Longhorn/snapshot work per the user's latest instruction —
  preserve existing PVCs and normal Recreate rollout instead — data recovery is
  neither performed nor proven if deployment fails.
- Ruling: no second experimental baseline/build/three-image scan campaign.
  Production main source code equals the previously verified d6ce76a state;
  carried specification/plan commits contain documentation only. AP1 will run
  the full local suite after actual changes and native checks in release once.

## Evidence

- Experimental functional proof: commit
  `3e0a144db3bbd4dfe72a94d2c2759e67514145b2`,
  https://github.com/frisbeecz/docker-oscar/actions/runs/44268476981.
- Before production implementation, `origin/main` read back as d6ce76a;
  original checkout retained its six unrelated dirty documents.
- At that initial preflight no production source edits or remote changes existed.

### AP1 progress — source, runtime and scan contracts

- Source-build/provenance RED → GREEN: `artifacts/source-red.log` (10 expected
  failures), `source-green-final.log` (39 passed, exit 0). A portable test shim
  uses the real macOS `shasum -a 256` when `sha256sum` is unavailable.
- Release source/base receipt validation RED → GREEN:
  `artifacts/release-source-red.log` (5 expected failures),
  `release-source-green.log` (6 passed, exit 0).
- Added one full candidate-only Trivy scan and image-bound receipt, with the
  five explicitly accepted HIGH advisory IDs retained in the full report.
  `artifacts/security-red.log` proves the missing module; `security-green.log`
  records 12 passed, exit 0. No scanner or image was run locally.
- Promoted the already exercised synthetic upload/watchdog/retention checks to
  `ci.runtime_checks`, reusing the existing owned volumes/container and initial
  ten-second startup observation. Tests exercise actual embedded check
  functions and the subprocess boundary, including missing/inaccessible-data
  diagnostics. `artifacts/functional-red.log`: 16 expected failures;
  `functional-green.log`: 42 passed, exit 0.
- New release scan-gate test initially called `publish` without its publication
  environment, so unrelated preflight rejection made the negative cases pass.
  Corrected the test to call the actual read-only gate directly. Proper RED:
  `artifacts/release-security-red-direct.log`, 11 DID-NOT-RAISE failures;
  GREEN: `release-security-green.log`, 17 passed including positive evidence
  and source-provenance checks. No false RED claim for the earlier draft.
- All commands above used the original checkout's existing `.venv` interpreter
  and tool PATH, with this production worktree as cwd. AP1 remains in progress:
  workflow/version/docs integration, full local verification and review remain.
  No product commits, pushes, image builds, releases or K3s changes yet.

### AP1 integration — workflow, versions and documentation

- Workflow/cache RED `artifacts/workflow-red.log`: 5 expected failures;
  GREEN `workflow-green.log`: 26 passed, exit 0. Main push skips only native
  builds; release-tag/PR contexts retain them. One candidate scan precedes
  the functional pass. Scanner/cache live in an owned temporary directory,
  not uploaded evidence.
- Version and historical-manifest RED `artifacts/version-red.log`: 2 expected
  failures. Updated project/chart to 1.1.0 and image to 2.1.1-r8, while saved
  startup-only published manifests remain verifiable without relabeling them.
  Compose remains pinned until publication yields its new index digest.
- Updated source/license, runtime/security scope and release documentation.
  Source bundles include the actual newly imported helper modules.
- Intermediate full integration suite: 430 passed, 2 failed
  (`artifacts/integration-pytest.log`). One old exact mount assertion omitted
  the newly required volume-nocopy flag and was updated without dropping its
  read-only check. The other was the existing lint-input safety guard seeing
  the intentionally deleted Debian test still in Git's index. Stage only that
  approved deletion before final validation; do not weaken the input guard.
- Final local command (cwd this production worktree):
  `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH /Users/ondrejvala/projects/oscar/.venv/bin/python -m ci.check --static-only --out-dir artifacts/alpine-production-static`
  exited 0; all six native lint/test groups passed, full pytest **432 passed**
  in 31.19s. Source identity is in its `check.json`.
- Native Helm 3.19.0 and 4.3.2 `ci.check.chart_checks` each exited 0, including
  strict source/package lint, all eight render/strict-schema variants, chart
  regression tests and exact packaged `oscar-1.1.0.tgz` read-back. Evidence:
  `artifacts/alpine-production-helm/helm-<version>/{chart,package}.json`;
  full command output `artifacts/helm-validation.log`.
- No new production native image was built locally. Main CI will run static
  and Helm only; after that succeeds, the release's native jobs must prove
  the production image before it may be published/deployed.
# AP1 review correction — attempt 2/2

The independent review found that a nonempty but structurally incomplete Trivy
`Results` list could pass the publication gate. Accepted after inspecting the
actual validator and retained Alpine report. Correct only report structure and
the expected Alpine/Python package coverage, retaining legitimate empty findings;
add the eight accepted findings fixture and release-gate regressions. This is
AP1's second and final implementation attempt, not a reset. No additional native
build campaign, deployment scope or Longhorn operation is introduced.

Correction evidence (production worktree cwd):
- Expected RED: security structure and matching-hash release regressions,
  `artifacts/security-coverage-red.log`, exit 1 (11 missing-behavior failures;
  one existing invalid-ID rejection already passed).
- Targeted GREEN: security/release tests, exit 0, 130 passed,
  `artifacts/security-coverage-green.log`.
- Full `ci.check --static-only --out-dir artifacts/alpine-production-static-a2`,
  exit 0, all six groups and **448 tests passed** (33.52s).
- The corrected validator also accepted the retained real AMD64 and ARM64 Trivy
  candidate reports, preserving all five HIGH, two MEDIUM and one LOW findings.
  Official Trivy v0.76.2 JSON writer retains named zero-finding targets; tests
  cover omitted, null and empty vulnerability lists without treating them as
  incomplete scans.
- Diff whitespace and AST graph update passed. Helm/chart inputs are unchanged
  since the successful two-version matrix/package verification.
- Awaiting the one scoped re-review; no source changes after the full suite.

Scoped re-review `ses_e11c42dc8ffeaSkHceVvxFxMk3` returned DONE/PASS,
closing the report-coverage P2 and eight-finding fixture gap. No substantive
outstanding local findings. AP1 is approved for the user-authorized main
integration. Production native build/scan/runtime/publication remain AP2, not
inferred from these local results. Preserve the original checkout's six dirty
documents and all existing published references.

### AP1 integration / AP2 gate

- Commit `613da3aeca05befef96b4ed0402ae854018d98bc` pushed and read back on
  `origin/main`; all reviewed source identities and the original checkout's six
  dirty-document hashes matched. No experimental workflow was promoted.
- An initial local `git add` included the already-staged absent Debian test and
  rejected that pathspec; no commit/push occurred in that command. Staged only
  existing approved paths, verified the exact complete staged scope including the
  pre-staged deletion, then committed successfully. No product changes or test
  reruns were needed.
- Main CI: https://github.com/frisbeecz/docker-oscar/actions/runs/44288349299,
  commit above, attempt 1, in progress. Native image work is deliberately skipped
  on this main push; await static/source and both Helm jobs before tagging v1.1.0.
- No release tag, image publication or K3s change yet.

### AP2 attempt 1 — authorized release execution

- Main CI 44288349299 completed successfully on exact reviewed commit
  `613da3aeca05befef96b4ed0402ae854018d98bc`: static/source and both Helm jobs
  passed; native job skipped as designed. Native result JSON:
  `artifacts/alpine-production-review/main-ci.json`.
- All frozen source hashes remain unchanged. Create only new `v1.1.0` at this
  commit and publish through the existing tag workflow. No old reference
  overwrite, manual image rebuild, release deletion or retry. Stop on failed
  release verification; AP3/AP4 require the final published digest.
- New `v1.1.0` tag created/pushed/read back at commit above, exit 0.
  `artifacts/alpine-production-review/tag.json` records the identity.
  Immediate filtered run discovery returned no entry yet (event registration
  lag); no tag push or workflow submission was repeated.
- Release attempt 1:
  https://github.com/frisbeecz/docker-oscar/actions/runs/44288664171,
  correct commit confirmed, in progress. Publication/native acceptance pending.

### AP2 completed; AP3 published-input handoff

- Release 44288664171 completed successfully on the reviewed commit, all six
  jobs PASS. `v1.1.0` is final, not draft/prerelease. Published image
  `ghcr.io/frisbeecz/docker-oscar:2.1.1-r8` and Docker Hub mirror share index
  `sha256:bf0524b3ba21744809c2569a8a770f270c77463d92bbdc96774ba95a87cbfa1a`.
  Chart `1.1.0` OCI digest:
  `sha256:c64778897995504f6490bcc1d33ee173123f4da5f02cafbf32d484daa8db914d`.
- Exact run/release/manifest JSON and native scan/runtime receipts retained under
  `artifacts/alpine-release/`. Native artifact JSON downloaded selectively
  without re-downloading/rebuilding OCI images. Both architectures passed all
  eight functional checks and scan policy: 0 critical, 5 accepted high,
  2 medium, 1 low. These remain real accepted findings, not zero-risk proof.
- AP2 native verification commands exited 0. Release publication itself verified
  anonymous GHCR/Docker Hub index equivalence and exact Helm chart download.
- AP3 writer slot transfers to coding-standard for the previously approved
  mechanical Compose pin/tests/guide update only. No Docker runtime or new
  image build, and no K3s writes in this unit.

### AP3 attempt 1 — Compose pin

- Consumed AP2's verified final `v1.1.0`, run `44288664171`, image
  `ghcr.io/frisbeecz/docker-oscar:2.1.1-r8@sha256:bf0524b3ba21744809c2569a8a770f270c77463d92bbdc96774ba95a87cbfa1a`.
  Changed only the Compose image pin, matching parser contract and stale guide
  version; retained all other Compose settings.
- Commands below used cwd
  `/Users/ondrejvala/.local/share/opencode/worktree/b0fea1/oscar-alpine-production`.
  Standalone parser: `/opt/homebrew/bin/docker-compose`, version `5.8.0`;
  tests execute only its `config` command.
- RED: `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH PYTHONDONTWRITEBYTECODE=1 /Users/ondrejvala/projects/oscar/.venv/bin/python -m pytest -p no:cacheprovider tests/image/test_compose.py::test_quick_start_exposes_only_loopback_without_host_access -q`
  exited 1 with the expected old r5 versus new r8 image assertion.
- GREEN: `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH PYTHONDONTWRITEBYTECODE=1 /Users/ondrejvala/projects/oscar/.venv/bin/python -m pytest -p no:cacheprovider tests/image/test_compose.py -q`
  exited 0, four passed.
- `PATH=/Users/ondrejvala/projects/oscar/.venv/tools/bin:$PATH /Users/ondrejvala/projects/oscar/.venv/bin/python -m ci.check --static-only --out-dir artifacts/alpine-compose-static`
  exited 0; six checks passed and pytest reported 448 passed. Evidence:
  `artifacts/alpine-compose-static/check.json` and `pytest.log`.
- `graphify update .` exited 0, rebuilt the code graph; it warned that saved
  community labels no longer match all communities. `git diff --check` exited
  0; the implementation diff contains only the three intended replacements.
  No Docker runtime, image pull, publication or K3s operation was performed.

- Primary inspected the actual three-file mechanical diff and native receipt:
  all six static groups and 448 tests passed (32.64 s). Accepted the worker's
  remaining concern as the explicit no-local-runtime limitation; AP2 already
  proves the published image's native functional scope. Integration into main
  is authorized by the approved plan. No executable change after verification.
