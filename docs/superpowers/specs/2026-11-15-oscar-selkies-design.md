# OSCAR se Selkies: image, Helm chart a GitHub Actions

Datum: 2026-11-15

Stav: specifikace k uživatelskému schválení. Konverzační návrh obou částí byl
schválen; tento dokument ještě není schválením implementace.

## 1. Cíl a kritéria úspěchu

Vytvořit nový, samostatný veřejný projekt pro provoz oficiálního OSCARu
v kontejneru a Kubernetes. Nejde o fork ani o přepis samotného OSCARu.
Původní docker-oscar slouží jen jako reference.

Výsledkem budou:

- image s aktuálním stabilním OSCARem a Selkies místo VNC;
- podpora Linux AMD64 a ARM64;
- obecný Helm chart s výchozími values, podporující Ingress i Gateway API;
- GitHub Actions pro kontroly, testy, sestavení a publikování;
- licence, attribution, zdroje a dokumentace instalace a bezpečného přechodu.

Alpine je preferovaná platforma, nikoliv nepřekročitelná podmínka.
Zachování stávajících profilů a historie je závazná podmínka pozdějšího přechodu.
Samotné úspěšné sestavení image není důkazem zachování dat.

## 2. Rozdělení repozitářů a hranice práce

### Nový veřejný projekt

Navržený název je `frisbeecz/docker-oscar`, image
`ghcr.io/frisbeecz/docker-oscar`. Vznikne až po schválení této specifikace,
implementačního plánu a způsobu provedení.

Veřejný projekt obsahuje Dockerfile a spouštěcí konfiguraci, chart
`charts/oscar`, testy, workflow, dokumentaci a licenční soubory.
Nebude obsahovat přizpůsobené PROD values, zdravotní data, zálohy,
interní domény, identifikátory infrastruktury ani secrets.
Lokální pracovní ledger se při publikaci nesmí automaticky přidat bez
kontroly a odstranění informací z privátního repozitáře.

### Pozdější samostatná integrace

Úprava existujícího chartu a skutečné PROD values patří výhradně do
privátního `frisbeecz/homelab-helm-chart`.
Tento krok má samostatné schválení a ověření. Vytvoření jeho PR může
spustit GitOps automatizaci, proto se před změnou ověří způsob synchronizace.

Tato fáze nezahrnuje přístup ke zdravotním datům, deployment do produkce,
spuštění migrace, změny autentizace ani přenastavení clusteru.

## 3. Zvolené řešení a alternativy

Základem bude udržovaná image LinuxServer Selkies s Wayland desktopem.
Nebudeme znovu implementovat vzdálenou plochu, kodeky ani její init systém.

Preferovaná varianta kombinuje Alpine Selkies a vlastní sestavení oficiálních
zdrojů OSCARu s Qt6. Nabízí Alpine základ, ale vyžaduje ověření závislostí
a runtime chování na obou architekturách.

Schválenou alternativou je Debian Selkies a oficiální OSCAR balíčky
pro odpovídající distribuci a architekturu, ověřené oficiálními kontrolními
součty. Tato varianta snižuje vlastní build integraci.

Nejprve se prověří Alpine. Pokud narazí na zásadní nekompatibilitu nebo
neprojde runtime ověřením, zaznamená se konkrétní příčina a použije se
Debian alternativa. Nepovedeme dvě trvale udržované varianty.
Změna strategie musí být viditelná v ledgeru a respektovat limit pokusů;
není povolené neomezené přepínání a zkoušení nových řešení.

## 4. Kontejner a rozhraní aplikace

### Verze a reprodukovatelnost

Výchozím cílem je OSCAR 2.1.1, aktuální stabilní vydání ověřené
2026-11-15. Verze 2.2.0-alpha-1 není cílem.
Zdrojový tag 2.1.1 odpovídá commitu
`4f14624616d62c6986788417bc5c519c807a7ade`.

Verze OSCARu, zdrojový commit nebo checksum balíčku, base image digest
a revize našeho projektu budou dohledatelné v build konfiguraci a metadatech.
Release nepoužije nepřipnutý vývojový HEAD ani tichý download „latest“.
Image tag rozliší verzi OSCARu a revizi balení; chart má vlastní SemVer.

