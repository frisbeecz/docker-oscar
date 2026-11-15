# OSCAR Selkies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodat samostatný veřejný projekt s OSCAR 2.1.1/Selkies pro AMD64 i ARM64, obecným Helm chartem a skutečně ověřeným GitHub release.

**Architecture:** Jedna udržovaná Selkies image: nejprve Alpine/Qt6 build oficiálních zdrojů, při doložené zásadní překážce schválený Debian fallback. Obecný chart odděluje config/data/SD PVC a nezávisle zapíná Ingress a HTTPRoute. CI nativně ověří image, GUI, persistenci a instalaci chartu před publikací stejných image artefaktů.

**Tech Stack:** LinuxServer Selkies/Wayland, OSCAR/Qt6/qmake, Docker Buildx/OCI, Helm 3 a 4, Kubernetes/Gateway API, Python/pytest/Playwright, GitHub Actions/GHCR.

**Spec:** `docs/superpowers/specs/2026-11-15-oscar-selkies-design.md` — uživatelem schválena 2026-11-15; SHA256 `29ec9e4fe38f98f2e8fdd50f28efb4f045afeaa6c64c02c2c7c5ebf7a1bc4867`.

## Global Constraints

- OSCAR `2.1.1`, upstream commit `4f14624616d62c6986788417bc5c519c807a7ade`; nikoliv `2.2.0-alpha-1` ani pohyblivý HEAD.
- Linux `amd64` a `arm64`; nativní runtime test na obou, samotná emulace nestačí.
- Image `ghcr.io/frisbeecz/docker-oscar`; nový samostatný veřejný projekt `frisbeecz/docker-oscar`, ne fork.
- Jedna OS varianta: Alpine preferováno, Debian povolen při doložených zásadních problémech; změna strategie spotřebuje další pokus IMAGE-01.
- `/config`, `/config/Documents/OSCAR20_Data`, `/config/SDCARD`; explicitní `--datadir`, SD standardně read-only.
- `replicaCount: 1`, `Recreate`, žádný automatický import, migrace ani ephemeral fallback.
- Spravované claims `<fullname>-config-v2`, `<fullname>-data-v2`, `<fullname>-sdcard-v2`; `existingClaim` pouze explicitně.
- HTTP `3000` uvnitř clusteru; HTTPS nebo podporovaný lokální secure context v prohlížeči; WebSocket/WebCodecs bez povinného UDP/TURN.
- `ingress.enabled: false`, `gateway.enabled: false`; chart neinstaluje controllery, Gateway, CRD ani cert-manager.
- Workload bez privileged/hostNetwork/hostPath/Docker socketu, bez eskalace oprávnění a automatického SA tokenu; root init není příslib `runAsNonRoot`.
- Nový kód `GPL-3.0-only`; licence závislostí beze změn, attribution a odpovídající zdroje s releasem.
- Žádné upravené PROD values ani privátní infrastruktura ve veřejném projektu; skutečná integrace patří až do samostatné privátní fáze.
- Žádný přístup k medicínským datům, produkčnímu clusteru, změnám auth/model/provider/account nastavení nebo placené infrastruktuře.
- Read-only PR tokeny, `pull_request`, plné SHA Actions; publish až po testech, bez nového sestavení otestovaných image.
- Evidence = přesný příkaz, cwd, exit, commit/diff/artefakt; GitHub runs a pull release artefaktů nejsou nahraditelné lokálními kontrolami.

## Review Focus

1. Dlouhé fullname a existující claims: odlišné, stabilní názvy do 63 znaků, žádné zkrácení obou claimů na stejné jméno; Task 2/test `test_claim_names_long_release`.
2. `storageClass: null` versus `storageClass: ""`: cluster default versus úmyslně žádná třída; Task 2/test `test_storage_class_three_states`.
3. Persistovaný desktopový autostart a nenulové UID/GID: po restartu skutečný OSCAR a Qt nastavení, nikoliv jen dostupný nginx; Task 1/runtime `test_application_state_survives_recreation`.
4. Uninstall a znovupoužití storage: spravované PVC zachována, explicitní cizí claims nedotčena; Task 2/test `test_uninstall_preserves_claims`.
5. Selhání architektury/testu a záměna artefaktu: žádný částečný release nebo nově sestavený image vydávaný za testovaný; Task 3/tests `test_release_dependency_closure`, `test_reject_mismatched_receipt`.

---

## Provedení, scope a evidence

Location/cwd pro všechny lokální příkazy: kořen nového projektu,
aktuálně `/Users/ondrejvala/projects/oscar`. Relativní cesty níže jsou vůči němu.
Před schválením tohoto plánu jsou povoleny jen dokumenty procesu a read-only
průzkum. Vytvoření Git/GitHub projektu, závislosti, buildy a testovací procesy
začnou až po schválení plánu a volbě execution.

Jde o jeden distribuovatelný celek, nikoliv o přepis OSCARu. Tři implementační
jednotky mají vlastní testovací cykly; Task 4 jen uzavírá důkazy a distribuci.
Příprava infrastruktury/testů patří k jejich deliverable, nemá vlastní pokusy.

