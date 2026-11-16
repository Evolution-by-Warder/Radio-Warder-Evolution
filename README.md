# Radio Warder Evolution

Samostatný natívny prehrávač internetových rádií pre Enigma2 / OpenATV / OpenPLi.

## Stabilná verzia 0.2.1

[Oficiálne vydanie 0.2.1](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/tag/warder-radio-v0.2.1)

Prehrávač používa online katalóg **Radio Browser**. Ponúka výber krajín a hudobných kategórií, sekcie Domov a Odbery, Obľúbené, Históriu, vlastné stanice, vyhľadávanie a natívne prehrávanie Enigma2 (4097).

### Menu

Ľavé menu používa osem vlastných modro-tyrkysových ikon zabalených priamo v IPK. Prvá položka **Krajina: Slovensko** zobrazuje názov krajiny rovnakým písmom ako ostatné položky.

### Logá staníc

Aktuálne logá staníc získava priamo z online údajov stanice a dostupných verejných obrazových zdrojov. Zobrazujú sa len pri viditeľných položkách a ukladajú sa do obmedzenej cache:

`/etc/enigma2/warder-radio/station-logo-cache`

Plugin používa malé online obrázky a vlastný neutrálny náhradný symbol, ak nie je overené logo dostupné. Žiadne externé balíky grafík sa pri otvorení pluginu neinštalujú.

### Hudba a prehrávanie

- Zobrazenie skladby, interpreta a dostupného obalu albumu.
- Informácie o interpretoch, texty piesní podľa dostupných overených zdrojov.
- Živé ICY metadáta, spektrálny analyzátor a voliteľný OLED šetrič.
- Nahrávanie pomocou streamripper, video vyhľadávanie na YouTube.
- Podpora 21 jazykov a rozlíšení HD, Full HD, WQHD a UHD.

### Dáta a aktualizácia

Nastavenia, Obľúbené, História, cache a vlastné stanice sa uchovávajú v `/etc/enigma2/warder-radio` a pri aktualizácii sa neodstraňujú.

Vydanie 0.2.0 bolo overené natívnymi testami OpenATV 8.0/8.1 a OpenPLi 9.2, testom aktualizácie cez opkg a kontrolou IPK. Súbory nových aktualizácií sa kontrolujú pred inštaláciou.

### Vývoj

```sh
python3 tools/build_ipk.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Zdrojový kód: [Radio-Warder-Evolution](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution). Licencia: GPL-2.0-or-later.