### Spuštění a komunikace

- Init a Selkies služby poskytuje base image; OSCAR se automaticky spustí
  a po ukončení se znovu otevře.
- Výchozí provoz nevyžaduje GPU; ověří se softwarové vykreslování.
- GUI poskytuje Selkies, nikoliv VNC či noVNC.
- Service a proxy používají HTTP port 3000 uvnitř clusteru.
- Prohlížeč musí k aplikaci přistupovat přes HTTPS, případně přes
  podporovaný lokální secure context při lokálním testování.
- Výchozí streaming používá WebSocket/WebCodecs. Povinné UDP porty,
  STUN ani TURN server nejsou součástí řešení.
- Provozní dokumentace vysvětlí rozdíl mezi tímto přenosem a volitelným
  Selkies WebRTC. Kompletní TURN/WebRTC infrastruktura není v rozsahu.

### Persistované cesty

| Účel | Cesta v kontejneru |
| --- | --- |
| Konfigurace a domov aplikace | `/config` |
| Nová data OSCAR 2.x | `/config/Documents/OSCAR20_Data` |
| Importní adresář SD karty | `/config/SDCARD` |

OSCAR dostane explicitní `--datadir` s novou datovou cestou.
Konfigurace musí zajistit, že související Qt nastavení skutečně přetrvá
pod `/config`; toto je součást runtime testu.
Oddělený datový mount je vnořený do config mountu: dokumentace proto
výslovně uvede, že samotná záloha config PVC nezálohuje data PVC.

Uživatelské UID, GID a časové pásmo budou nastavitelné přes podporované
konvence base image. Spouštěč ani init nesmějí kopírovat nebo převádět
staré profily do nového formátu.

## 5. Obecný Helm chart

### Workload a konfigurace

Chart obsahuje Deployment, ClusterIP Service, volitelné PVC, volitelný
Ingress a volitelný HTTPRoute, základní metadata a instalační poznámky.
Případný ServiceAccount nemá RBAC oprávnění a jeho token se do podu
automaticky nepřipojuje.

Podporované konfigurační oblasti:

- `image.repository`, `image.tag`, `image.digest`, `image.pullPolicy`
  a `imagePullSecrets`; zadaný digest má přednost před tagem;
- `replicaCount` povolující právě jednu instanci a strategie `Recreate`;
- kontejnerové proměnné a odkazy na existující Secrets bez hesel v defaults;
- resources, nodeSelector, tolerations a affinity;
- startup, readiness a liveness probes s nastavitelnými parametry;
- `persistence.config`, `persistence.data`, `persistence.sdcard`;
- `ingress.enabled` a `gateway.enabled`, obě standardně `false`.

Každá persistence podporuje chartem spravovaný PVC nebo `existingClaim`.
U spravovaného PVC lze nastavit velikost, accessModes a storage class.
Nové spravované claims používají jména `<fullname>-config-v2`,
`<fullname>-data-v2` a `<fullname>-sdcard-v2`, aby se neztotožnily
s původními claims stejnojmenného releasu. Jména jsou stabilní pro další
aktualizace této generace; existující claims se připojují jen explicitně.
Výchozí storage class není navázaná na konkrétního poskytovatele:
nezadaná hodnota použije cluster default; explicitní prázdná třída musí
být rozlišitelná od nezadané.
Výchozí provoz je persistentní; automatický ephemeral fallback není přípustný.
SD karta je standardně připojena pouze pro čtení, přepnutí je explicitní.
Spravované PVC mají ochranu před odstraněním při Helm uninstall a dokumentace
popíše důsledky pro následné opětovné převzetí releasem.
Cizí `existingClaim` chart nikdy nevytváří ani nemaže.

Bezpečné rozšíření pro jednorázový import může využít explicitně zadaný
další PVC mount. Není to automatická migrace ani defaultní hostPath.
Podpora dalších volume mountů nesmí vést k výchozímu připojení host disku
nebo Docker socketu.

### Ingress