| ID | Owner/režim | Přesný write scope | Acceptance |
| --- | --- | --- | --- |
| IMAGE-01 | primary/high, write | Soubory a adresáře vyjmenované v Task 1, lokální `.git` při skutečném založení projektu | Ověřené zdroje/licence, bezpečný image kontrakt a funkční native runtime/persistence harness |
| CHART-01 | primary/high, write | `charts/oscar/`, `tests/chart/`, `ci/chart.py`, `ci/kubernetes.py`, `tests/fixtures/kind.yaml`, `docs/chart.md` | Celá chart matice a izolovaný install/restart/uninstall smoke |
| CI-01 | primary/high, write | `.github/workflows/`, `ci/check.py`, `ci/release.py`, `tests/ci/`, `docs/releasing.md`, `docs/acceptance.md`, `README.md`; pouze doplnění release nástrojů v `ci/tools.lock.json` | Skutečné bezpečné GitHub běhy, gate a distribuce přesně ověřených artefaktů |
| INTEGRATE-01 | deferred | Žádné změny v této fázi | Samostatně schválená privátní integrace, zálohy, import a akceptace dat |

Primární agent vlastní writer slot i procesní ledger. Žádní dva writeři
současně; žádné delegování bezpečnosti, nových veřejných/persistovaných kontraktů
nebo datových rizik na nižší profil. Doporučená execution je přímé provedení
na high s jedním nezávislým review společného relevantního diffu po CI důkazech.
Volba subagent-driven nemění tato routing ani review omezení.

Každá implementační jednotka má nejvýše **2 pokusy celkem**, včetně oprav z review.
Před začátkem: owner/session, číslo pokusu, scope, approval a příkazy do lokálního
`docs/superpowers/WORKLOG.md`. Integrační nález se účtuje původní jednotce,
nikoliv jako nový rozpočet Task 4. Alpine → Debian je viditelný druhý pokus,
ne skrytá nová strategie. Po jeho neúspěchu nebo další nutné opravě STOP/BLOCKED.
Account/quota/permission/infra/unsupported znamená okamžitý STOP bez retry
nebo model fallbacku; pokračování jen po odstranění příčiny a výslovném pokynu.
Očekávané TDD RED a explicitní negativní test nejsou takové selhání.

Publikované důkazy obsahují jen syntetické údaje. `artifacts/`, `.venv/`,
`graphify-out/` a lokální ledger se necommitují. Před commitem kontrolovat přesný
staged diff; nikdy hromadné přidání celého checkoutu. Po změnách kódu spustit
`graphify update .`; graph je lokální odvozený výstup, nikoliv acceptance důkaz.

### Konkrétní rozhodnutí pro implementaci

- První chart verze `0.1.0`, `appVersion: "2.1.1"`, image tag `2.1.1-r1`;
  první Git release tag `v0.1.0`. Chart SemVer se dále neodvozuje z OSCAR verze.
- `versions.lock.json` bude mít literální immutable digests pro zvolený
  multiarch Selkies základ, platformní manifesty, SHA256 zdrojového archivu
  a případných oficiálních `.deb`. Počáteční Alpine selector je `alpine324`;
  fallback selector `debiantrixie` s Debian13 Qt6 balíčky pro obě architektury.
- Digests/checksums se získají z konkrétních upstream metadat v Task 1 a zapíší
  **před prvním buildem**. Nikdy se nevymýšlejí ani neřeší přes `latest` při releasu.
- `ci/tools.lock.json` zaznamená přesné verze a hashe stažených nástrojů/schémat;
  Python 3.13 v CI, Playwright `1.64.1`, Helm `3.19.0` a `4.3.2`.
  Kind `0.33.0`; konkrétní node image digest a schema verze musí odpovídat
  ověřenému podporovanému node releasu tohoto kind, ne náhodnému latest.
- Python závislosti mají úplný hashovaný `requirements-ci.lock`.
  Nainstalovaný lokální Helm je `4.3.2`; žádný test Helm 3 se tím nepředstírá.
- Config/data/SD defaults mají `1Gi`/`5Gi`/`2Gi`, `ReadWriteOnce`,
  `storageClass: null`, `existingClaim: ""`; tyto velikosti nejsou tvrzením
  o potřebách konkrétních skutečných dat.
- `service.port: 3000`; `env: {PUID: "1000", PGID: "1000", TZ: "Etc/UTC"}`,
  `envFrom: []`, `imagePullSecrets: []`, `serviceAccount.create: true`.
  `envFrom` pouze odkazy na existující Secrets/ConfigMaps, nikoliv jejich obsah.
- Default resources requests CPU `250m`, memory `512Mi`; limits CPU `2`,
  memory `2Gi`. `/dev/shm` je paměťový emptyDir s `512Mi` limitem, není datový
  fallback; spotřeba se ověří smoke testem a není to doporučení pro PROD.
- Probes jsou nastavitelné objekty. Default TCP `http`: startup period 5 s,
  timeout 3 s, failureThreshold 60; readiness 10/3/3; liveness 30/3/3.
  Zjišťují dostupnost serveru, nenahrazují GUI ani app-state test.

## File structure a společná testovací rozhraní

