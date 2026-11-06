# Warder Radio – register postupu

Aktualizované 6. 11. 2026. Register pokrýva samostatný plugin pre Enigma2 a jeho rádiové picony. Pravidlá odovzdania sú v [AGENTS.md](AGENTS.md).

## Overené východiská

| Oblasť | Vetva alebo vydanie | Posledný overený commit a stav |
| --- | --- | --- |
| Warder Radio | `main` | [`095e88d`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/095e88dbec8a9504931978a6c79b378dd753b5b2), univerzálny downloader zlúčený. Stabilný aj testovací kanál naďalej uvádzajú [0.1.8](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/tag/warder-radio-v0.1.8). |
| Warder Radio 0.1.8 | Zdroj vydania | [`26225c0`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/26225c0d2a61d04663c1ed3d3cf083faa0d94305), zastavenie a obnovenie prehrávania pôvodnej stanice bez duplikovania histórie. [Záznam vydania](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/blob/349fd7ec25e3f7979cb28b8dab0ed5f3fbf2434b/docs/releases/radio-resume-0.1.8.json) uvádza 148 jednotkových testov a po 70 natívnych testov na OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next. Fyzický test 0.1.8 v zázname nie je. |
| Rádiový katalóg a živé balíky | PiconHub `main` | [`648c52b`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/648c52b5cc69038bd1b6a1d7ad5b5514c308458d), balíky cez dávku 27 a univerzálny index. Zdrojový katalóg má 40 903 servisných referencií v 219 krajinských skupinách a skupine HDF. |
| Svetový checkpoint 22 | PiconHub `work/radio-catalogue-strict-ocr-20261105` | [`4dd8220`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/4dd8220efc5180db9e0fca56335b4a01b9193558/migration/radio-reconciled-checkpoint-20261105/summary.json), 19 756 pripravených referencií a 177 804 PNG, z toho 19 706 referencií v hlavnom katalógu checkpointu. Evidovaných 21 197 nepokrytých referencií. Stav je pracovný. |
| Dávka 23 | PiconHub `work/warder-radio-world-batch23-20261106` | [`02aafea7`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/02aafea7e4e326aace955f72b6d20c68c7e45eba), 9 referencií a 81 PNG, pripravené v pracovnej vetve. |

## Pokrytie krajín

[Živý online index](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/main/picons/radio-world/catalog/countries.json) eviduje **219 krajín, 16 dostupných a 491 pokrytých krajinských referencií**. Skupina HDF je vedená oddelene. Úplné pokrytie je overené pre Slovensko a Česko.

| Krajina | Referencie v katalógu | Živé pokrytie | Stav |
| --- | ---: | ---: | --- |
| SK · Slovensko | 89 | 89 | Úplné |
| CZ · Čechy | 249 | 249 | Úplné |
| AR · Argentina | 841 | 3 | Čiastočné |
| AT · Austria | 219 | 12 | Čiastočné |
| CL · Chile | 415 | 1 | Čiastočné |
| DE · Germany | 3 422 | 76 | Čiastočné |
| GR · Greece | 1 597 | 1 | Čiastočné |
| HU · Hungary | 237 | 11 | Čiastočné |
| LT · Lithuania | 80 | 1 | Čiastočné |
| PL · Poland | 500 | 25 | Čiastočné |
| RO · Romania | 657 | 1 | Čiastočné |
| LK · Sri Lanka | 51 | 1 | Čiastočné |
| SE · Sweden | 115 | 1 | Čiastočné |
| UA · Ukraine | 202 | 1 | Čiastočné |
| GB · United Kingdom | 1 345 | 5 | Čiastočné |
| US · United States | 4 881 | 14 | Čiastočné |

Úplný historický manifest cez dávku 28 bol obnovený: 22 751 pripravených referencií a register 18 307 skontrolovaných zdrojov. Ich PNG payloady nie sú všetky lokálne obnovené. Čísla tabuľky vyššie pochádzajú z produkčného indexu; historický checkpoint a nové pracovné dávky sú vedené oddelene.

## Denník významných zmien

### 6. 11. 2026 – schválená stabilná 0.1.9, záverečná príprava