`networking.k8s.io/v1`, konfigurovatelné ingressClassName, annotations,
hostnames, cesty a TLS odkazy.
Defaultní provoz používá kořenovou cestu `/`; libovolné přepisování cest
bez odpovídajícího nastavení aplikace není slíbenou funkcí.
Chart neinstaluje ingress controller ani cert-manager.

### Gateway API

`gateway.networking.k8s.io/v1` HTTPRoute s konfigurovatelnými parentRefs,
hostnames a kořenovou cestou ke stejné Service.
TLS ukončuje existující Gateway, kterou tento chart nevytváří.
Chart neinstaluje Gateway controller ani CRD.
Pokud je HTTPRoute vypnutý, instalace nesmí Gateway API vyžadovat.
Pokud je zapnutý a API v cílovém clusteru chybí, instalace musí selhat
s vysvětlením chybějícího předpokladu.
Ingress i HTTPRoute lze zapnout nezávisle; vypnutí jednoho nesmí
odstranit ani přenastavit druhý.

U obou variant dokumentace vysvětlí HTTPS, podporu WebSocket upgrade
a dlouhé timeouty. Controller-specific annotations či policies nastavuje
provozovatel; obecný chart je nebude vydávat za univerzálně přenositelné.

## 6. Bezpečnostní hranice

- Bez privileged režimu, hostNetwork a připojení Docker socketu.
- OSCAR běží pod aplikačním uživatelem. Init base image může potřebovat
  root pro nastavení vlastnictví; neslibujeme kompatibilitu
  s vynuceným `runAsNonRoot` nebo profilem Pod Security Restricted.
- Zakázat passwordless sudo a zbytečné desktopové spouštění příkazů
  podporovaným hardeningem Selkies. Potřebný import přes souborový dialog
  musí zůstat použitelný.
- Nepovolovat eskalaci oprávnění; konkrétní capabilities omezit podle
  ověřených potřeb init systému, nikoli obcházením privileged režimem.
- Ve výchozím stavu žádné veřejné vystavení ani zabudované heslo.
  Veřejný provoz vyžaduje HTTPS a autentizaci na proxy nebo existující
  secret-backed ochranu Selkies. Chart sám není identity provider.
- GitHub workflow ani testy nesmějí dostat produkční kubeconfig nebo přístup
  k produkčním datům. Dočasný kubeconfig izolovaného testovacího clusteru
  je přípustný. Secrets se neukládají do values, image ani logů.

Existující autentizace a její konkrétní nastavení se vyhodnotí teprve
při samostatně schvalované privátní integraci.

## 7. GitHub Actions a distribuce

### Kontroly PR a hlavní větve

- Validace workflow, YAML, Dockerfile a shell skriptů.
- Helm lint, renderovací regrese a schema validace Kubernetes objektů
  včetně HTTPRoute proti připnutým odpovídajícím schématům.
- Matice chartu: defaults bez obou vstupů, pouze Ingress, pouze Gateway,
  oba vstupy, existující claims, digest image a negativní neplatné hodnoty.
- Nativní build a runtime smoke test pro Linux AMD64 i ARM64,
  ne pouze sestavení pod emulací.
- Runtime test ověří proces OSCARu, služby Selkies, dostupnost webu,
  navázání streamovacího WebSocketu a skutečně dostupné GUI.
- Syntetický profil nebo ekvivalentní syntetický stav ověří nový datadir,
  zápis pod správným UID/GID a zachování stavu po restartu kontejneru.
  Pouhý soubor vytvořený mimo OSCAR se nepočítá za důkaz persistence aplikace.

Fork PR nedostávají publikační oprávnění ani secrets. Použije se
`pull_request`, nikoli privilegovaný běh nedůvěryhodného kódu přes
`pull_request_target`. Actions budou připnuté na plné commit SHA.

### Release

Verzovaný release spustí příslušné kontroly nad přesným releasovaným stavem.
Teprve po jejich úspěchu publikuje:

- image pro AMD64 a ARM64 a společný multiarch manifest do GHCR;
- zabalený verzovaný chart do GHCR jako OCI artifact;
- odpovídající zdrojový archiv OSCARu, build informace a licenční podklady.