- `Dockerfile`, `.dockerignore`, `versions.lock.json`: jediná podporovaná
  build varianta a její immutable vstupy.
- `root/defaults/autostart_wayland`, `root/usr/local/bin/oscar-start`:
  base-compatible autostart a předání pevného datadir bez vlastní migrace.
- `ci/build_image.py`, `ci/runtime.py`, `ci/gui.py`, `ci/source_bundle.py`:
  OCI build, životní cyklus izolovaného kontejneru, browser/Qt flow, zdroje.
- `ci/tools.lock.json`, `requirements-ci.lock`, `pyproject.toml`: připnuté testy.
- `tests/image/`, `tests/runtime/`, `tests/chart/`, `tests/ci/`:
  kontrakty, aplikační runtime, chart matice, release/security gate.
- `ci/chart.py`, `ci/kubernetes.py`, `ci/check.py`, `ci/release.py`:
  chart ověření, explicitně izolovaný cluster test, společný lint, release.
- `charts/oscar/{Chart.yaml,values.yaml,values.schema.json,.helmignore}`,
  `templates/{_helpers.tpl,deployment.yaml,service.yaml,serviceaccount.yaml,pvc.yaml,ingress.yaml,httproute.yaml,NOTES.txt}`.
- `LICENSE`, `NOTICE.md`, `README.md`, `docs/{container,chart,migration,releasing,acceptance}.md`:
  licence/původ, instalace, provoz a skutečný stav ověření.

Veškerá CLI níže vracejí exit 0 jen při úspěchu, jinak nenulový exit.
Evidence JSON má `schemaVersion: 1`, `gitCommit`, `dirtyDiffSha256`,
`command`, `cwd`, `exitCode`, `platform` a explicitní výsledky kontrol;
release vyžaduje čistý přesný Git commit a odpovídající artefaktové digests.
Dirty identita zahrnuje i nové neignorované soubory: SHA256 kanonického
seznamu relativních cest a obsahových SHA256, nikoliv jen tracked `git diff`.
Runtime receipts navíc identifikují OCI manifest/config digest, ne jen image tag.
Odvozené přesuny image mezi OCI a Docker se kontrolují přes config/layer identitu.
Native artefakty mají adresáře `artifacts/native/<arch>/`, Helm receipts
`artifacts/chart/helm-<version>/chart.json`, zdroje `artifacts/sources/`.
Statická sada `ci/check.py` spouští `tests/image`, `tests/chart`, `tests/ci`;
`tests/runtime` se skutečně vykonají v native jobech, ne jako tiché static skips.

### Task 1 / IMAGE-01: Image, aplikace, native runtime a licence

**Files:** Vytvořit `Dockerfile`, `.dockerignore`, `.gitignore`,
`versions.lock.json`, `root/defaults/autostart_wayland`,
`root/usr/local/bin/oscar-start`, `ci/__init__.py`, `ci/build_image.py`,
`ci/runtime.py`, `ci/gui.py`, `ci/source_bundle.py`, `ci/tools.lock.json`,
`requirements-ci.lock`, `pyproject.toml`, `tests/image/`, `tests/runtime/`,
`LICENSE`, `NOTICE.md`, `README.md`, `docs/container.md`, `docs/migration.md`.

**Interfaces:**
- Consumes: schválený spec, upstream source commit a oficiální checksumy.
- Produces: `python3 -m ci.build_image --arch {amd64,arm64} --out-dir DIR`;
  soubory `image-<arch>.oci.tar`, `build-<arch>.json` a importovaný Docker
  test image `oscar-under-test:<arch>` se stejným config/layer obsahem.
- Produces: `python3 -m ci.runtime --image REF --arch ARCH --run-id ID --artifacts DIR`;
  receipt `runtime-<arch>.json`, screenshoty/traces/logy pouze syntetického běhu.
- Produces: `ci.gui.exercise(page, phase: str, profile: str, artifacts: Path) -> dict`,
  kde phase je `create` nebo `verify` a vrácený dict popisuje GUI checkpointy.
- Produces: `python3 -m ci.source_bundle --out-dir artifacts/sources`;
  archive odpovídajícího OSCAR source, build/patch/licence podklady a origin manifest.

