# Docker Compose guide

The repository's [`compose.yaml`](../compose.yaml) runs the published OSCAR
image without building it. It uses the same browser upload and window recovery
settings exercised in the ARM64 K3s homelab, but does not depend on Kubernetes.

## Requirements and Quick Start

- Docker Engine on Linux, or Docker Desktop with Linux containers.
- Docker Compose v2 or later. Check with `docker compose version`.
  If you have the standalone `docker-compose` executable instead, use that
  spelling in every command below. No Docker configuration change is needed.
- Linux AMD64 or ARM64; Docker selects the matching image from its pinned
  multi-platform index.
- A current Chrome or Edge browser and enough Docker storage for profiles,
  uploaded card copies and backups. Software rendering needs no GPU.

```sh
git clone https://github.com/frisbeecz/docker-oscar.git
cd docker-oscar
docker compose config --quiet
docker compose pull
docker compose up -d
```

Open **http://localhost:3000**. To inspect startup:

```sh
docker compose ps
docker compose logs --tail=100 oscar
```

This is a new installation with fresh volumes, **not an automatic migration**
from an existing OSCAR installation. Follow the [migration guide](migration.md)
before using existing profiles.

## Security and network access

The only published port is `127.0.0.1:3000:3000` (HTTP on the Docker host).
No login is configured in this local example; anyone who can reach that
listener can access OSCAR. Localhost provides the browser secure context needed
by WebCodecs. If Docker is on a remote server, your browser's localhost refers
to your own computer, not that server.

