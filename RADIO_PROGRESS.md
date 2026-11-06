# Warder Radio – register postupu

Aktualizované 6. 11. 2026. Register pokrýva samostatný plugin pre Enigma2 a jeho rádiové picony. Pravidlá odovzdania sú v [AGENTS.md](AGENTS.md).

## Overené východiská

| Oblasť | Vetva alebo vydanie | Posledný overený commit a stav |
| --- | --- | --- |
| Warder Radio | `main` | [`c988c30`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/c988c30f415eee0565a1365a5be986d36101cee5), zlúčenie dokumentácie. Posledný commit vydania na tejto vetve je [`349fd7e`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/349fd7ec25e3f7979cb28b8dab0ed5f3fbf2434b), publikácia testovacieho kanála. Aktuálne manifesty v2 pre stabilný aj testovací kanál uvádzajú [0.1.8](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/tag/warder-radio-v0.1.8). |
| Warder Radio 0.1.8 | Zdroj vydania | [`26225c0`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/26225c0d2a61d04663c1ed3d3cf083faa0d94305), zastavenie a obnovenie prehrávania pôvodnej stanice bez duplikovania histórie. [Záznam vydania](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/blob/349fd7ec25e3f7979cb28b8dab0ed5f3fbf2434b/docs/releases/radio-resume-0.1.8.json) uvádza 148 jednotkových testov a po 70 natívnych testov na OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next. Fyzický test 0.1.8 v zázname nie je. |
| Rádiový katalóg a živé balíky | PiconHub `main` | [`e90a1fe`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/e90a1fe3a2734b555f48f343284f9103530180fb), 40 903 servisných referencií v 219 krajinských skupinách a skupine HDF. |
| Svetový checkpoint 22 | PiconHub `work/radio-catalogue-strict-ocr-20261105` | [`4dd8220`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/4dd8220efc5180db9e0fca56335b4a01b9193558/migration/radio-reconciled-checkpoint-20261105/summary.json), 19 756 pripravených referencií a 177 804 PNG, z toho 19 706 referencií v hlavnom katalógu checkpointu. Evidovaných 21 197 nepokrytých referencií. Stav je pracovný. |
| Dávka 23 | PiconHub `work/warder-radio-world-batch23-20261106` | [`02aafea7`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/02aafea7e4e326aace955f72b6d20c68c7e45eba), 9 referencií a 81 PNG, pripravené v pracovnej vetve. |

## Pokrytie krajín

Živé inventáre všetkých deviatich variantov pokrývajú **464 presných referencií** z aktuálneho katalógu vrátane 14 zo skupiny HDF. Úplné pokrytie krajinskej skupiny je overené pre **Slovensko a Česko**. Súčet 338 nižšie vychádza z referencií v aktuálnych krajinských skupinách. Historický audit SK/CZ r6 uvádza 320 staníc a 358 súborov na variant podľa svojho rozsahu. [Audit r6](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/e90a1fe3a2734b555f48f343284f9103530180fb/reports/radio-country-quality-20261105.json)

| Krajina | Referencie v katalógu | Živé pokrytie | Stav |
| --- | ---: | ---: | --- |
| Slovensko | 89 | 89 | Úplné |
| Česko | 249 | 249 | Úplné |
| Rakúsko | 219 | 12 | Čiastočné |
| Nemecko | 3 422 | 64 | Čiastočné |
| Maďarsko | 237 | 11 | Čiastočné |
| Poľsko | 500 | 25 | Čiastočné |

[Prehľad všetkých skupín](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/02aafea7e4e326aace955f72b6d20c68c7e45eba/picons/radio-world/coverage.json) vedie živé pokrytie, dávku 23 a známe nevyriešené položky oddelene. Úplný inventár a ZIPy checkpointu 22 sa v dostupných podkladoch nepodarilo nájsť. Jedinečný súčet naprieč checkpointom a novou dávkou preto zostáva otvorený.

## Denník významných zmien

### 6. 11. 2026 – integrácia krajín a manifestov

