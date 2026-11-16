FROM lscr.io/linuxserver/baseimage-selkies:debiantrixie@sha256:d03d09e9ceb770032db5892dd7caa9b207ef09b55a9b79491a1c4d37842e6c01
ARG TARGETARCH
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="OSCAR with Selkies" \
    org.opencontainers.image.version="2.1.1-r2" \
    org.opencontainers.image.revision="${VCS_REF}" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.source="https://github.com/frisbeecz/docker-oscar"
ENV PIXELFLUX_WAYLAND=true RESTART_APP=true HARDEN_DESKTOP=true \
    START_DOCKER=false HOME=/config TITLE=OSCAR \
    QT_QPA_PLATFORM=wayland LIBGL_ALWAYS_SOFTWARE=true \
    XDG_CONFIG_HOME=/config/.config XDG_DATA_HOME=/config/.local/share \
    XDG_CACHE_HOME=/config/.cache
# Official unmodified Debian13 Qt6 packages; validate bytes and metadata before apt.
RUN case "$TARGETARCH" in \
      amd64) sha256=a9256776774e9ae1313feb5ed0aa5fe38eb808168c3e2d5ea0e3e3ce4ce289dc ;; \
      arm64) sha256=6973e4f8d81f170a6d59ea1205c954e231c8158f10c433cec3bc23e903f9bece ;; \
      *) echo "Unsupported OSCAR architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && test "$(dpkg --print-architecture)" = "$TARGETARCH" \
    && curl --fail --location --connect-timeout 20 --max-time 300 \
      --max-filesize 134217728 \
      "https://www.sleepfiles.com/OSCAR/2.1.1/oscar20_2.1.1-Debian13_${TARGETARCH}-Qt6.deb" \
      -o /tmp/oscar.deb \
    && echo "$sha256  /tmp/oscar.deb" | sha256sum -c - \
    && test "$(dpkg-deb -f /tmp/oscar.deb Package)" = oscar20 \
    && test "$(dpkg-deb -f /tmp/oscar.deb Version)" = 2.1.1-Debian13 \
    && test "$(dpkg-deb -f /tmp/oscar.deb Architecture)" = "$TARGETARCH" \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      /tmp/oscar.deb libqt6sql6-sqlite qt6-wayland qt6-translations-l10n \
      libgl1-mesa-dri fonts-dejavu-core \
    && rm -f /tmp/oscar.deb \
    && rm -rf /var/lib/apt/lists/*
RUN test -x /usr/bin/OSCAR20 \
    && test -d /usr/share/OSCAR20/Translations \
    && test -d /usr/share/OSCAR20/Html \
    && test -f /usr/share/doc/oscar20/copyright \
    && mkdir -p /usr/share/oscar \
    && dpkg-query -W > /usr/share/oscar/runtime-packages.txt
COPY LICENSE NOTICE.md versions.lock.json /usr/share/oscar/
COPY root/ /
RUN chmod 755 /usr/local/bin/oscar-start /etc/s6-overlay/s6-rc.d/init-oscar-data/run
# Retain base /init, services, UID/GID handling and watchdog; OSCAR runs as abc.