- Používateľ potvrdil úspešné fyzické overenie `0.1.9-test2`: navigácia, stránkovanie, OK označovanie aj samostatné výsledky aktualizácie fungujú. Výslovne schválil stabilnú `0.1.9`, merge do main, oficiálny Release aj aktualizačné kanály. Model prijímača a presná verzia image neboli uvedené.
- Vetva `release/radio-0.1.9-20261106` vychádza z overeného `3b21a6b`; produkčný základ je Radio `428f64a`, PiconHub `648c52b`, pracovná piconová dávka 29 `7a650606`. UI a ostatné funkcie test2 ostávajú bez zmien. Mení sa verzia, dokumentácia a nevyhnutná kompatibilita prechodov test → stable.
- Skutočný problém poradia balíkov: `0.1.9-1` je pre opkg starší než `0.1.9-test2-1`, hoci plugin správne radí stabilnú verziu vyššie. Pôvodný test2 updater vyžaduje presné číslo balíka. Preto testing kanál cielene ponúkne `0.1.9-test3`, po reštarte jeho updater číta stable kanál a inštaluje `0.1.9`. Výnimka `--force-downgrade` platí výhradne pre presný prechod test3 → 0.1.9 po všetkých kontrolách integrity. Z 0.1.8 je prechod priamy. Žiadne ručné sťahovanie IPK nie je potrebné.
- Lokálne prešlo 162 jednotkových testov a 79 natívnych replayov na každom základe OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next. Pred merge nasleduje CI s reálnym opkg v izolovaných offline koreňoch, pôvodnými publikovanými IPK, obľúbenými/históriou/nastaveniami/piconmi a kontrolou živého downloadera. Skutočný opkg odhalil aj chybu pôvodného overovača: odmietal platný stav `install user installed`. Nový overovač prijíma `ok` aj `user` iba pri presnej verzii a úplnom stave installed; chyby/reinstreq/unpacked naďalej odmieta. Pôvodný kód prvého kroku môže po úspešnej inštalácii nahlásiť falošnú chybu; vtedy je potrebný jednorazový reštart GUI. Test ponecháva pôvodný kód, eviduje túto chybu a nezávisle overí skutočný balík/stav aj používateľské dáta pred pokračovaním. Stav: schválené na vydanie, zatiaľ nepublikované.


### 6. 11. 2026 – oprava navigácie a výsledku aktualizácie, 0.1.9-test2

- Používateľ fyzicky otestoval `0.1.9-test1`: potvrdil fungovanie zoznamu 219 krajín, aktívne dostupné krajiny a zobrazenie počtov piconov. Toto je používateľom potvrdený fyzický rozsah; model prijímača a presná verzia image neboli uvedené. Nové opravy ešte fyzicky overené nie sú.
- Samostatná vetva `work/radio-0.1.9-test2-navigation-update-20261106` vychádza z testovacieho základu `f26b558a4f307fd5936843516c797afe87eb10bc`. Produkčné Radio `main` je `428f64a`, PiconHub `main` je `648c52b`; posledná piconová vetva dávky 29 je `7a650606`. V tomto zadaní sa mení iba Radio.
- V krajinskom výbere ľavá a pravá volajú natívne pageUp/pageDown. Ľavá opustí výber až pri indexe 0; hore/dole zostávajú po jednej položke. OK výhradne prepína dostupnú krajinu. Stránkovanie nemení rozpracované ani uložené označenia. Výber 219 krajín, online dostupnosť a počty ostávajú nezmenené.
- Ručná kontrola aktualizácie otvára samostatné bezrámové informačné okno Warder Radio pre aktuálnu verziu, dostupnú aktualizáciu aj zlyhanie vrátane odmietnutej pracovnej fronty. OK/EXIT zatvárajú bez inštalácie. Pri dostupnej aktualizácii zelené tlačidlo otvorí existujúce explicitné potvrdenie; samotné zobrazenie výsledku nič neinštaluje. Bezpečný updater a priebeh inštalácie sa nemenia. Nový stav dostupnosti je preložený do všetkých 21 jazykov.
- Lokálne prešlo 159 jednotkových testov a po 79 natívnych replayov na OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next, vrátane stránkovania v 720p/1080p/1440p/2160p a troch stavov informačného okna. Prešla kontrola IPK a gramatiky Python 3.9. Hlavný XML dizajn, downloader, model používateľských dát a bezpečný updater sú bajtovo zhodné so základom test1. [GitHub CI](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42231547865) prešiel so [zdrojom `aece59b`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/aece59bfc738fdb88c15c1187f002b7058334127). Zopakoval 159 jednotkových testov a 79 replayov na každom základe. Živý downloader v každom pozadí 220×132 nainštaloval 490 piconov, zachoval jeden vlastný a vzorové nastavenia, obľúbené aj históriu; opakovanie nevyžiadalo ZIPy. Overil 45 reálnych ZIPov. Lokálne aj CI IPK majú identické bajty: 3 176 184 B, SHA-256 `81594a7401cdb52b8466ff8fc0a887a04019a8a1576aba428030f2472be30f2d`. [Podrobný záznam](docs/releases/radio-0.1.9-test2.json) a [fyzický testovací postup](docs/receiver-test-0.1.9-test2.md). Publikácia: iba pracovná vetva a priame testovacie IPK; stabilné vydanie ani aktualizačné kanály nie sú povolené. Testovací IPK je pripravený a odovzdaný. Najbližší krok: fyzicky preveriť stránkovanie a informačné okno vo verzii `0.1.9-test2`; zaznamenať model prijímača a presnú verziu image.


