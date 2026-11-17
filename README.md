# OSCAR with Selkies

Run [OSCAR](https://www.sleepfiles.com/OSCAR/) in a container and access its
desktop from your web browser. OSCAR helps you explore CPAP therapy data,
review nightly charts and follow trends over time.

The project provides:

- **A browser-accessible desktop** powered by Selkies, Wayland and
  WebSocket/WebCodecs streaming.
- **AMD64 and ARM64 image targets** using official OSCAR **2.1.1** Debian13
  Qt6 packages on LinuxServer's Debian13 Selkies base. The current image build revision is
  **2.1.1-r6**.
- **A Kubernetes Helm chart** with configurable storage, resources, Ingress
  and Gateway API routing.
- **Persistent profiles and settings**, with separate volumes for application
  configuration, OSCAR data and SD-card imports.
- **Docker Compose Quick Start** with local-only access, browser uploads and
  automatic application restart.

## Quick Start — Docker Compose

Install Docker Engine or Docker Desktop with **Docker Compose v2 or later**.
No Python, Kubernetes, local image build or GPU is needed to run the release.

```sh
git clone https://github.com/frisbeecz/docker-oscar.git
cd docker-oscar
docker compose pull
docker compose up -d
```

Open **http://localhost:3000** in a current Chrome or Edge browser. Initial
startup may take a little time; use `docker compose logs --tail=100 oscar` to
check progress. The published image selects Linux AMD64 or ARM64 automatically.
If your installation provides the standalone `docker-compose` executable
instead, substitute it for `docker compose` in these commands.

The included [`compose.yaml`](compose.yaml) creates three persistent named
volumes and binds **only to 127.0.0.1**. It intentionally remains pinned to
the published **2.1.1-r5** image by immutable digest, not the current r6 build. This local example has no login configured:
do not change it to a public listener without an authenticated HTTPS proxy.

To import a copy of an SD card:

1. Copy the **whole card**, preserving all files and directory structure.
2. Open **Files** in the browser sidebar and drag in the copied folder.
3. In OSCAR, import from `/config/Uploads/<your-copied-folder>`.

Uploads persist in the config volume, separately from the OSCAR profile/data
volume. Do not upload into the profile database directory or alter the original
card. ZIP files are not automatically extracted.

See the **[Compose guide](docs/compose.md)** for all settings, storage,
window recovery, backups, upgrades and troubleshooting. For Kubernetes, use the
[Helm chart guide](docs/chart.md).

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

## Verification scope

[The v0.1.4 Actions run](https://github.com/frisbeecz/docker-oscar/actions/runs/44067963403)
passed native AMD64/ARM64 `startup-smoke-v1` and both Helm validation matrices.
The startup smoke requires a running container, HTTP200 and the same
unprivileged OSCAR process for at least 10 seconds. It is not a full GUI,
CPAP import or profile-restoration test.

Separate ARM64 K3s homelab checks exercised browser uploads and automatic
application restart; browser use and uploads were also manually confirmed.
Those observations do not expand the automated CI guarantees. Compose parser
checks validate this example's configuration, not a fresh Compose runtime or
browser session. See [CI](https://github.com/frisbeecz/docker-oscar/actions) and
the [acceptance guide](docs/acceptance.md) for the automated scope.

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
for chart render and packaging tests, and a Docker Compose CLI for Compose
configuration tests. Those Compose tests do not need a Docker daemon.

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