- [ ] **1. Založit pouze lokální projekt a RED kontrakty.** Po kontrole aktuálního
  stromu inicializovat skutečný projekt `git init -b main` (nikoliv rollback
  mechanismus); existující procesní dokumenty zachovat. `.gitignore` nejprve vyloučí
  ledger, credentials, runtime artefakty a graph. Syntetické testy:

  ```python
  def test_locked_inputs(lock):
      assert lock["oscar"]["version"] == "2.1.1"
      assert lock["oscar"]["commit"] == "4f14624616d62c6986788417bc5c519c807a7ade"
      assert set(lock["platforms"]) == {"linux/amd64", "linux/arm64"}
      assert valid_immutable_digests_and_checksums(lock)

  def test_launcher_contract():
      assert captured_launcher_args() == [
          "--legacy", "--datadir", "/config/Documents/OSCAR20_Data"
      ]
      assert no_legacy_copy_import_or_conversion_in_startup()
  ```

  Dále `test_source_bundle_matches_lock`, `test_license_and_notices`,
  `test_default_hardening`, `test_build_rejects_foreign_native_arch`:
  konkrétní GPL text, upstream notices, Wayland/RESTART_APP/HARDEN_DESKTOP,
  absence VNC/socket/privileged, zákaz tichého emulovaného native testu.
  Pomocné funkce patří do `tests/image/conftest.py`, ne do product API:
  fixture `lock() -> dict`, `captured_launcher_args() -> list[str]`,
  `valid_immutable_digests_and_checksums(lock: dict) -> bool`,
  `no_legacy_copy_import_or_conversion_in_startup() -> bool`.
  Launcher test používá falešný OSCAR binární soubor zachycující argv, nikoliv GUI.
  Před product implementací zároveň zapsat native assertions
  `test_gui_and_stream`, `test_application_state_survives_recreation`,
  `test_application_restarts_after_close`, `test_sdcard_read_only`,
  `test_import_dialog_under_hardening`, `test_no_ephemeral_fallback`.
- [ ] **2. Ověřit RED.** `python3 -m pytest tests/image -q` musí selhat na dosud
  chybějících kontraktech, nikoliv na chybě prostředí. Testovací dependencies
  připnout a instalovat do lokální `.venv`, bez změn systémového Pythonu.
- [ ] **3. Zapsat ověřené vstupy a sestavit Alpine implementaci.** Ověřit metadata
  `alpine324`, source commit/archive a license. Zdrojový build má oddělený builder
  a runtime; qmake Qt6 moduly podle `oscar/oscar.pro`, runtime včetně Qt SQL SQLite,
  Wayland pluginu, fontů a překladů. Žádný vývojový HEAD ani nedoložené checksumy.
  Base init ponechat. `oscar-start` spustí OSCAR20 s výše testovanými argumenty,
  správným HOME/XDG pod `/config`; neimituje profil ani nepřepisuje staré Qt
  nastavení. Autostart musí zůstat kompatibilní s base watchdogem.
- [ ] **4. Implementovat jednoznačný build a source bundle.**
  `build_image.py` odmítne foreign native arch před buildem; používá vlastní
  pojmenovaný Buildx docker-container builder, `--platform linux/<arch>`,
  `--provenance=false` a `--output type=oci,dest=...`, bez registry push.
  Zdrojová provenance je samostatné metadata JSON; toto nastavení netvrdí
  existenci podepsané BuildKit attestation. Archiv obsahuje jeden platformní
  image manifest. K runtime importu použít Skopeo a ověřit identitu config/layers.
  Buildx docker-container používá privilegovaný infrastrukturní BuildKit
  kontejner: v tomto plánu pouze na disposable GitHub runneru. Lokální
  spuštění takového builderu vyžaduje další konkrétní souhlas, nikoliv
  automatické oprávnění z přítomnosti Docker CLI.
  Source bundle obsahuje přesný upstream archiv, aplikované patche i jejich
  nulový seznam, naše build skripty, checksumy a licence/origin metadata.
  U Debian fallbacku nesmí chybět zdroje/patches odpovídající skutečnému balíčku.
- [ ] **5. GREEN kontrakty.** `python3 -m pytest tests/image -q`, poté
  `python3 -m ci.build_image --arch arm64 --out-dir artifacts/native/arm64` na skutečně
  nativním ARM64 Linux builderu, analogicky AMD64 na AMD64. Lokální macOS ani
  přítomnost `docker` samy nedokazují dostupnost nativního Linux daemonu.
  Plné native příkazy zde definují gate; standardně je poprvé vykoná GitHub
  Task 3. Do té doby IMAGE-01 není finálně přijat.
- [ ] **6. RED skutečného runtime.** Dokončit harness assertions před laděním
  runtime integrace a prokázat očekávané RED proti samotnému připnutému base
  image bez OSCARu v native CI. Musí odhalit chybějící OSCAR GUI/profil,
  nikoliv jen kontrolovat nginx. Negativní probe dostane vlastní receipt,
  nesmí se započítat do pozitivní acceptance odvozené image.
- [ ] **7. Implementovat runtime/GUI harness.** Jedinečně pojmenované
  vlastní kontejnery a tři nové named volumes, vazba webu pouze `127.0.0.1`,
  žádné host data, socket mount, GPU ani privileged. Test použije PUID/PGID
  `1234:2345`, samostatný read-only SD vstup a softwarové vykreslování.
  Playwright Chromium na hostu otevře localhost secure context, zkontroluje
  skutečný streamovací WebSocket a jeho media frame provoz, obraz OSCARu a
  ovladatelnost GUI. Qt UI není DOM: GUI helper použije screenshot/OCR přes
  připnutý Tesseract při pevné velikosti 1280×800 a anglické locale; browser
  vstupy vytvářejí syntetický profil `ci-synthetic`, nikoliv upravenou DB fixture.
  Flow vybere startup jazyk `English` a ověří jeho uložení v Qt nastavení,
  po restartu nesmí znovu vynucovat volbu jazyka. Uzavře aplikaci čistě,
  zkontroluje obnovení watchdogem a otevření importního file dialogu.
  Po odstranění a **novém vytvoření kontejneru** nad stejnými volumes znovu
  přes GUI otevře stejný profil/jazyk, ověří zvlášť data a Qt config
  pod `/config`, UID/GID aplikačních souborů a read-only stav SD.
  Zaznamená screenshoty checkpointů, přijaté media frames, relativní cesty
  a integritu vytvořených SQLite databází read-only kontrolou.
  Nezapisovat do DB ani configu místo aplikace. Test read-only/nepoužitelného
  datového mountu musí odhalit problém bez založení náhradní ephemeral databáze.
  Timeout/selhání uloží vlastní logy a uklidí jen identifikované vlastní zdroje.
