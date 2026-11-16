# Warder Radio – pokyny pre pokračovanie

- Tento repozitár spravuje samostatný plugin Warder Radio. Aktívny kandidát používa Radio Browser a online logá. Skin, satelitné picony, Vhannibal a spoločné šablóny patria do samostatného projektového Worku.
- Na začiatku nového chatu otvor [RADIO_PROGRESS.md](RADIO_PROGRESS.md) na aktívnej rádiovej vetve. Porovnaj zaznamenané SHA s aktuálnym `main` a dotknutými PR a vydaniami. Pokračuj od posledného doloženého kroku.
- Po každej významnej zmene aktualizuj register. Zapíš dátum, vetvu, SHA, rozsah testov, stav schválenia a publikácie a ďalší krok. Historické výsledky zostávajú v denníku a v odkazovaných checkpointoch.
- Rádiové balíky a príslušné PR v PiconHube sú archív predchádzajúcej implementácie. Aktívny vývoj online pluginu používa stránkovaný internetový katalóg a automatické logá. Pri aktualizácii chráň obľúbené, históriu, vlastné streamy, nastavenia, nahrávky a stiahnuté používateľské logá.
- Merge, publikovanie balíkov, vydanie IPK a zápis do produkcie vyžadujú výslovný súhlas. Rozlišuj lokálne testy, CI a fyzické overenie.

## Bezpečnosť prístupu a nahrávania na GitHub

- Používaj existujúce, používateľom autorizované GitHub pripojenie a jeho podporované operácie. Nemeň svojvoľne spôsob autentifikácie, neprihlasuj sa cez nový webový formulár, nevytváraj tokeny ani nežiadaj heslá, 2FA kódy či iné prihlasovacie tajomstvá.
- Ak existujúce pripojenie nestačí na nahratie veľkých binárnych súborov, zastav iba dotknutý prenos. Najprv zdokumentuj konkrétne obmedzenie, prípadnú chybu a bezpečné alternatívy; pred novou autentifikáciou alebo zmenou spôsobu prenosu vyžiadaj výslovný súhlas vlastníka.
- Bez nového súhlasu neskúšaj ďalšie prihlasovacie cesty, opakované Base64 uploady ani nekonečné opakovania zlyhávajúcej operácie. Ak je podporovaná už autorizovaná dávková cesta, použi ju iba v rámci existujúcich oprávnení a schváleného rozsahu.
- Pred zápisom over cieľovú vetvu, očakávaný obsah a SHA-256 existujúcich schválených súborov. Nečakaný rozdiel je blokácia, nie dôvod na prepísanie. Pracuj iba na oddelených pracovných vetvách; produkčný merge vyžaduje samostatné schválenie.
- Po každej bezpečne dokončenej dávke ulož commit a aktualizuj `RADIO_PROGRESS.md` s presným SHA, počtami, stavom úspešných uploadov a nespracovanými lokálnymi výstupmi. Nikdy neoznač lokálne pripravené archívy za nahrané, kým neoveríš ich existenciu a kontrolné súčty na GitHube.
