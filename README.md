# OSCAR with Selkies

Run [OSCAR](https://www.sleepfiles.com/OSCAR/) in a container and access its
desktop from your web browser. OSCAR helps you explore CPAP therapy data,
review nightly charts and follow trends over time.

The project provides:

- **A browser-accessible desktop** powered by Selkies, Wayland and
  WebSocket/WebCodecs streaming.
- **AMD64 and ARM64 image targets** using official OSCAR **2.1.1** Debian13
  Qt6 packages on LinuxServer's Debian13 Selkies base. The current image revision is
  **2.1.1-r3**.
- **A Kubernetes Helm chart** with configurable storage, resources, Ingress
  and Gateway API routing.
- **Persistent profiles and settings**, with separate volumes for application
  configuration, OSCAR data and SD-card imports.

## Kubernetes and storage

The chart lives in [`charts/oscar`](charts/oscar). Start with its default values
and configure storage and HTTPS access for your cluster. See the
[chart guide](docs/chart.md) for routing, existing volumes and configuration.

The container uses these persistent paths:

| Mount | Purpose |
| --- | --- |
| `/config` | Home, Qt configuration and desktop state |
| `/config/Documents/OSCAR20_Data` | Separate OSCAR2 SQL data volume |
| `/config/SDCARD` | Separate SD input, read-only by default |

Set `PUID`, `PGID` and `TZ` for file ownership and your local time zone.
OSCAR uses software rendering and stores its SQL data in
`/config/Documents/OSCAR20_Data`.

For an existing OSCAR installation, follow the [migration guide](docs/migration.md)
to back up and import profiles using separate working copies. Keep the original
data and volumes available for rollback. The
[container guide](docs/container.md) covers access security and backups of each
volume.

## Development status

The current startup-only smoke still awaits native verification on both
architectures. The user-approved 2026-11-15 scope supersedes the historical
GUI/profile/persistence/Kubernetes acceptance plan: start the container, require
HTTP200, and observe the same unprivileged OSCAR process for at least 10 seconds.
It does **not** verify remote GUI usability/media, import, profile/data persistence,
watchdog behavior, or actual Kubernetes installation/routing. Follow
[CI](https://github.com/frisbeecz/docker-oscar/actions) and the
[acceptance guide](docs/acceptance.md) for verification evidence.

## Development

Development and CI use **Python 3.14**. Create a local environment:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-ci.lock
python -m ci.check --install-tools
python -m ci.check
```

The check command runs linters, image/chart/CI contract tests and both Helm
matrices. Use `python -m pytest -q` for the static test suite; Helm is required
for chart render and packaging tests.

Native CLI, on matching **disposable GitHub-hosted Linux runners only**:

```sh
python3 -m ci.build_image --arch amd64 --out-dir artifacts/native/amd64
python3 -m ci.runtime --image oscar-under-test:amd64 --arch amd64 \
  --run-id image01-amd64 --artifacts artifacts/native/amd64
```

Use the corresponding `arm64` values on a native ARM64 runner. The Buildx
docker-container driver bootstraps privileged BuildKit infrastructure; that
is not authorized on a developer machine by the mere presence of Docker.
The application runs with the chart's constrained workload security settings.
Publication and Helm render/schema validation have separate CI gates.

## CI and release

PR/main checks use read-only tokens and SHA-pinned Actions. Native AMD64 and
ARM64 jobs build/import exact OCI bytes and run `startup-smoke-v1`; neither
browser/OCR nor kind is launched. Both Helm matrices remain mandatory. Release
workflows validate the tagged commit, publish corresponding sources first and
distribute the tested image and chart artifacts.

See [acceptance/evidence](docs/acceptance.md), [release trust boundary and
commands](docs/releasing.md), and [chart configuration](docs/chart.md).

## License

The container packaging, scripts and Helm chart are licensed under
[Apache-2.0](LICENSE). OSCAR and bundled dependencies retain their respective
licenses and source-distribution requirements; see [NOTICE](NOTICE.md).
