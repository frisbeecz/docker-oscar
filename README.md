# OSCAR with Selkies

Run [OSCAR](https://www.sleepfiles.com/OSCAR/) in a container and access its
CPAP therapy charts and trends through a browser-accessible desktop. This is
independent packaging, not an official OSCAR release.

- Browser desktop with Selkies, Wayland and WebSocket/WebCodecs streaming.
- Linux AMD64 and ARM64 images with software rendering; no GPU required.
- OSCAR built from checksum-verified source on a pinned Alpine/Selkies base.
- Docker Compose for local use and a configurable Kubernetes Helm chart.
- Separate persistent storage for settings, OSCAR profiles and SD-card input.

## Quick Start — Docker Compose

Install Docker Engine on Linux or Docker Desktop with Linux containers, and
**Docker Compose v2 or later**. Then run:

```sh
git clone https://github.com/frisbeecz/docker-oscar.git
cd docker-oscar
docker compose pull
docker compose up -d
```

Open **http://localhost:3000** in a current Chrome or Edge browser. Initial
startup may take a little time; check `docker compose logs --tail=100 oscar`
for progress. Docker selects the matching AMD64 or ARM64 image. If you use the
standalone `docker-compose` executable, substitute it for `docker compose` in
these commands.

The included [`compose.yaml`](compose.yaml) pins a published image by digest;
it does not automatically track the latest image. It binds only to
**127.0.0.1:3000** and configures no login. Anyone who can reach that listener
can access OSCAR. Remote access requires an authenticated HTTPS reverse proxy
with WebSocket support; see the [security guidance](docs/compose.md#security-and-network-access).

### Import a copy of an SD card

1. Copy the **whole card** to your computer, preserving all files and directory
   structure; keep the original safe.
2. Open **Files** in the browser sidebar, drag in the copied folder and wait
   for the upload to finish.
3. In OSCAR, select `/config/Uploads/<your-copied-folder>` as the import
   directory.

The Compose example enables browser uploads and downloads. Uploads persist in
the config volume, separately from the profile database. ZIP files are not
automatically extracted. See the [upload guide](docs/compose.md#upload-and-import-an-sd-card-copy)
for details.

## Storage and backups

The Compose example uses three persistent named volumes:

| Path | Purpose |
| --- | --- |
| `/config` | Settings, desktop state and browser uploads |
| `/config/Documents/OSCAR20_Data` | OSCAR profile and SQL data |
| `/config/SDCARD` | Separate read-only SD input |

The data and SD mounts are nested under `/config` but are separate volumes.
Stop application writes and back up **all three**; backing up config alone does
not include the others. Test restores to separate volumes. For existing
profiles, use the [migration guide](docs/migration.md) and keep originals safe;
startup does not automatically migrate data.

## Documentation

- [Docker Compose guide](docs/compose.md): configuration, storage, [backups](docs/compose.md#stop-back-up-and-update),
  window recovery and [troubleshooting](docs/compose.md#window-recovery-and-troubleshooting).
- [Helm chart guide](docs/chart.md): Kubernetes installation, storage and routing.
- [Container guide](docs/container.md): security, storage and source information.
- [Acceptance scope](docs/acceptance.md): what automated validation does and
  does not cover.

For help or contributions, use [GitHub Issues](https://github.com/frisbeecz/docker-oscar/issues).
See [CI](https://github.com/frisbeecz/docker-oscar/actions) for automated checks.

## License

The container packaging, scripts and Helm chart are licensed under
[Apache-2.0](LICENSE). OSCAR and bundled dependencies retain their own licenses
and source-distribution obligations; see [NOTICE](NOTICE.md).
