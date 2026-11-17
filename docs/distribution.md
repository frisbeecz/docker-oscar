# Docker Hub and Artifact Hub

GitHub Actions publishes the tested image to GHCR and mirrors the **same
multi-platform index** to Docker Hub. The Helm chart stays in GHCR; Artifact Hub
is a discovery catalog, not another chart registry.

## Docker Hub setup

1. Use the Docker Hub account **`frisbeecz24`** and create a **public** repository
   named **`frisbeecz`**. Check that its image-version tags do not conflict with
   any existing content. The pipeline does not change repository visibility.
2. Create a Docker Hub access token with permission to push to that repository.
3. Store it as a GitHub Actions repository secret. Run this in your own terminal
   and paste the token at the interactive prompt, not into the command itself:

   ```sh
   gh secret set DOCKERHUB_TOKEN --repo frisbeecz/docker-oscar
   ```

   Never commit the token, put it in Helm/Compose values, or send it in an issue.
   Local `docker login` does not configure GitHub Actions.

Only the trusted release publish step receives the secret. Missing credentials
stop publication before external writes. Existing job-scoped `GH_TOKEN` still
authenticates GHCR and GitHub Releases.

## Release behavior

Push a fresh release tag following [the release guide](releasing.md). After CI
and the corresponding-source availability check:

- Existing tested AMD64/ARM64 artifacts are published to GHCR.
- Skopeo copies the complete image index from its **digest reference**, with
  `--all --preserve-digests`, to
  `docker.io/frisbeecz24/frisbeecz:<image-tag>`.
- Nothing is rebuilt, and no `latest` tag is created.
- The final anonymous read checks that the Docker Hub tag has the same index
  digest as GHCR before the GitHub prerelease is finalized.

`release-manifest.json` records `imageTag`, `imageIndexDigest` and
`dockerHubRepository`. The image tag is distinct from the chart/release version.
Use the recorded image tag or digest when pulling from Docker Hub:

```text
docker pull frisbeecz24/frisbeecz:<image-tag>
docker pull frisbeecz24/frisbeecz@sha256:<image-index-digest>
```

Replace the placeholders with values from an actually verified release.
Existing deployments and the pinned Compose image are not switched to
Docker Hub automatically.

Use fresh image/chart versions for each new release. Publishing across
registries is not atomic: a failure can leave a prerelease or some artifacts
uploaded. There is no automatic retry, tag replacement or cleanup recovery.
Do not rerun an old release to overwrite published content.

## Register the chart with Artifact Hub

This is a **one-time action in your Artifact Hub account**:

1. Sign in at [Artifact Hub](https://artifacthub.io/).
2. In the control panel, add a repository of kind **Helm charts**.
3. Choose an available repository name, for example `docker-oscar`.
4. Use this exact repository URL, without a version tag:

   ```text
   oci://ghcr.io/frisbeecz/charts/oscar
   ```

5. Save it, then check the repository's tracking status and errors. GHCR chart
   manifests/packages must be anonymously readable.

Artifact Hub automatically indexes published SemVer chart versions after
registration. GitHub Actions keeps publishing to the existing OCI location;
no Artifact Hub API token or extra publish job is needed for normal indexing.
The chart metadata supplies its description, source, maintainer, keywords,
license and documentation/support links.

Repository ownership verification is optional and separate. It uses the
Artifact Hub-assigned repository ID and an `artifacthub-repo.yml` OCI artifact
under the special `artifacthub.io` tag. This setup does not create that artifact
or claim a Verified Publisher badge.

Metadata changes apply to the **next fresh chart release**. Existing immutable
chart versions are not overwritten, and Artifact Hub cannot force-reindex an
existing OCI version by changing its digest. Editing these files alone does
not publish a new image/chart or register the repository.

References:
- [Artifact Hub Helm/OCI repositories](https://artifacthub.io/docs/topics/repositories/helm-charts/)
- [Supported chart annotations](https://artifacthub.io/docs/topics/annotations/helm/)
- [Skopeo copy options](https://github.com/containers/skopeo/blob/main/docs/skopeo-copy.1.md)