Publikovaný image musí odpovídat otestovanému artefaktu, nikoli
neověřenému novému sestavení po testech. Release zaznamená image digest
a chart verzi; dokumentace ukáže jejich připnutí.
Zápisová oprávnění budou jen u publikačních jobů s `GITHUB_TOKEN`.
Workflow se nepřipojuje do homelabu a nic tam nenasazuje.

Pokud je runner nebo publikační oprávnění nedostupné, práce se nezamlčí
za úspěšný test. Výsledek uvede konkrétní blocker. Nastavení účtu,
placených služeb ani oprávnění se bez schválení nemění.

## 8. Licence a původ kódu

Nový kód projektu bude pod `GPL-3.0-only`; přiloží se plný text licence
a jednoznačné označení v metadatech a dokumentaci.
Jde o volbu pro náš kód, nikoli o přelicencování OSCARu, Qt, Selkies
nebo balíčků operačního systému.

Attribution uvede OSCAR Team, původ projektu SleepyHead a použitý Selkies
základ. Pokud se převezme kód z docker-oscar, zachová se jeho příslušná
licence a attribution; pouhá inspirace nevytvoří deklaraci forku.

Release bude poskytovat přesné použité zdroje OSCARu včetně případných
patchů, náš build kód a manifest původu distribuovaných komponent.
Dokumentace popíše zdrojové a licenční odkazy base image a balíčků;
samotná licence nového repozitáře nenahrazuje povinnosti jejich distribuce.

## 9. Zachování dat a pozdější přechod

OSCAR 1.x používá jiný datový formát než SQL databáze OSCAR 2.x.
Oficiální 2.1.1 obsahuje interaktivní import profilů z původního formátu.
Přepojení původního data PVC na novou cestu není migrace.

Nový chart se nesmí bez výslovného nastavení připojit ke starým PVC
jen shodou jména releasu. Před privátní integrací vznikne přesná mapa
starých a nových claims; první spuštění nové verze použije oddělené claims
nebo ověřené klony, nikoli původní produkční config/data PVC.
Recreate není náhrada této izolace.
Nová jména sama také nebrání tomu, aby Helm při nahrazení původního chartu
odstranil jeho staré PVC. Proto se před izolovaným ověřením a samostatným
schválením nesmí původní release aktualizovat novým chartem.
Privátní integrační plán musí nejprve ochránit původní spravované PVC
před odstraněním a ověřit vedlejší běh pod odlišným release jménem
bez převzetí produkčního routování.

Postup přechodu, který se nyní pouze dokumentuje:

1. Po samostatném schválení zjistit skutečný stav instalace a GitOps.
2. Zastavit zápisy staré aplikace a vytvořit konzistentní zálohu config,
   dat i vstupů SD karty. Ověřit obnovitelnost, nejen existenci snapshotu.
3. Ponechat originály a vytvořit izolovanou pracovní kopii se samostatnou
   konfigurací a novou datovou složkou. Zdrojový archiv zůstane neměnný.
4. Spustit novou aplikaci a provést podporovaný interaktivní import
   z pracovní kopie. Pokud importer potřebuje zápis do svého zdroje,
   dovolí se pouze do další zahoditelné kopie, nikdy do originálu.
5. Ověřit všechny profily a zařízení, časový rozsah historie, počty
   dnů a sessions, jejich enabled/disabled stav, poznámky/deník,
   dostupnost detailních grafů a reprezentativní nastavení.
   Porovnání zohlední pouze doložené změny reprezentace mezi verzemi.
6. Zkontrolovat varování importeru, integritu nové databáze a další
   restart nad novým PVC. Úspěšné dialogové hlášení samo nestačí:
   upstream importer některá selhání deníku nebo kopírování záloh
   zaznamená jen jako varování a pokračuje.
7. Teprve po akceptaci výsledku schválit přepnutí provozu.