- [ ] **8. Spustit runtime a dokumentovat.**
  `python3 -m ci.runtime --image oscar-under-test:arm64 --arch arm64 --run-id image01-arm64 --artifacts artifacts/native/arm64`
  (na AMD64 odpovídající hodnoty). Zelená vyžaduje všechny checkpointy, ne skip.
  Dopsat container/security/backup/source dokumentaci, GPL-3.0-only text,
  attribution a bezpečný migrační checklist podle spec §9, bez skutečné migrace.
  Zdůraznit nested mounts, varování importeru a nepřípustnost připojení starých
  originálů nebo nahrazení starého releasu před samostatnou integrační ochranou.
- [ ] **9. Zkontrolovat změny a checkpoint commit.** `graphify update .`,
  přesný diff/test receipts do ledgeru; stage pouze soubory Task 1 a schválené
  procesní spec/plan po privacy kontrole. Commit `feat: package OSCAR with Selkies`.
  Případný Alpine blocker nejprve uzavřít v ledgeru; přechod na Debian až jako
  pokus 2 se stejnými kontrakty/testy a bez ponechání druhé varianty.

### Task 2 / CHART-01: Obecný chart a jeho end-to-end testy

**Files:** Vytvořit `charts/oscar/` s výše přesně uvedenými soubory,
`tests/chart/`, `ci/chart.py`, `ci/kubernetes.py`,
`tests/fixtures/kind.yaml`, `docs/chart.md`.

**Interfaces:**
- Consumes: image a datový/UID/security kontrakt Task 1.
- Produces: `helm install RELEASE charts/oscar -f VALUES`, bez závislostí.
- Produces: `python3 -m ci.chart --helm HELM_EXEC --out-dir DIR`:
  lint/render/schema matice a receipt `chart.json`.
- Produces: `python3 -m ci.kubernetes --kubeconfig FILE --context NAME --image REF --run-id ID --artifacts DIR`:
  izolovaný install/restart/uninstall test, receipt `kubernetes.json`.
  Skript cluster **nevytváří**; explicitní kubeconfig/context jsou povinné.

- [ ] **1. RED render/schema testy.** Přidat skutečné `helm template` testy
  parsující dokumenty, nikoliv substringy celého YAML. `test_defaults` očekává
  Deployment/Recreate/1/3×v2 PVC, ClusterIP a žádné Ingress/HTTPRoute;
  `test_route_matrix` testuje všechny čtyři kombinace. Další assertions:

  ```python
  def test_storage_class_three_states():
      assert "storageClassName" not in config_pvc(None)["spec"]
      assert config_pvc("")["spec"]["storageClassName"] == ""
      assert config_pvc("example-sc")["spec"]["storageClassName"] == "example-sc"

  def test_existing_claim_is_not_managed():
      docs = render_chart({"persistence": {"config": {"existingClaim": "external-config"}}})
      assert pvc_names(docs) == {
          "demo-oscar-data-v2", "demo-oscar-sdcard-v2"
      }
      assert config_claim_reference(docs) == "external-config"
  ```

  Helpers v `tests/chart/conftest.py`: `render_chart(values: dict,
  api_versions: tuple[str, ...] = ()) -> list[dict]` používá release `demo`,
  `config_pvc(storage_class: str | None) -> dict`,
  `pvc_names(docs: list[dict]) -> set[str]`,
  `config_claim_reference(docs: list[dict]) -> str`.
  Dále `test_digest_precedes_tag`, `test_gateway_api_detection`,
  `test_claim_names_long_release`, `test_security_and_mounts`,
  `test_extra_pvc_mounts`, `test_reject_invalid_values`.
  Negativní vstupy: replicas 0/2, invalid tag/digest formát, prázdné repository,
  prázdná required storage velikost, chybějící host/parentRefs u zapnuté route,
  neplatné typy env/probes a kolidující/nesprávný extra mount.
  `python3 -m pytest tests/chart -q` musí nyní skončit očekávaným RED.