Do not replace the loopback binding with `3000:3000` for Internet access.
Remote/public access needs an authenticated HTTPS reverse proxy supporting
WebSocket upgrades and long-lived connections; see
[browser access](container.md#browser-access). The Compose file does not
install or configure a proxy, passwords, Cloudflare Access or an identity
provider.

The service keeps desktop hardening enabled, disables the command API/Apps
sidebar, sets `no-new-privileges` and drops `NET_RAW`. It requires neither
privileged mode nor host networking, devices, Docker socket or host-directory
mounts. Base initialization runs as root to prepare directories; the desktop
and OSCAR then run as unprivileged `abc`. Do not add `user:` to bypass init.

## Configuration reference

The image is pinned to released **2.1.1-r8**, both by tag and manifest-index
digest. There is deliberately no `latest`, forced CPU architecture or build
step.

Optional `.env` beside `compose.yaml`, set before the first start:

```dotenv
PUID=1000
PGID=1000
TZ=Europe/Prague
```

| Setting | Default | Purpose |
| --- | --- | --- |
| `PUID`, `PGID` | `1000`, `1000` | UID/GID for the unprivileged desktop and new managed data directories |
| `TZ` | `Etc/UTC` | Local IANA time zone |
| `shm_size` | `512m` | Shared memory for the desktop/streaming stack |
| `restart` | `unless-stopped` | Restart the container after an unexpected exit/daemon restart, unless manually stopped |
| `RESTART_APP` | `"true"` | Existing base watchdog restarts OSCAR after it exits |
| `DISABLE_WINDOW_BUTTONS` | `"true"` | Hide minimize, maximize and close controls |
| `HARDEN_KEYBINDS` | `"false"` | Keep the current base image's valid keyboard configuration |
| `DISABLE_MOUSE_BUTTONS` | `"false"` | Preserve the middle-click window list for recovery |
| `SELKIES_FILE_TRANSFERS` | `upload,download` | Enable Files upload, listing and download |
| `SELKIES_UI_SIDEBAR_SHOW_FILES` | `"true"` | Show Files in the browser sidebar |
| `FILE_MANAGER_PATH` | `/config/Uploads` | Root for browser file transfers |
| `HARDEN_DESKTOP` | `"true"` | Retain desktop restrictions |
| `PIXELFLUX_WAYLAND` | `"true"` | Use the image's Wayland desktop |
| `START_DOCKER` | `"false"` | Do not start Docker inside the container |
| `SELKIES_COMMAND_ENABLED` | `"false"` | Keep the command API disabled |
| `SELKIES_UI_SIDEBAR_SHOW_APPS` | `"false"` | Keep the Apps sidebar disabled |

The current pinned base has a broken shortcut-hardening transformation, so
keyboard shortcuts are intentionally retained. Hidden window buttons reduce
accidental hiding/closing; this is not a guarantee that a window can never
disappear or that an application can never hang.

Changing `PUID`/`PGID` later does **not** migrate ownership of existing profile
contents. Do not recursively chown or overwrite real data just to fix startup:
see the [ownership boundary](container.md#operating-boundary).

## Persistent storage

| Named volume | Container path | Access and contents |
| --- | --- | --- |
| `config` | `/config` | Read/write home, settings, desktop state and `Uploads/` |
| `data` | `/config/Documents/OSCAR20_Data` | Read/write OSCAR profile and SQL data |
| `sdcard` | `/config/SDCARD` | Read-only optional SD input, initially empty |

These are Docker-managed named volumes, not folders inside the Git checkout.
`nocopy: true` starts fresh volume roots without copying image-layer contents.
Compose normally prefixes their names with the project name (the checkout
directory name unless overridden); `docker compose config` shows the resolved
names. Keep the same project name across restarts and updates, or Compose may
select a different set of volumes and appear to lose your profiles. Run only
one OSCAR instance against a data volume.

The mounts are nested: backing up `config` alone does **not** back up the
separately mounted `data` and `sdcard`. Browser uploads use `config/Uploads`,
not the read-only SD mount or the profile database directory. This example
does not impose a 1 GiB quota: available space depends on Docker's backing
storage, and uploads share that capacity with the config volume.

Do not substitute an existing nonempty volume without checking ownership and
backing it up. The initializer deliberately leaves existing data untouched,
including root-owned directories containing `lost+found`.

## Upload and import an SD-card copy

1. Preserve the original card; use its physical write-protect switch if
   available. Copy the **entire card** to a folder on your computer.
2. In the OSCAR browser page, open **Files** in the sidebar.
3. In Chrome/Edge, drag the copied folder into Files. Wait for every upload to
   finish, preserving nested directories, filenames and hidden files.
4. In OSCAR, choose the SD import directory
   `/config/Uploads/<your-copied-folder>` — the card root, not an arbitrary
   individual file.
5. Keep the original/local copy until import is confirmed and profiles are
   backed up. Uploaded copies remain until you remove them; clean up only
   copies you no longer need through Files, never the profile database.

ZIP archives are not automatically extracted. The current file manager needs
download permission even for directory browsing, so the configuration enables
both upload and download, confined to the transfer root. It does not provide
an independent system file manager or automatically import files into OSCAR.

## Window recovery and troubleshooting

- **Blank desktop:** middle-click the desktop and choose OSCAR from the
  window list if it is hidden. The existing watchdog relaunches an exited
  application, not an application that is still running but hidden or stuck.
- **Files missing:** refresh the browser page after configuration changes.
  Uploads are under `/config/Uploads`, not `/config/SDCARD`.
- **Page not reachable:** check `docker compose ps` and logs. Port 3000 must
  be free on the Docker host; the default listener is local-only.
- **Permission denied creating data:** check the UID/GID and ownership of
  any reused volume. Fresh Docker volumes are the supported Quick Start;
  existing nonempty data is not automatically repaired.
- **Storage full:** remove only unneeded uploaded copies or increase the
  Docker backing storage. Do not delete a profile or volume as a cleanup step.

## Stop, back up and update

Stop writes before making a consistent backup:

```sh
docker compose stop
```

Back up **all three named volumes** with a Docker volume backup tool, retaining
ownership and permissions. Also save `compose.yaml`, `.env` if used and the
image tag/digest. A copy of a live SQLite main file without its WAL is not a
consistent backup. Restore-test backups into **separate new volumes**, never
over originals; see [backup guidance](container.md#sources-licensing-and-backup)
and [Docker volume backup documentation](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes).
Resume the existing container with `docker compose start`.

To remove containers/network while retaining named volumes:

```sh
docker compose down
```

**Do not use `docker compose down --volumes` / `down -v`: it deletes the named
volumes and their data.** `docker compose up -d` recreates containers using the
retained volumes. Deleting the Git checkout is not a volume backup.

For an update, back up first, read the target release/migration notes, then
change **both** the image tag and its matching index digest from the target
release's `release-manifest.json`. Pulling the pinned current image alone does
not upgrade it:

```sh
docker compose pull
docker compose up -d
```

Do not downgrade a changed profile in place; test rollback with the previous
image and a restored backup on separate volumes.

## Verification limits

The released image passed native AMD64/ARM64 startup smoke tests. Browser
uploads and watchdog recovery were exercised separately in the ARM64 K3s
homelab. Compose configuration tests use the real parser and validate ports,
storage, security flags, settings and overrides **without starting containers**.
They are not a claim of a new Compose runtime/GUI/import or backup/restore test.