Při neúplném importu se nepřepíná. Návrat znamená starou verzi se starou,
nedotčenou konfigurací a daty. Starý OSCAR se nesmí spouštět nad novou
SQL složkou. Případné nové zápisy po přepnutí vyžadují před návratem
samostatné rozhodnutí; nelze slíbit automatické sloučení obou historií.

## 10. Akceptace a požadované důkazy

| Oblast | Podmínka přijetí |
| --- | --- |
| Image | Obě architektury sestavené a nativně runtime ověřené, správná stabilní verze, GUI a streaming bez VNC |
| Persistence | Syntetický stav vytvořený aplikací přežije restart; config a data jsou odděleně dohledatelné |
| Chart | Lint/render/schema regrese v celé matici, negativní testy, žádná závislost na vypnutém Gateway API |
| Kubernetes | Smoke instalace a restart v neprodukčním clusteru s izolovanými daty; schema validace sama není deployment test |
| CI | Skutečné úspěšné GitHub běhy proti předávanému commitu; lokální kontroly se za ně nevydávají |
| Release | Pullnutelný multiarch image a OCI chart, dohledatelné digests/verze a zdrojové artefakty |
| Bezpečnost | Žádné výchozí veřejné vystavení, privileged/socket/hostPath ani secrets ve veřejných artefaktech |
| Licence | Licence nového kódu, attribution a zdroje odpovídající distribuované verzi |
| Data | Zdokumentovaný bezpečný postup; skutečná migrace a její akceptace jsou až samostatný privátní krok |

Pro testy se zaznamená příkaz, cwd, exit status a identita ověřeného stavu.
Pro GitHub se zaznamenají odkazy na konkrétní workflow runs.
Co nebylo provedeno nebo nebylo dostupné, bude uvedeno jako neověřené
či blokované, ne jako splněné.

Významné implementační změny projdou jedním nezávislým review acceptance
i kvality nad skutečným diffem a test evidence. Jednotky mají nejvýše
dva implementační pokusy; případná oprava review tento rozpočet nesmí obejít.

## 11. Mimo rozsah

- ARM32, VNC/noVNC, vlastní desktopový streaming stack.
- Více souběžných replik nad stejnou databází a autoscaling aplikace.
- Automatický převod produkčních dat v entrypointu, init containeru
  nebo Helm hooku.
- Převzetí nesouvisejících cron/ezShare importerů bez dalšího požadavku.
- Veřejné homelab PROD values, kubeconfigy nebo medicínské fixtures.
- Automatické nasazení do produkce, změny identity provideru
  a instalace placené infrastruktury.

## 12. Ověřené zdroje a omezení důkazů

- [Oficiální OSCAR download a stable verze](https://www.sleepfiles.com/OSCAR/)
- [Oficiální zdroje OSCAR 2.1.1](https://gitlab.com/CrimsonNape/OSCAR-SQL/-/tree/v2.1.1)
- [Zdroj importu profilů v 2.1.1](https://gitlab.com/CrimsonNape/OSCAR-SQL/-/blob/v2.1.1/oscar/profileimporter.cpp)
- [Argumenty a startup OSCARu v 2.1.1](https://gitlab.com/CrimsonNape/OSCAR-SQL/-/blob/v2.1.1/oscar/main.cpp)
- [Selkies base images](https://github.com/linuxserver/docker-baseimage-selkies)
- [Selkies reverse proxy](https://docs.linuxserver.io/selkies/user-guide/reverse-proxy/)
- [Původní návrh přechodu z VNC](https://github.com/rogerrum/docker-oscar/issues/43)
- [GitHub Actions runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [Publikace packages z Actions](https://docs.github.com/en/packages/learn-github-packages/publishing-a-package)

Ověřeno bylo čtení oficiálních zdrojů, dostupnost stabilní verze, existence
ARM64 i AMD64 balíčků a dokumentované vlastnosti Selkies.
Linux build návod v OSCAR repozitáři stále uvádí starší Qt5 závislosti:
nepovažujeme jej za ověření Qt6/Alpine.
Dosud neproběhl žádný build, runtime test, GitHub workflow, deployment
ani migrace. Proveditelnost Alpine a úplnost konkrétního importu se
teprve musí prokázat podle výše uvedených bran.