- [ ] **2. Implementovat defaults/schema/šablony.** API properties spec §5 a
  konkrétních rozhodnutí výše; `nameOverride`, `fullnameOverride`,
  `serviceAccount.{create,name}`, `env`, `envFrom`, scheduling a configurable
  probe objects. `image.digest` buď prázdný nebo `sha256:<64 hex>`.
  `storageClass` string/null bez `default` přepisujícího prázdný string.
  Každá persistence má `size`, `accessModes`, `storageClass`, `existingClaim`;
  není přepínač pro nechtěné vypnutí persistence. PVC keep annotation;
  external claim nevytvářet. Fullname zkrátit **před** přidáním role/v2 suffixu,
  aby názvy zůstaly odlišné a vešly se do 63 znaků.
  `extraPvcMounts: []` přijímá jen name/claimName/mountPath/readOnly:
  `/imports/<bezpečný-podadresář>`, bez `..`, bez překrytí aplikačních mountů;
  není univerzální escape pro hostPath. Explicitní `readOnly` default true.
  `allowPrivilegeEscalation: false`, token false, app/base vyžadované
  capabilities neodhadovat slepě; finální sada musí projít runtime i K8s testem.
- [ ] **3. Implementovat obě routy.** Ingress v1: className/annotations/hosts
  s path/pathType/TLS. HTTPRoute v1: parentRefs/hostnames/path; žádný Gateway
  nebo CRD. Zapnutý HTTPRoute vyžaduje
  `.Capabilities.APIVersions.Has "gateway.networking.k8s.io/v1/HTTPRoute"`,
  jinak `fail` s konkrétním vysvětlením; vypnutý netestuje tuto capability.
  Test renderu zapnuté route předá přesné `--api-versions`.
  Obě routy odkazují na stejný pojmenovaný Service port.
- [ ] **4. GREEN matice.** `python3 -m ci.chart --helm helm --out-dir artifacts/chart/helm-4.3.2`;
  script spustí pytest/render/lint i kubeconform strict se staženými a
  checksum-připnutými K8s a HTTPRoute schématy. Nikdy globální
  `-ignore-missing-schemas`; clusterové capability není náhrada schema testu.
  Zopakovat se samostatně připnutými Helm 3 a 4 v CI.
- [ ] **5. RED/implementace izolovaného K8s smoke.** Testy `test_fresh_install`,
  `test_application_survives_pod_replacement`, `test_uninstall_preserves_claims`,
  `test_reinstall_with_existing_claims`, `test_refuse_ambient_kubeconfig`.
  Skript odmítne implicitní context, nesouhlas explicitního run-id/contextu
  nebo chybějící značku vlastního CI clusteru. Žádný fallback na `~/.kube/config`.
  Nejprve instalace defaults **bez Gateway CRD**, pouze s override lokálního
  test image REF a `pullPolicy: Never` po `kind load`, žádný registry fallback;
  bound PVC a Ready pod,
  přes lokální port-forward Task 1 GUI helper vytvoří profil, pod se nahradí
  a profil zůstane. Potom uninstall: tři PVC stále existují; čerstvý release
  s explicitními existingClaim je znovu připojí bez převzetí/změny jejich
  vlastnictví a po svém uninstall je nezruší.
  Teprve poté instalovat do CI clusteru připnuté upstream Gateway API CRD
  z `ci/tools.lock.json`, ověřit instalaci s gateway i ingress manifesty
  a zachování druhé route při vypnutí první. Nečekat přenos média přes
  neexistující controller: datový přenos se testuje port-forwardem; skutečná
  produkční route/controller zůstává integrační acceptance.
- [ ] **6. GREEN v izolovaném clusteru.** Příkaz
  `python3 -m ci.kubernetes --kubeconfig artifacts/kubeconfig --context kind-oscar-ci-RUNID --image oscar-under-test:ARCH --run-id RUNID --artifacts artifacts/native/ARCH`.
  `RUNID` a `ARCH` dodá konkrétní CI run; žádný příkaz proti produkci.
  První úplné provedení v Task 3, pokud lokálně není výslovně schválený izolovaný
  cluster; bez něho se schema/render testy nesmějí označit jako deployment PASS.
- [ ] **7. Dokumentace a checkpoint commit.** `docs/chart.md` obsahuje generické
  příklady obou route bez PROD, controller-specific WebSocket/timeouts/HTTPS
  předpoklady, digest pin, Secret refs, PVC backup/uninstall/re-adoption.
  Zdůrazní zachované orphan PVC a explicitní existingClaim jako bezpečnou
  cestu opětovného použití; neautomatizuje přebírání cizího vlastnictví.
  `graphify update .`, kontrola konkrétního diffu a commit
  `feat: add portable OSCAR Helm chart`.

### Task 3 / CI-01: GitHub testy a bezpečná release pipeline

**Files:** Vytvořit `.github/workflows/{ci.yaml,release.yaml}`,
`ci/check.py`, `ci/release.py`, `tests/ci/`,
`docs/releasing.md`, `docs/acceptance.md`; doplnit `README.md`.
`ci/tools.lock.json` smí doplnit piny deklarovaných release nástrojů.
Používat již definované nástroje/kontrakty, nevytvářet alternativní test stack.

**Interfaces:**
- Consumes: build/runtime/chart/K8s/source CLI a receipts z Tasks 1–2.
- Produces: `python3 -m ci.check`, společná lint/kontrakt/schema sada.
- Produces: `python3 -m ci.release verify --artifacts DIR --commit SHA` bez publikace;
  `python3 -m ci.release publish --artifacts DIR --commit SHA --registry ghcr.io/frisbeecz`;
  `python3 -m ci.release verify-published --release-manifest FILE`.
