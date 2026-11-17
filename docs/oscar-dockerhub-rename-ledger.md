# OSCAR-DOCKERHUB-RENAME

- Owner/writer: high primary; location `/Users/ondrejvala/projects/oscar`.
- Base: `7931d3860c70b0d0f1e0f65bf03c4d8a1ec6809f`.
- Attempt: 1/2. State: locally verified; integration and execution authorized.
- Approval: user approved `frisbeecz24/docker-oscar`, including the existing
  image, and requested Docker Hub overview/documentation, description and category.
- Scope: `ci/dockerhub.py`, `ci/release.py`,
  `.github/workflows/dockerhub.yaml`, `tests/ci/test_dockerhub.py`,
  `tests/ci/test_release.py`, `tests/ci/test_policy.py`,
  `docs/dockerhub.md`, `docs/distribution.md`, `docs/releasing.md`, this ledger,
  ignored `artifacts/dockerhub-rename-a1/` and generated graph updates.
- Preserve all five pre-existing dirty documents, old registry artifacts, release
  manifests, version tags, Compose pins, K3s and authentication settings.

## Acceptance and execution

1. Future releases use only the new Docker Hub destination; saved manifests
   pointing to the former approved destination remain verifiable.
2. Synchronize a short description, an absolute-link user overview and the
   Docker Hub `data-science` category using the existing Actions secret.
3. A main-branch-only manual workflow copies the already published v1.0.2
   image `2.1.1-r7` by its known immutable GHCR index digest, preserving both
   architectures and all digests without rebuilding or overwriting other content.
4. Reuse a matching destination tag; stop on a conflicting tag. Create the
   requested public repository only if absent; never change existing privacy.
5. Secrets remain in memory/stdin or temporary private registry authentication;
   no credentials in command arguments, reports or redirected HTTP requests.
6. Native full static/pytest verification, independent security/acceptance review,
   then request commit/push/manual-execution approval. No live credential probes
   or registry mutations during local implementation.

## Stop conditions

Real authorization/quota/infra failure, concurrent checkout changes, conflicting
published image, private destination, or a required scope decision: stop and report.
No automatic retry, destructive cleanup, release rerun or secret-scope changes.

## References

- Docker Hub repository information:
  <https://docs.docker.com/docker-hub/repos/manage/information/>
- Authentication and repository creation:
  <https://docs.docker.com/reference/api/hub/latest/>
- Metadata/category update implementation reference:
  <https://github.com/docker-library/docs/blob/master/push.pl>
- Existing image index:
  `sha256:386ff28089d399c1305f42cb811a53ce9c9ac18695981888fb13094d348fad0f`.

## Local evidence

- Expected RED: renamed-destination publication test failed because the old
  publisher still copied to `frisbeecz24/frisbeecz`; exit 1, `red.log`.
- Initial targeted GREEN: 110 passed, exit 0, `green.log`.
- Additional native API-boundary regression: successful metadata PATCH responses
  need not contain JSON. Watched empty-response RED, then accepted an empty
  successful body without changing HTTP failure/redirect handling.
- `.venv/bin/python -m ci.check --static-only --out-dir artifacts/dockerhub-rename-static-a1`
  in the stated checkout: exit 0; all six native groups passed,
  **387 pytest tests passed in 31.84s**. Includes native Helm compatibility tests,
  actual workflow/action linting, real urllib redirect rejection, fixed-image
  migration, conflict protection, credential cleanup and old-manifest compatibility.
- After the suite only overview prose clarified that Compose retains its own
  independent immutable GHCR pin; source, workflows and tests are unchanged.
- Evidence and complete relevant diff: ignored `artifacts/dockerhub-rename-a1/`.
- Live Docker Hub creation, token permissions, metadata and image migration have
  not been exercised. No commit, push, manual dispatch or new release yet.
- Independent review `ses_e1467b37fffevewfluKfArQczl`: DONE, local acceptance PASS
  and quality/security PASS, no substantive findings. No source/test corrections.
  External mutation remains non-atomic; an out-of-band concurrent tag writer
  is outside the workflow lock.

## Integration approval

- User approved commit, push and one execution of the fixed-image migration,
  including overview, short description and Data science category.
- Before integration, all nine reviewed source/document hashes and all five
  pre-existing dirty document hashes matched their saved receipts. The full
  387-test/static receipt remains applicable; no executable changes since it.
- Preserve the old Docker Hub repository and every existing release/tag.
