## 19. 11. 2026 — SK + CZ, celé nové bouquety a všetky dostupné originálne logá

- **Výsledok úplného online zberu:** [GitHub Actions #44577435803 – full-slovak-czech SUCCESS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44577435803), commit [`9814b71`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/9814b7145c0fad1bf12b85baccdbc929f8fbf25a).
- **Slovensko:** kompletný bouquet **123/123** platných streamovaných staníc, original `WarderRadio.station_logos` PNG **111 úspešných** a **12 nedostupných** (pokus o všetkých 123).
- **Česko:** kompletný bouquet **229/229** platných staníc, PNG **202 úspešných** a **27 nedostupných** (pokus o všetkých 229).
- **Overenie skutočného artefaktu:** kompletný Actions ZIP 3 244 604 B má SHA-256 `6dafe590a8b751eac94f44f388e892ab67655b6e3395723b1a5ae716bdeb4045`. Z neho `logos/SK.zip` má **1 226 871 B**, 111 platných PNG, `bouquets/SK.radio` **15 635 B**; `logos/CZ.zip` **2 099 517 B**, 202 platných PNG, `bouquets/CZ.radio` **29 015 B**. Všetkých **313 PNG** otvorených a `Pillow.Image.verify()` PASS, bez poškodených obrázkov. Rozmery sú pôvodné/normalizované do limitu pluginu (nie tri prepracované grafické varianty).
- **Spolu:** **352 staníc**, **313 log**, **39 chýbajúcich log**. `catalogue_complete=true`, `logo_package_complete=true` (znamená všetky **pokusy**, nie že každá stanica má logo), SHA-256 kontrola country bouquetov, ZIP, manifestov a presných referencií PASS. [Review-only artifact #14556504575](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44577435803), GitHub artifact ZIP **3 244 604 B**, digest `sha256:6dafe590a8b751eac94f44f388e892ab67655b6e3395723b1a5ae716bdeb4045`.
- **Schválenie:** iba zdrojový pilot, nešlo o produkčné vydanie balíkov, dočasné artifacty sa nesmú zameniť za trvalé Release. Francúzsko zostáva overené ako **2476 kompletných staníc**, logá zatiaľ iba 6 z 8 skúšobných; Etiópia **22 staníc, 18 log**.
- **Ďalší krok:** vytvoriť ďalšie krajiny, zhromaždiť všetkých 224 kompletných country snapshotov, až potom schválené nemenné GitHub Release + `assets/radio-country/latest.json`. Zdrojovo má skin [PR #129](https://github.com/Evolution-by-Warder/FullHDGlass-Warder-Evolution/pull/129) lokálny world downloader, prvú krajinu z jazyka a per-country original ZIP; fyzicky neodskúšané. Pred verejnou redistribúciou log riešiť podmienky použitia pôvodných obrázkov.

---

## 19. 11. 2026 — Overený centrálny index s SHA-256 pre nový Radio Live

- **Zdroj:** výhradne aktuálny `WarderRadio.radio_browser.RadioBrowser` a `WarderRadio.station_logos.StationLogos` na pracovnej vetve PR [#52](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/52). Nijaký starý 6 741-staničný world bouquet sa neimportoval.
- **Jednotný distribučný formát:** kanonický generátor [`tools/assemble_country_radio_snapshots.py`](tools/assemble_country_radio_snapshots.py) pripravuje **jeden** `radio-countries-bouquets.zip` s lokálnymi `bouquets/CC.radio`, `catalog/CC.json`, `manifests/CC.json` a `index.json`. Logá **nie sú** vo svetovom archíve; každá krajina má samostatný `CC.zip` s presnými Enigma2 referenciami. Duplicitný experimentálny assembler `assemble_country_radio_snapshot.py` aj jeho test odstránené z vetvy, aby nevznikali dve súťažné formy balíka.
- **Centrálna aktualizácia:** [`tools/prepare_country_release_index.py`](tools/prepare_country_release_index.py) vytvorí `latest.json` so známym `radio-country-YYYYMMDD` tagom, SHA-256 a dĺžkami svetového ZIP aj každého `CC.zip`. Pred vydaním vyžaduje úplnosť inventára a úplné pokusy o získanie log. Review manifest zostáva `complete=false`, aby ho prijímač nemohol prevziať ako ostrý.
- **Overenie:** [CI #44571104153 PASS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44571104153): ET **22**, FR **2476**, spolu **2498** úplných staníc; len review logo ZIP-y (nie všetky logá). `radio-countries-bouquets.zip` **298 076 B**, SHA-256 `e9fc5b50b16148c0d029d90737a03329b7b052c8abcedd0e5b2f5a33b4ddd1d8`; sprievodný `latest.json` je úmyselne `complete=false`. Artefakt `warder-radio-world-initial-bouquets-REVIEW-NOT-PRODUCTION` #14554970483, GitHub overené SHA. 14-dňový workflow je draft; na pracovnej vetve nespúšťa plánovaný job.
- **Stav:** zdrojovo pripravený review builder a index. Kompletných **224 krajín/území s úplnými originálnymi logami NIE je hotových**. Chýba stabilné schválené GitHub release a publikované `assets/radio-country/latest.json`. Žiadna publikácia `main`, ostrý balík ani aktualizačný feed nebol zmenený. Pred verejnou distribúciou prevzatých log skontrolovať aj práva na ich ďalšie šírenie.

---

## 19. 11. 2026 — Prvý spoločný ZIP kompletných krajinských bouquetov

- **Nová úloha:** [`tools/assemble_country_radio_snapshots.py`](tools/assemble_country_radio_snapshots.py) vytvára jeden malý komprimovaný prvotný archív zo všetkých **kompletných** a kontrolnými súčtami SHA-256 overených krajín; zámerne neobsahuje žiadne PNG logá. Tie sú vždy samostatné country ZIP-y. Testy [`tests/test_country_snapshot_bundle.py`](tests/test_country_snapshot_bundle.py) overujú deterministické ZIP bajty, bezpečné názvy, úplné stanice, poškodený hash, neúplnú krajinu a ochranu cudzieho súboru. Commity [`6c73ff2`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/6c73ff2d05627d321a42c302ee3e4e3027bd8387), [`6809a56`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/6809a56dc297ce9c7721f44ffd46590a8ad6a940), [`a46b9da`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/a46b9da216c5f061fa52f0191eeaa93bfca26acf).
- **Dôkaz:** [world-sharded review CI #44567288502 – všetky 4 joby PASS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44567288502). Prvotný ZIP `radio-countries-bouquets.zip`, **298 076 B**, SHA-256 `e9fc5b50b16148c0d029d90737a03329b7b052c8abcedd0e5b2f5a33b4ddd1d8`. Obsahuje **ET 22 + FR 2476 = 2498 platných staníc** vrátane katalogových máp a manifestov. [Review artifact #14550809831](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44567288502) je vytvorený a checksum overený, stále **NOT PRODUCTION**. ZIP je vhodný len na funkčnú integráciu a testy, neobsahuje logá.
- **Rozsah:** full-world pipeline pripravená pre všetkých 224 kódov s matrix `max-parallel=4`, ale v aktuálnom PR automatické push spúšťa len dvojkrajinskú kontrolu. Úplné krajinské ZIP s originálnymi logami pre celých 224 krajín ešte **neboli** vytvorené. 14-dňový cron sa nespúšťa na pracovnej vetve a publikovanie do `main` či Release nebolo schválené.

---

## 19. 11. 2026 — Celosvetový inventár 224 kódov a samostatné balíky krajín

- **Autoritatívny zdroj:** stále výhradne `WarderRadio.radio_browser.RadioBrowser` a `WarderRadio.station_logos.StationLogos` na pracovnej vetve [PR #52](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/52). Nový live inventory `countrycodes` vracia **224 krajín a území** (zachované `available-countries.json` v ET review artefakte). Starý world bouquet nie je zdrojom.
- **Kompletné súpisy:** ET **22 staníc**, úplný PNG import **18 dostupných zo všetkých 22 pokusov**, [Actions PASS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44562666840). FR **2 476 platných staníc**, celý scan, len **8 testovaných log** (z nich 6 dostupných), [Actions PASS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44563769694). FR logo ZIP preto označený `logo_package_complete=false` — nesmie sa považovať za hotové vydanie.
- **Rozdelenie úloh:** `tools/build_country_radio_packages.py` podporuje oddelený úplný zber bouquetu cez `--catalogue-only` (ZIP má 0 PNG, `logo_package_complete=false`, teda nikdy falošný úspech log). Test `test_catalogue_only_world_pass_preserves_all_stations_but_no_logo_claims` doplnený. Commit [`546f22b`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/546f22b7495c3b416cadfa76f6b701acb2ce6f4d).
- **Hromadné spracovanie:** kandidát [`country-world-sharded-review.yml`](.github/workflows/country-world-sharded-review.yml) z [`63ea3cc`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/63ea3ccf460e7f8af2dc2ba9b2b301829917205f) vytvára samostatný job pre krajinu (`max-parallel=4`), na push kontrolné ET/FR, pri workflow_dispatch/cron `ALL`, každá krajina má manifest a SHA; [preview ET+FR CI PASS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44564734699). Cron `1.` a `15.` v mesiaci sa **nespúšťa na pracovnej vetve** a po schválení default merge začne pripravovať **iba review artefakty**, NIE produkčné vydania.
- **Zostáva:** úplné spracovanie všetkých 224 krajín vrátane paralelných originálnych log, výstupné signované manifesty a schválené publikovanie cez stabilné URL/Release, 14-dňový monitor aktuality a sprístupnenie v skine. Bez zmien `main` a stabilnej verzie; tento stav nie je celosvetový RELEASE.

---

## 19. 11. 2026 — nový Radio Browser country bouquet + originálne logá z pluginu (PR #52)

- **Zadanie:** Nepoužiť starý a chybný 6 741-staničný `userbouquet.warder.radio`. Namiesto neho všetky krajiny získavať rovnakým `WarderRadio.radio_browser.RadioBrowser` API ako samostatný plugin. Počas toho istého spracovania pripravovať jeden `CC.radio` a jeden `CC.zip` s rovnakými malými PNG, aké skutočne získava `WarderRadio.station_logos.StationLogos`. Žiadne čierne/biele štýly ani tri rozmery; presné priradenie na UUID-derived Enigma2 servisnú referenciu.
- **Pracovná vetva:** `feature/radio-browser-country-bouquets-and-logo-zips-20261119`, [draft PR #52](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/52). Generátor [`tools/build_country_radio_packages.py`](tools/build_country_radio_packages.py), testy [`tests/test_country_radio_packages.py`](tests/test_country_radio_packages.py), testovací workflow [`country-radio-snapshot-preview.yml`](.github/workflows/country-radio-snapshot-preview.yml).
- **Doložený test:** [GitHub Actions #44560765795 – oba jobs SUCCESS](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44560765795). Offline unit testy PASS. Skutočná online vzorka Radio Browser: ET = **22/22 staníc**, z 8 skúšobne spracovaných log dostupných **8/8**; FR = **60 záznamov (neúplný náhľad)**, z 8 pokusov **6 log dostupných, 2 chýbajúce**. Vytvorené `bouquets/ET.radio`, `bouquets/FR.radio`, `logos/ET.zip`, `logos/FR.zip`, JSON mapy, manifesty. Kontrola SHA-256 všetkých šiestich dátových súborov PASS (plus krajinské manifesty). [Review-only Actions artifact #14550615093](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/44560765795) má **361 747 B**, iba testovacie neúplné výstupy. Pri FR je `catalogue_complete=false`; pri oboch `logo_package_complete=false`.
- **Zámer publikácie:** po dokončení všetkých krajín a schválení publikovať hashované dátové balíky na GitHub po krajinách, kontrolovať raz približne za 14 dní. Skin z nich lokálne vytvorí rýchly výber krajiny a pri zmene krajiny načíta iba príslušný ZIP do `hdg17_files/picon/radio/`; súvisiaca spotreba, mazanie a GUI vyžadujú oddelenú ochranu, testy a schválenie. Workflow teraz **nepublikuje**, spúšťa len obmedzený online náhľad.
- **Čo ešte nie je hotové:** úplný inventár všetkých krajín, plné ZIP log pre všetky stanice, produkčná distribúcia, 14-dňový publikujúci workflow a klient v skine. Neprezentovať neúplnú skúšobnú sadu ako hotovú. **Žiadna zmena `main`, oficiálnej verzie Warder Radio ani feedu; žiadna IPK.**

---

# Radio Warder Evolution – stav stabilného vydania

## 0.2.0 Stable

Oficiálne stabilné vydanie: [warder-radio-v0.2.0](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/tag/warder-radio-v0.2.0).

Podporované funkcie: Radio Browser, Domov, Odbery, Obľúbené, História, vyhľadávanie, prehrávanie streamov, ICY metadáta, online logá staníc s obmedzenou cache, albumové obaly, texty piesní, informácie o interpretoch, nahrávanie, YouTube a OLED šetrič.

- Stabilná vetva `main` má verziu 0.2.0.
- Online logá sú priebežne získavané len pre relevantné viditeľné stanice.
- Používateľské dáta pod `/etc/enigma2/warder-radio` zostávajú zachované.
- Testy OpenATV 8.0, OpenATV 8.1 a OpenPLi 9.2 a aktualizácie pomocou opkg prešli pri vydaní.

Ďalšie zmeny nesmú bez výslovného schválenia upravovať stabilnú verziu ani vydávací kanál.
