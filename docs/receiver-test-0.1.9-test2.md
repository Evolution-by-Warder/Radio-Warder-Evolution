# Warder Radio 0.1.9-test2 — skúška opráv na prijímači

Základom je používateľom fyzicky vyskúšaná verzia 0.1.9-test1. Potvrdený bol zoznam 219 krajín, aktivácia dostupných krajín a počty piconov. Model prijímača ani image zatiaľ nie sú zaznamenané. Táto nová verzia opravuje iba navigáciu a výsledok kontroly aktualizácie; sama ešte fyzicky overená nie je.

## Inštalácia

Skopíruj `enigma2-plugin-extensions-radio-warder-evolution_0.1.9-test2_all.ipk` do `/tmp` a nainštaluj cez miestnu inštaláciu IPK alebo cez SSH:

```sh
opkg install /tmp/enigma2-plugin-extensions-radio-warder-evolution_0.1.9-test2_all.ipk
```

Potom reštartuj GUI. Ide o aktualizáciu existujúceho balíka; predchádzajúcu verziu neodinštaluj a nemaž používateľské dáta. Nastavenia, obľúbené, história a vlastné picony zostávajú zachované.

## Krajiny piconov

- Otvor Sťahovanie piconov → Krajiny piconov. Skontroluj 219 krajín, dostupnosť a počty.
- Hore/dole sa pohybujú po jednej položke. Pravá stránkuje dopredu o viditeľnú stránku (osem riadkov); ľavá stránkuje dozadu. Ľavá vráti predchádzajúcu obrazovku až vtedy, keď stojíš na úplne prvej položke.
- OK iba označí alebo odznačí dostupnú krajinu. Over, že šípky nemenia označenia, ani pri prechode cez poslednú neúplnú stránku.
- Označ viac krajín, prelistuj tam aj späť a potvrď zeleným tlačidlom. Over zachovanie označení po opätovnom otvorení výberu. EXIT aj návrat ľavou na prvej položke ponechávajú pôvodné správanie zrušenia nepotvrdených zmien.

## Výsledok aktualizácie

- Otvor Nastavenia → Aktualizovať. Výsledok sa otvorí v samostatnom okne Warder Radio; OK alebo EXIT ho zatvoria a vrátia nastavenia bez inštalácie.
- Aktuálna verzia, dostupná novšia verzia a zlyhanie majú vlastné texty. Pri dostupnej verzii zelené tlačidlo otvorí pôvodné explicitné potvrdenie inštalácie. OK ani EXIT v informačnom okne aktualizáciu nespúšťajú.
- Pri odpojenej sieti prever chybový výsledok; po obnovení spojenia kontrolu zopakuj. Dostupná aktualizácia je overená simulovaným výsledkom v natívnych replayoch; produkčné feedy sa pre tento test nemenili.

## Rozsah

Hlavný dizajn a rozmery jeho prvkov, 219 krajín, online manifest, počty piconov, downloader, model používateľských dát a bezpečný mechanizmus aktualizácií sa nemenia. Mimo repozitára Radio sa nič neupravovalo. Stabilné vydanie ani aktualizačné kanály neboli publikované alebo zmenené.

[CI](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42231547865) a [podrobný záznam](releases/radio-0.1.9-test2.json).