- Produces: `release-manifest.json` s image index + platform manifest/config
  digests, chart version/digest, source checksums a konkrétními GitHub run URLs.

- [ ] **1. RED workflow/release policy testy.** `test_no_privileged_pr`,
  `test_actions_sha_pinned`, `test_minimal_job_permissions`,
  `test_release_dependency_closure`, `test_reject_mismatched_receipt`,
  `test_refuse_dirty_or_wrong_commit`, `test_publication_inputs_are_data`.
  Parse YAML do AST a ověřit dependency graf, nikoliv existenci slova `needs`.
  Tamper archive hash, jiný commit/platforma, chybějící runtime/K8s receipt,
  skipped/failed job a alpha OSCAR verze musí odmítnout publish před prvním zápisem.
  Untrusted branch/tag/title se nevkládají jako shell source. Spustit
  `python3 -m pytest tests/ci -q`, očekávat chybějící gate/workflow RED.
- [ ] **2. Implementovat společné kontroly.** `ci/check.py`: actionlint,
  yamllint, hadolint, shellcheck, Python lint/pytest a chart matice, se
  skutečnou detekcí souborů a zákazem tichých skipů. Nástroje a Actions SHA
  ověřit z upstream vydání, zapsat literal piny; žádné neověřené fiktivní SHA.
  Lock změny pouze jako doplnění deklarovaných release nástrojů, ne přepis
  přijatého image/chart kontraktu bez účtování původní jednotce.
- [ ] **3. Implementovat `ci.yaml`.** `pull_request` a push main, top-level
  `contents: read`, žádné PR secrets/registry login/publish. Statické kontroly,
  checkout s `persist-credentials: false`, artefakty jen z konkrétního runu.
  Helm 3/4 matice a native build/runtime matice:
  `amd64 → ubuntu-24.04`, `arm64 → ubuntu-24.04-arm`. Host arch ověřit,
  nepřidávat QEMU jako náhradu native gate. Každý native job vyrobí OCI,
  runtime receipt a zdroje; upload až po důkazech, diagnostika `always`
  nesmí obsahovat secrets. Build/test skripty stejné jako lokálně.
- [ ] **4. Přidat skutečné K8s testy do native CI.** Na každém disposable
  GitHub runneru vznikne **vlastní** kind cluster s explicitním kubeconfigem,
  image z předchozího buildu se načte bez rebuild; použije se Task 2 CLI.
  Pozor: kind vytváří privileged node kontejner, podobně jako Buildx
  docker-container builder používá privilegovaný BuildKit kontejner.
  Schválení tohoto plánu se žádá i pro tyto úzce vymezené infrastrukturní běhy na
  jednorázovém GitHub runneru; OSCAR workload privilegovaný není.
  Žádný takový bootstrap na lokálním stroji bez dalšího výslovného souhlasu.
  Úklid jen vlastního clusteru v `always`; žádný globální prune/reset/restart.
  Kubeconfig se nepublikuje a testy nemají přístup do homelabu.
- [ ] **5. Implementovat `release.yaml`.** Push verzovaného tagu `v0.1.0`
  (další pouze validní projektové SemVer); všechny gates znovu nad přesným
  tag commitem: statické/Helm/native/runtime/K8s/source. Nepoužívat předchozí
  nepřiřazené workflow artefakty ani registry push v build/test jobech.
  Jeden publish gate `needs` všech povinných úspěšných výsledků, žádné
  `continue-on-error`/povolující `always`. Stažení přesných artefaktů tohoto
  runu, ověření receipts/checksums a commit před `packages: write`.
  Neprovádět checkout/build nedůvěryhodného PR v publikačním kontextu.
- [ ] **6. Implementovat distribuci beze změny image.** Skopeo
  `copy --preserve-digests oci-archive:... docker://...` pro obě otestované
  platformy, potom manifest index z těchto digestů přes Buildx imagetools.
  Nepřepočítávat vrstvy ani znovu buildit při nemožnosti zachovat digest.
  Publikovat `2.1.1-r1`, OCI chart `oci://ghcr.io/frisbeecz/charts/oscar`
  verze `0.1.0`, source bundle a release manifest.
  Chart se před push balí/lintuje/renderuje a testuje ve stejné verzované
  podobě; po testu se nesmí měnit defaults tag ani přepisovat tarball.
  `GITHUB_TOKEN` jen s job-scoped `packages: write`, pro GitHub release
  `contents: write`; žádná změna account nastavení/token scope jako workaround.
  Zdrojové podklady musí být přístupné současně s první distribucí binárek:
  před image upload připravit veřejný prerelease s ověřenými source assets,
  finální release označit až po ověření všech artefaktů. Nejde o záruku
  atomické transakce GitHub/GHCR; částečný síťový publish je blocker, ne PASS.
- [ ] **7. GREEN lokální policy testy.** `python3 -m pytest tests/ci -q`;
  `python3 -m ci.check`; `python3 -m ci.release verify --artifacts artifacts --commit "$(git rev-parse HEAD)"`.
  Poslední příkaz může být plně úspěšný až s receipts přesného čistého commitu
  z GitHub; lokální neúplná evidence musí být čitelně odmítnuta, ne přeskočena.
  `graphify update .`, privacy/staged kontrola, commit
  `ci: verify and release native OSCAR artifacts`.
