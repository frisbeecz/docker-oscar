# Throwaway native feasibility build. Never used by the release workflow.
FROM ghcr.io/linuxserver/baseimage-selkies:alpine324@sha256:f2820b8df78eb020785850492c2b6547de2c762fcfcd644b11d4f7e211f5a987 AS build
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
RUN apk add --no-cache \
      build-base bash python3 curl ca-certificates \
      qt6-qtbase-dev qt6-qtserialport-dev qt6-qttools \
      libx11-dev zlib-dev glu-dev
WORKDIR /src
RUN curl --fail --location --connect-timeout 20 --max-time 300 \
      "https://gitlab.com/CrimsonNape/OSCAR-SQL/-/archive/4f14624616d62c6986788417bc5c519c807a7ade/OSCAR-SQL-4f14624616d62c6986788417bc5c519c807a7ade.tar.gz" \
      -o /tmp/oscar-source.tar.gz \
    && echo "063b4b6e797d40f8d060453f865fb0e5f48c71cbb72adee0387e76e844313dad  /tmp/oscar-source.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/oscar-source.tar.gz --strip-components=1 \
    && rm /tmp/oscar-source.tar.gz
WORKDIR /build
# Keep upstream graphics selection and diagnostics: no source patches or warning suppression.
RUN qmake6 /src/OSCAR_QT.pro 'CONFIG+=release' 'CONFIG-=debug' \
    && make -j2 \
    && test -x /build/oscar/OSCAR20 \
    && test -f /build/oscar/Html/about.html \
    && test -d /build/oscar/Translations

FROM ghcr.io/linuxserver/baseimage-selkies:alpine324@sha256:f2820b8df78eb020785850492c2b6547de2c762fcfcd644b11d4f7e211f5a987
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
LABEL org.opencontainers.image.title="EXPERIMENTAL OSCAR Alpine feasibility probe" \
      org.opencontainers.image.source="https://github.com/frisbeecz/docker-oscar"
ENV PIXELFLUX_WAYLAND=true RESTART_APP=true HARDEN_DESKTOP=true \
    START_DOCKER=false HOME=/config TITLE=OSCAR \
    QT_QPA_PLATFORM=wayland LIBGL_ALWAYS_SOFTWARE=true \
    XDG_CONFIG_HOME=/config/.config XDG_DATA_HOME=/config/.local/share \
    XDG_CACHE_HOME=/config/.cache
RUN apk add --no-cache \
      qt6-qtbase-x11 qt6-qtbase-wayland qt6-qtbase-sqlite \
      qt6-qtserialport qt6-qtwayland qt6-qttranslations \
      libx11 zlib glu font-dejavu mesa-dri-gallium
COPY --from=build /build/oscar/OSCAR20 /usr/bin/OSCAR20
COPY --from=build /build/oscar/Html/ /usr/share/OSCAR20/Html/
COPY --from=build /build/oscar/Translations/ /usr/share/OSCAR20/Translations/
COPY --from=build /src/COPYING /usr/share/licenses/OSCAR20/COPYING
COPY LICENSE NOTICE.md /usr/share/oscar/
COPY root/ /
RUN chmod 755 /usr/local/bin/oscar-start /etc/s6-overlay/s6-rc.d/init-oscar-data/run \
    && apk info -v > /usr/share/oscar/runtime-packages.txt \
    && ldd /usr/bin/OSCAR20 > /usr/share/oscar/ldd.txt \
    && ! grep -q 'not found' /usr/share/oscar/ldd.txt