### 6. 11. 2026 – testovací IPK 0.1.9-test1 a pokračovanie dávkou 29

- Podľa zadania je pripravený samostatný testovací balík `0.1.9-test1`, bez stabilného vydania, GitHub Release alebo zmeny aktualizačných kanálov. Základ je produkčný Radio `428f64a` po merge `095e88d` a PiconHub `648c52b`. [Zdroj testovacieho kandidáta `101445e`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/101445efe2c6e90634928ca65bde3352f0838840) mení v runtime iba `version.txt`; existujúci kód univerzálneho downloadera sa zachoval.
- [Testovací CI beh](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42227033576) prešiel: **159 jednotkových testov**, **73 natívnych replayov na každom** z OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next, gramatika Python 3.9 a kontrola IPK vrátane povolených ciest a offline inštalačných skriptov. Lokálne aj CI IPK majú rovnaké bajty a SHA-256 `4091be762cb772ff240027eddbadd1dcfc2c5d320eaf202aae3aa502e4735cef` (3 175 204 B).
- Živý index má **219 krajín, 16 dostupných a 491 pokrytých referencií**. V každom z troch pozadí 220×132 sa overilo 15 skutočných ZIPov, nainštalovalo 490 piconov a zachoval jeden vlastný picon. Nastavenia, obľúbené aj história vzorových používateľských dát zostali zhodné; nedostupná uložená krajina zostala vybraná. Opakovanie nevyžiadalo ZIPy. Lokálny prvý pokus prerušil timeout švédskeho archívu; úplný čistý CI replay všetkých krajín a pozadí prešiel.
- Balík bol odovzdaný priamo na fyzickú skúšku. [Inštalačný a skúšobný postup](docs/receiver-test-0.1.9-test1.md), [presný záznam zostavenia](docs/releases/radio-0.1.9-test1.json). Fyzický prijímač **zatiaľ neoverený**. Budúca stabilná verzia musí byť aj podľa opkg novšia než `0.1.9-test1` (napríklad `0.1.10`); jej vydanie zatiaľ nie je povolené.
- Pre ďalšie picony bol obnovený presný historický manifest cez uzavretú dávku 28: 22 751 pripravených referencií a 18 307 skontrolovaných zdrojov. Overili sa aj dávky 23–27 a nezmenený živý katalóg 40 903 referencií. Nová [samostatná pracovná vetva dávky 29](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/tree/work/radio-world-batch29-20261106) pripravuje **4 nové referencie / 36 PNG**: Schwendermarkt (AT), Durisima Radio (CO), 2000er Hits by MineMusic a Radio AENA (DE). [Zdrojový plán `de00619`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/de00619a5c74cc45a7f5e73cc0ef315f5464204d) uchováva dôkazy a 16 odložených kandidátov. Žiadna hotová referencia ani schválené PNG sa neprekresľovali. Nové balíky zostávajú staging, bez zápisu do živého indexu. [GitHub zostavenie dávky 29](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/actions/runs/42227610357) prešlo vrátane dvoch zhodných renderov, deviatich ZIPov a staging downloadera v troch pozadiach. [Výsledný commit `7268d09`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/7268d09fe94b6a833ca5b99523353acbeb9cde01) uchováva manifest, SHA-256 aj PNG archívy; lokálny a GitHub manifest sa zhodujú.


