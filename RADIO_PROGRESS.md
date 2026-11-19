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