- [Radio PR #15](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/15) pridáva Argentínu, Švédsko, Ukrajinu, Spojené kráľovstvo a USA s názvami vo všetkých 21 jazykoch. Nemecko využíva existujúci výber. Automatický rozmer v prijímači je 220×132. Kandidátske balíky obsahujú aj 50×30 a 400×240, každý v troch pozadiach.
- [PiconHub PR #64](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/pull/64) obsahuje šesť manifestov [`5829aca`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/5829aca2b1809d2945a9acc20d81dae30acfb10f) a 54 ZIPov v nemennom [commite `1707bdf`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/1707bdf858c9f831515d2be89d9d115280af8f6d). Overené spätným stiahnutím, SHA-256, CRC a SHA-256 každej PNG položky. V Nemecku je 91 súborov na variant, z toho 90 pôvodných s identickými PNG bajtmi.
- [CI pluginu](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42202245581) prešlo vrátane natívnych replayov OpenPLi a OpenATV. Lokálne prešlo 148 jednotkových testov, kontrola IPK a opakovaná inštalácia s reálnymi pracovnými manifestmi vo všetkých troch pozadiach. Test potvrdil zachovanie vlastného piconu a preskočenie ZIPov pri opakovaní. Fyzický prijímač nebol testovaný.
- Oba PR sú drafty. Po výslovnom schválení nasadiť balíky a overiť ich manifesty v `main`, potom zlúčiť plugin. Vydanie IPK má samostatné schválenie.

### 6. 11. 2026 – dávka 24

- [Pracovný manifest a dôkazy](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/5821c5e29c306c546cffb01a167b42fba27a42ee/picons/radio-world/staging/batch-24/manifest.json) obsahujú 16 presných referencií a 144 PNG. AR 1, DE 9, GB 1, US 5. Zaznamenaných je 30 neuzavretých kandidátov.
- Pôvodné podklady, deväť variantov a kontrolné súčty sú uložené na pracovnej vetve. Všetky ZIPy boli opätovne stiahnuté a overené. Pri Lyca Radio 1458 sú použité dve pôvodné verzie vysielateľa pre správnu čitateľnosť na rôznych pozadiach. Ďalší pracovný krok je zlúčenie dávky 24 do krajinských kandidátov podľa presných referencií.

### 6. 11. 2026 – krajinské balíky dávky 23

- [Radio PR #14](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/14) a [FullHDGlass PR #46](https://github.com/Evolution-by-Warder/FullHDGlass-Warder-Evolution/pull/46) boli zlúčené po výslovnom schválení. V `main` sú overené oba rádiové súbory a spoločný `AGENTS.md` s pôvodnými pokynmi a odkazom na rádiový register.
- [Pracovný commit `6832fb4`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/6832fb4d5a63842984cbc2af01fa62de12dee3d4) ukladá opakovateľný postup zostavenia a [kontrolné súčty 54 ZIPov](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/6832fb4d5a63842984cbc2af01fa62de12dee3d4/picons/radio-world/staging/batch-23/country-pack-checksums.json) pre AR, DE, GB, SE, UA a US. Výstup obsahuje existujúcich 90 nemeckých referencií v každom variante s bitovo identickými PNG a deväť nových referencií naprieč krajinami.
- Dve zostavenia dali rovnaký výstup. Prešlo 29 testov downloadera a lokálna inštalácia troch pozadí 220×132 cez testovací endpoint. Zachovala existujúci index aj používateľský picon a pri opakovaní ZIPy nesťahovala.
- Ďalej pripraviť výber ďalších krajín v plugine. Pracovné ZIPy treba pred prípadným zverejnením pripnúť k commitu s balíkmi a pripraviť manifesty pre downloader. Publikovanie balíkov a zmeny v produkčnom plugine čakajú na samostatné schválenie.

### 6. 11. 2026 – dávka 23

- Argentina 2, Nemecko 1, Švédsko 1, Ukrajina 1, Spojené kráľovstvo 2, USA 2. Každá referencia má transparentný, biely a čierny variant v 50×30, 220×132 a 400×240. Sedem kandidátov má zdokumentovanú blokáciu identity alebo značky. [Manifest a SHA-256](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/02aafea7e4e326aace955f72b6d20c68c7e45eba/picons/radio-world/staging/batch-23/manifest.json)
- Overené ZIPy a všetkých 81 PNG. Prešlo 29 testov downloadera. Lokálny test s pracovným endpointom a katalógom overil inštaláciu, vyhľadanie a opakovanie bez nového sťahovania pre všetkých deväť referencií v troch variantoch 220×132. Dávka zostáva pracovná. [Detailný register dávky](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/02aafea7e4e326aace955f72b6d20c68c7e45eba/picons/radio-world/RADIO_PICONS_PROGRESS.md)
- Schválenie zahŕňa spracovanie ďalších rádiových dávok. Produkčný merge, publikovanie balíkov a vydanie IPK majú samostatné schvaľovanie.

## Zostávajúce úlohy

1. Naviazať na dávku 23. Overiť aktuálny katalóg a obnoviť úplný inventár checkpointu 22, ak je dostupný. Pri zlúčení evidencie deduplikovať presné servisné referencie a chrániť schválené PNG.
2. Pokračovať v dávkach zo zvyšného katalógu. Preverovať identitu podľa servisnej referencie, streamu a dôkazu vysielateľa. Blokované logá evidovať oddelene. Kossuth, Radio 88 Retro / REPLAY a regionálne ESKA 2 sledovať v [redakčnom registri](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/issues/41).
3. Predložiť overenú integráciu krajín na schválenie. Po schválení postupovať v poradí PiconHub PR #64, overenie živých balíkov, Radio PR #15 a samostatné schválenie vydania.
4. Overiť nové správanie na fyzickom prijímači a zapísať výsledok oddelene od CI a lokálnych testov.
