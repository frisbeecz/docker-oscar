# OSCAR in your browser

[OSCAR](https://www.sleepfiles.com/OSCAR/) is a desktop application for exploring
CPAP therapy data. This independent container packaging provides its desktop
through a Selkies web session on Linux AMD64 and ARM64.

- Browser access with Chrome or Edge.
- Web upload of complete SD-card directory copies.
- Persistent application settings and a separate OSCAR data volume.
- A single application desktop, hidden window buttons and automatic application
  restart. Keyboard shortcuts can still close or hide a window.
- Docker Compose and Helm deployment options.

## Quick Start: Docker Compose

Install Docker Engine or Docker Desktop with Compose, then:

```sh
git clone https://github.com/frisbeecz/docker-oscar.git
cd docker-oscar
docker compose pull
docker compose up -d
```

Open **http://localhost:3000** in Chrome or Edge.

The Compose file pins a verified GHCR image by digest and is maintained
independently of this mirror. New release images are also mirrored to
**frisbeecz24/docker-oscar** without another build.
Docker Hub tags use the image version, not the chart version. Consult the
[latest release and its manifest](https://github.com/frisbeecz/docker-oscar/releases/latest)
for available tags and immutable digests. There is no floating `latest` tag.

The default port is bound to **127.0.0.1 only** and has no application login.
Do not expose it publicly without an authenticated HTTPS reverse proxy that
supports WebSockets. Localhost or HTTPS is required for browser video features.

## Import an SD-card copy

1. Keep the original card unchanged; copy its complete directory structure.
2. Open **Files** in the web sidebar.
3. Drag the copied directory into the file panel using Chrome or Edge.
4. In OSCAR, import the uploaded copy from `/config/Uploads/<directory>`.

Do not upload only selected files or flatten nested directories. ZIP files are
not automatically extracted. Uploads share the configuration volume's available
disk space, so monitor free space and retain an independent original backup.

## Persistent storage and window recovery

The Compose deployment uses three distinct named volumes:

| Container path | Purpose |
| --- | --- |
| `/config` | Settings and uploaded SD-card copies |
| `/config/Documents/OSCAR20_Data` | OSCAR profiles and imported therapy data |
| `/config/SDCARD` | Separate read-only SD-card input |

Back up **all three volumes** with OSCAR stopped. A backup of `/config` alone
does not include the separately mounted OSCAR data volume. `docker compose down`
retains named volumes; adding `--volumes` deletes them.

If the window disappears, middle-click the desktop to open the window list.
The application watchdog restarts an exited OSCAR process, but it cannot fix
every browser, desktop or application failure.

## Documentation and support

- [Compose configuration, backups and troubleshooting](https://github.com/frisbeecz/docker-oscar/blob/main/docs/compose.md)
- [Helm chart deployment](https://github.com/frisbeecz/docker-oscar/blob/main/docs/chart.md)
- [Container settings and security](https://github.com/frisbeecz/docker-oscar/blob/main/docs/container.md)
- [Verification scope](https://github.com/frisbeecz/docker-oscar/blob/main/docs/acceptance.md)
- [Report an issue](https://github.com/frisbeecz/docker-oscar/issues)

This is an independent project, not an official OSCAR distribution. Packaging
code is Apache-2.0; OSCAR and bundled components retain their respective licenses.
See [NOTICE.md](https://github.com/frisbeecz/docker-oscar/blob/main/NOTICE.md).
