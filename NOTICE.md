# Copyright, licensing and origin

New packaging, launcher, CI harness, tests and documentation in this project:
Copyright (C) 2026 docker-oscar contributors, **Apache-2.0**.
The complete Apache License, Version 2.0 is in [LICENSE](LICENSE).
This also covers the independently written Helm chart. The project license
metadata (including the OCI label and source manifest's `license` field)
describes this packaging, not an exhaustive license inventory of the image.
OSCAR, Qt, the Selkies base and other bundled dependencies are **not**
relicensed by this declaration.

Licensing amendment: the project owner approved Apache-2.0 after the initial
GPL-3.0-only packaging revisions. The original design/plan remain historical
records; this notice supersedes their choice of license for our own code only.
Previously granted GPL permissions for earlier revisions are not revoked.

This is independent packaging, not an official OSCAR release or a fork of OSCAR.
No code from rogerrum/docker-oscar has been copied.

- **OSCAR Team**: OSCAR 2.1.1, commit
  `4f14624616d62c6986788417bc5c519c807a7ade`, from
  <https://gitlab.com/CrimsonNape/OSCAR-SQL>. Original copyright notices,
  including its **SleepyHead** origins and Mark Watkins' contributions,
  remain in the exact source archive. Its `COPYING` and individual file
  notices govern upstream code; our license does not narrow upstream grants.
- **LinuxServer.io / Selkies contributors**: Selkies Debian13 (`debiantrixie`) base,
  <https://github.com/linuxserver/docker-baseimage-selkies>, source commit
  `e45b4fe636ee99860a40eb552d0e4b21aefad842`, immutable image index and per-arch
  manifests in `versions.lock.json`. Base licensing and bundled components
  retain their upstream licenses. Selkies:
  <https://github.com/selkies-project/selkies>, PixelFlux and PCMFlux:
  <https://github.com/selkies-project>.
- **Qt** and its contributors: dynamically linked Qt6 under the applicable
  LGPL/GPL/commercial upstream terms, <https://www.qt.io/licensing/> and
  <https://code.qt.io/>. This project does not relicense Qt.
- **Debian** and package authors: individual licenses in
  `/usr/share/doc/<package>/copyright`, common license texts in
  `/usr/share/common-licenses/`, corresponding package sources at
  <https://sources.debian.org/> and <https://snapshot.debian.org/>.
  The exact installed package inventory is inside the image at
  `/usr/share/oscar/runtime-packages.txt`; distribution dependencies are not
  claimed to be byte-reproducible.
- **Official OSCAR binary packages**: unmodified
  `oscar20_2.1.1-Debian13_{amd64,arm64}-Qt6.deb` from
  <https://www.sleepfiles.com/OSCAR/2.1.1/>, with independently checked published
  SHA256 values in `versions.lock.json`. Package copyright declares GPL-3+
  and remains at `/usr/share/doc/oscar20/copyright`; the executable and resources
  remain at `/usr/bin/OSCAR20` and `/usr/share/OSCAR20/`.
- Test-only tools retain their licenses: Playwright (Apache-2.0), Tesseract
  (Apache-2.0), Skopeo (Apache-2.0), Docker/BuildKit/Buildx, Helm, kind and
  kubeconform. Exact tool origins/checksums are in `ci/tools.lock.json` and
  the fully hashed `requirements-ci.lock`.

`python3 -m ci.source_bundle --out-dir artifacts/sources` produces the exact
upstream source, unmodified upstream COPYING, explicit empty patch list,
our image build/launcher/harness source archive and checksum/origin manifest.
The manifest explicitly records the official binary URLs, hashes, architecture
and package version. Source tag `v2.1.1`, package version `2.1.1-Debian13`
and embedded short source commit align. This is not an independently proven
binary-to-source correspondence or reproducible upstream build: before
redistribution, resolve any missing corresponding-source/build-input obligations
for these upstream binaries as well as the base and dependencies.
No profile/database fixtures or private data belong in that bundle.
Distributors remain responsible for satisfying the source/license obligations
of **all** included components; a link to this repository or our LICENSE alone
is not a substitute for those obligations. Retain matching base/package source
availability when redistributing the complete image.
