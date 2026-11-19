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