### 6. 11. 2026 – produkčná publikácia dávok 23–27

- Po výslovnom schválení zlúčený [PiconHub PR #65](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/pull/65) ako [`648c52b`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/648c52b5cc69038bd1b6a1d7ad5b5514c308458d). Živý index a 15 manifestov sa zhodujú s pripnutými schválenými údajmi. Všetkých 135 produkčných ZIPov bolo stiahnutých a overených kontrolou SHA-256, CRC a SHA-256 členov. Zachovalo sa všetkých 4 968 pôvodných súčtov PNG z kandidáta cez dávku 26 aj pôvodné PNG zo starších živých kolekcií.
- Po kontrole PiconHubu zlúčený [Radio PR #15](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/15) ako [`095e88d`](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/commit/095e88dbec8a9504931978a6c79b378dd753b5b2). Pred aj po zlúčení prešiel downloader s produkčným indexom, reálnymi katalógovými dátami a ZIPmi pre všetkých 16 dostupných krajín. Každé pozadie 220×132 nainštalovalo 490 piconov a zachovalo jeden používateľský. Opakovanie nevyžiadalo ZIPy.
- Radio merge bol označený `[skip ci]`, aby sa nespustilo automatické vydávanie. Overená nulová aktivita release workflow pre tento commit, nezmenené súbory aktualizačných kanálov a nezmenené GitHub release assety. Fyzická skúška prijímača je otvorená. Príprava testovacej verzie IPK je ďalší krok.

### 6. 11. 2026 – finálna kontrola spoločného kandidáta

- [PiconHub PR #65](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/pull/65) smeruje na [`bb44e9e`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/bb44e9e8f7359ab115ea0d671c51f33889db78ae) s dávkami 23–27 a pracovným indexom **219 krajín, 16 dostupných, 491 referencií**. Dávka 27 je súčasťou spoločných DE a GB balíkov. [Radio PR #15](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/15) používa ten istý formát online indexu.
- Porovnanie všetkých deviatich variantov v 15 kolekciách potvrdilo zhodu **4 968 pôvodných SHA-256 položiek**. Spätne stiahnutých a overených bolo 57 ZIPov: všetky tri pozadia 220×132 pre dostupné kolekcie a oba ďalšie rozmery zmenených DE a GB balíkov. Nové PNG sa zhodujú s manifestom dávky 27.
- Finálny downloader na `c1820b0` prešiel s reálnymi katalógovými balíkmi všetkých 16 dostupných krajín, ich manifestmi a ZIPmi. V každom pozadí nainštaloval 490 piconov a zachoval jeden používateľský. Pri opakovaní nesťahoval ZIPy. Nedostupná voľba zostala uložená a spoločný SK/CZ balík sa stiahol iba raz na pozadie.
- Prešlo 159 jednotkových testov, lokálna kontrola IPK a [GitHub CI s natívnymi replaymi](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42220201366). Fyzický prijímač zostáva otvorený. Oba PR sú predložené na schválenie. Produkčný merge, publikácia a vydanie IPK vyžadujú súhlas.

### 6. 11. 2026 – dávka 27

- [Pracovný commit `bb44e9e`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/bb44e9e8f7359ab115ea0d671c51f33889db78ae) rozširuje DE o Technoszene a Lkwfreunde a GB o Like Country. [Manifest dávky](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/bb44e9e8f7359ab115ea0d671c51f33889db78ae/picons/radio-world/staging/batch-27/manifest.json) obsahuje **3 referencie, 27 PNG a 5 odložených kandidátov**. Pri odložených položkách chýba potvrdené párovanie presného streamu a loga.
- [Zostavenie](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/actions/runs/42219877225) prešlo. Pred každým balíkovým commitom sa overilo **1 152 pôvodných PNG položiek** v 11 pracovných kolekciách oproti dávke 26. Ochrana odmietla zámerne zmenenú testovaciu položku. Staršie dávkové ZIPy a ostatné schválené krajinské kolekcie chráni kontrola Git rozdielu.
- [Pracovný univerzálny index](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/bb44e9e8f7359ab115ea0d671c51f33889db78ae/picons/radio-world/catalog/countries.json) eviduje **219 krajín, 16 dostupných a 491 pokrytých krajinských referencií**. Overenie s reálnymi ZIPmi DE a GB v každom z troch pozadí 220×132 nainštalovalo 80 piconov, zachovalo jeden vlastný súbor a pri opakovaní ZIPy nesťahovalo. Ostatné dva rozmery sú archivované v pracovných ZIPoch. Fyzický test zostáva otvorený.
- [PiconHub PR #65](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/pull/65) je kandidát na schválenie cez dávku 26; dávka 27 zostáva na samostatnej pracovnej vetve. [Radio PR #15](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/15) používa univerzálny index. Živá publikácia, merge aj vydanie IPK majú samostatný súhlas.

### 6. 11. 2026 – dávka 26 a univerzálny manifest

- [Pracovný commit `fe6a52a`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/fe6a52a41b9b359bdf842d8b194830d4c0718e16) integruje **9 referencií a 81 PNG** do siedmich krajinských kolekcií. CL, GR, LT, LK, RO a GB pridali po jednej referencii, US tri. Dávky 23–25 zostali uložené bez opätovného renderovania.
- [Kontrola SHA-256 a zostavenie](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/actions/runs/42219235514) prešli. Pred každým balíkovým commitom sa overovalo všetkých **1 071 pôvodných PNG položiek** v šiestich pracovných kolekciách proti `1eff65c`; ostatné schválené kolekcie a staršie ZIPy sú chránené aj kontrolou Git rozdielu. Zostavenie používa zmrazených deväť originálov, takže už nezávisí od dostupnosti Gavdos alebo ďalšieho vysielateľa.
- [Pracovný univerzálny manifest](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/fe6a52a41b9b359bdf842d8b194830d4c0718e16/picons/radio-world/catalog/countries.json) má **219 krajín, 16 dostupných a 488 pokrytých krajinských referencií**. Ďalšie dva rozmery sú naďalej v ZIPoch na GitHube.
- Na [Radio PR #15](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/pull/15) prešlo 159 jednotkových testov a kontrola lokálneho IPK. Skúška s reálnym pracovným indexom, pripnutými manifestmi a ZIPmi overila pri každom z troch pozadí 22 spravovaných inštalácií, zachovanie jedného vlastného piconu a opakovanie bez ZIPov. Vyžadované ZIPy boli výhradne 220×132. Fyzické overenie zostáva otvorené.
- Zverejnenie pracovných balíkov, zlúčenie a vydanie IPK čakajú na schválenie. Ďalšia dávka pokračuje oddelene od tohto kandidáta.

### 6. 11. 2026 – krajinské balíky cez dávku 25

- [Pracovný commit `1eff65c`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/1eff65c3698280657fd7ac1b8db4cff40cb80089) pridáva 20 referencií z dávok 24 a 25 do krajinských kandidátov. Počty súborov na variant sú AR 2 → 3, DE 91 → 100, GB 2 → 3 a US 2 → 11. SE a UA zostávajú na balíkoch dávky 23.
- [Zostavenie na GitHube](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/actions/runs/42217409652) a spätné stiahnutie overili 36 ZIPov a štyri manifesty downloadera. V každom z deviatich variantov má všetkých 97 existujúcich PNG rovnaký SHA-256 a nové PNG sa zhodujú so svojimi dávkovými manifestmi. Obsah švédskeho a ukrajinského manifestu sa zhoduje s dávkou 23.
- Stav je pracovný na vetve `work/warder-radio-country-packs-batch25-20261106`. Pôvodný PiconHub PR #64 zostáva kandidátom dávky 23. Rozšírený kandidát s dávkami 24 a 25 je vedený oddelene. Produkčný rozsah, zlúčenie a vydanie čakajú na výslovný súhlas.

### 6. 11. 2026 – univerzálna dostupnosť všetkých krajín (pracovná integrácia)

- Výber piconov už obsahuje všetkých **219 krajín** katalógu. Samostatná skupina HDF sa nepovažuje za krajinu. Online manifest `picons/radio-world/catalog/countries.json` určuje dostupnosť, počet pokrytých referencií a nemenný manifest každého balíka. Krajina bez publikovaných piconov zostáva viditeľná a nedá sa novo vybrať; čiastočná krajina umožňuje stiahnuť existujúce picony.
- Sprístupnenie ďalšej krajiny vyžaduje iba balíky a aktualizáciu online manifestu, bez nového IPK. Plugin overuje presnú cestu, SHA-256 a veľkosť krajinského manifestu, ZIP aj PNG. Sťahuje výhradne **220×132** v zvolenom transparentnom, bielom alebo čiernom pozadí. Ďalšie rozmery zostávajú v GitHube.
- Sieťová obnova výberu aj sťahovanie bežia mimo GUI. Zachováva sa posledný platný manifest a pribalený stav publikovaných šiestich krajín; chybná alebo neúplná obnova neprepíše dobrú cache. Pôvodné nastavenia, zvolené krajiny a vlastné PNG zostávajú zachované. Odchod z výberu ruší obnovu a ignoruje oneskorené výsledky.
- Lokálne prešlo **159 jednotkových testov**, kontrola IPK vrátane gramatiky Python 3.9 a **73 natívnych replayov na každej z troch vetiev**: OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next. Testy zahŕňajú sprístupnenie krajiny iba zmenou manifestu, všetky tri pozadia, vylúčenie 50×30/400×240, neúplný manifest, výpadok siete, pôvodné nastavenia a používateľské picony. Fyzický prijímač nebol testovaný.
- PiconHub pracovný commit [`c33c3cb`](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/commit/c33c3cb33c4fc32682ca5dc1c4ad1933bdb96803) spája dávky 24 a 25 do šiestich krajinských balíkov: **119 PNG súborov na variant**, z toho 99 predchádzajúcich zostáva bajtovo zhodných. Pracovný univerzálny index rozlišuje všetkých 219 krajín, 11 dostupných krajín a 479 presných krajinských referencií. Živý index/publikované balíky zostávajú oddelené od pracovného stavu.
- Podrobnosti a poradie nasadenia: [online dostupnosť krajín](docs/picon-country-availability.md). Pracovné zmeny sú schválené; produkčný merge, publikácia balíkov a vydanie IPK čakajú na výslovné schválenie. Najbližší krok je integrácia overenej dávky 26, prehratie reálnych manifestov a ZIPov a aktualizácia draft PR.

### 6. 11. 2026 – dávka 25

- [Pracovný manifest](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/blob/3cf90597d6fd644e257ff79d231332c6fc7d9e46/picons/radio-world/staging/batch-25/manifest.json) obsahuje 4 referencie USA a 36 PNG. Backlink Broadcast, Grok and Roll, OpenAir a Thinking Frequencies majú pôvodné grafiky prevádzkovateľa a zhodu presných streamov s katalógom.
- [Zostavenie](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/actions/runs/42203293074) prešlo po oprave zápisu príkazu v prvom behu. Deväť ZIPov bolo opätovne stiahnutých a overených. Dávky 24 a 25 spolu pridávajú 20 navzájom odlišných pracovných referencií a 180 PNG. Zlúčenie s úplným historickým inventárom checkpointu 22 zostáva otvorené.

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

1. Pokračovať od staging dávky 29 a obnoveného historického manifestu cez dávku 28. Začleniť štyri nové referencie do samostatných AT, CO a DE krajinských kandidátov, deduplikovať presné servisné referencie a chrániť schválené PNG.
2. Pokračovať v dávkach zo zvyšného katalógu. Preverovať identitu podľa servisnej referencie, streamu a dôkazu vysielateľa. Blokované logá evidovať oddelene. Kossuth, Radio 88 Retro / REPLAY a regionálne ESKA 2 sledovať v [redakčnom registri](https://github.com/Evolution-by-Warder/PiconHub-Warder-Evolution/issues/41).
3. Fyzicky overiť pripravenú verziu 0.1.9-test1 podľa skúšobného postupu; stabilné vydanie zostáva pozastavené.
4. Overiť nové správanie na fyzickom prijímači a zapísať výsledok oddelene od CI a lokálnych testov.

