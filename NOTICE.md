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
- **LinuxServer.io / Selkies contributors**: Selkies Alpine 3.24 (`alpine324`) base,
  <https://github.com/linuxserver/docker-baseimage-selkies>, source commit
  `4acbc9ebc23dfdc0ed6f815223f13412bd3735f5`, immutable image index and per-arch
  manifests in `versions.lock.json`. Base licensing and bundled components
  retain their upstream licenses. Selkies:
  <https://github.com/selkies-project/selkies>, PixelFlux and PCMFlux:
  <https://github.com/selkies-project>.
- **Qt** and its contributors: dynamically linked Qt6 under the applicable
  LGPL/GPL/commercial upstream terms, <https://www.qt.io/licensing/> and
  <https://code.qt.io/>. This project does not relicense Qt.
- **Alpine Linux** and package authors: applicable individual package licenses
  and corresponding package recipes/sources at
  <https://gitlab.alpinelinux.org/alpine/aports>.
  The exact installed package inventory is inside the image at
  `/usr/share/oscar/runtime-packages.txt`; distribution dependencies are not
  claimed to be byte-reproducible.
- **OSCAR source build**: the unpatched archive at the exact commit above is
  checksum-verified before extraction and compiled natively against Alpine Qt6.
  Its COPYING remains at `/usr/share/licenses/OSCAR20/COPYING`; executable and
  resources remain at `/usr/bin/OSCAR20` and `/usr/share/OSCAR20/`.
  The source-build recipe and hash-locked Python wheels are recorded in
  `versions.lock.json` and `python-requirements.txt`.
- Test-only tools retain their licenses: Playwright (Apache-2.0), Tesseract
  (Apache-2.0), Skopeo (Apache-2.0), Docker/BuildKit/Buildx, Helm, kind and
  kubeconform, plus Trivy (Apache-2.0). Exact tool origins/checksums are in `ci/tools.lock.json` and
  the fully hashed `requirements-ci.lock`.

`python3 -m ci.source_bundle --out-dir artifacts/sources` produces the exact
upstream source, unmodified upstream COPYING, explicit empty patch list,
our image build/launcher/harness source archive and checksum/origin manifest.
The manifest records source commit/archive hash, build recipe, Python
requirements, pinned base and actual packaging-input hashes. The produced OSCAR
binary is built from that source, rather than a separately distributed Debian
binary. This is not a reproducible-build or complete redistribution-compliance
claim: distribution package repositories are live and obligations for the base,
Qt and all other dependencies still need to be satisfied.
No profile/database fixtures or private data belong in that bundle.
Distributors remain responsible for satisfying the source/license obligations
of **all** included components; a link to this repository or our LICENSE alone
is not a substitute for those obligations. Retain matching base/package source
availability when redistributing the complete image.