- [ ] **8. Založit a ověřit skutečný GitHub projekt.** Ověřit aktuální identitu
  a jednoznačně nepřítomný cíl; existující cíl bez jasného vlastnictví znamená
  STOP/otázku, ne přepis. Po privacy kontrole
  `gh repo create frisbeecz/docker-oscar --public --source . --remote origin --push`.
  Vyčkat na skutečné běhy pomocí `gh run watch RUN_ID --exit-status`, uložit
  run URLs a SHA. Žádné přenastavování Actions permissions, branch protection,
  package visibility, runner billing nebo secrets bez zvláštního souhlasu.
  Nedostupný ARM runner/publish oprávnění znamená STOP, ne AMD64-only release.

### Task 4: Nezávislé review, ověřený release a předání

Tato část není nová implementační jednotka ani nový rozpočet oprav.
Owner primary; write jen acceptance dokumentace/ledger a schválené git
tag/publication operace. Žádný přístup do privátního repozitáře nebo produkce.

- [ ] **1. Sestavit skutečný relevantní diff a evidence před review.**
  Pro první root commit použít `git diff-tree --root --no-commit-id -r -p SHA`,
  pro celý projekt přesný kumulativní diff včetně nových testů/souborů.
  Reviewer dostane spec/plan acceptance, konkrétní Git SHA/tree, diff,
  příkazy/cwd/exity, nativní platformy, artifact digests a úspěšné run URLs.
  Nedávat jen self-report implementera. Neukládat velký diff do veřejného repa.
- [ ] **2. Jedno read-only `coding-review` acceptance i quality.** Bez shellu,
  bez zápisu/testování/delegace. Jeden společný initial review pro IMAGE-01,
  CHART-01 a CI-01, bez duplicitního whole-branch review později.
  Chybějící významné důkazy nejsou PASS. Případná oprava je pokus 2 původní
  jednotky na high; pak odpovídající nové testy a nejvýše jedno scoped
  re-review. Vyčerpané pokusy nebo neúspěšná závěrečná verifikace = BLOCKED,
  nikoliv další skryté kolo.
- [ ] **3. Uzavřít předrelease acceptance a verzi.** Jen po PASS a skutečně
  úspěšném CI finálního commitu: zkontrolovat čistý tree, release metadata,
  source/license completeness a anonymitu artefaktů; `git tag v0.1.0`,
  `git push origin v0.1.0`. Žádný rebuild mimo definovanou testovanou pipeline,
  žádná ruční publikace obcházející gate. Release workflow provede své
  povinné testy nad tagem a publikuje až po jejich úspěchu.
- [ ] **4. Ověřit pull, nikoliv jen push.**
  `python3 -m ci.release verify-published --release-manifest artifacts/release-manifest.json`:
  anonymous registry inspect/pull indexu i obou platforem a porovnání digestů,
  `helm pull oci://ghcr.io/frisbeecz/charts/oscar --version 0.1.0`,
  porovnání chart digestu a zdrojových checksumů/licencí. Pokud se package
  automaticky nestane veřejným, STOP a požádat o konkrétní schválení změny
  visibility; neměnit account/permissions potají.
- [ ] **5. Zapsat finální stav a předat.** `docs/acceptance.md` zaznamená
  image/chart/source identity a run URLs; změna pouze evidence dokumentace
  má vlastní odkaz na skutečný otestovaný release commit a nepředstírá,
  že pozdější doc commit už prošel GitHubem. Pokud se doc commit publikuje,
  vyžádat i jeho běžný CI výsledek bez nového vydávání binárek.
  Předat repo/release/OCI odkazy, licenční podklady, použité OS řešení a
  případné doložené omezení Alpine. Označit privátní PROD values, skutečný
  controller routing a zachování reálných profilů za **dosud neprovedené**.
  Vyžádat samostatné schválení INTEGRATE-01; žádný automatický navazující PR.

## Self-review tohoto plánu

- Spec §1–4 → Task 1 + native CI a pull identity; Alpine není předem prohlášen za funkční.
- Spec §5 → Task 2 včetně v1 route API, storage tri-state, long names a retention.
- Spec §6 → Tasks 1–3: hardening/import dialog, init versus app UID, explicitní test context a minimální CI oprávnění.
- Spec §7 → Task 3 + Task 4: skutečné GitHub běhy, přesné artefakty, veřejný pull a source distribuce.
- Spec §8 → Task 1 source/license bundle + Task 3 release podklady.
- Spec §9 → Task 1 migrační dokumentace; skutečné operace zůstávají mimo scope.
- Spec §10–12 → Task 4 evidence/review; dva pokusy, žádné neověřené PASS.
- CLI names, mount paths, version/tag a receipt identity jsou mezi Tasks 1–4 jednotné.
- Pět Review Focus vstupů má pojmenované owning testy; žádný univerzální controller ani právní/Alpine/runtime výsledek se nepředjímá.
- Tento dokument je plán. Dosud neproběhl product build/test, GitHub run, release ani migrace.
