# Warder Radio 0.1.9-test1 — fyzická skúška

Balík je určený na ručnú skúšku v prijímači. Má univerzálnu architektúru 219 krajín a živý online manifest. Aktuálne má 16 krajín publikované picony; SK a CZ sú úplné, ostatné dostupné krajiny sú čiastočné. Nejde o kompletné pokrytie celého sveta.

## Inštalácia

Skopíruj `enigma2-plugin-extensions-radio-warder-evolution_0.1.9-test1_all.ipk` do `/tmp` prijímača a nainštaluj ho cez miestnu inštaláciu balíkov alebo cez SSH:

```sh
opkg install /tmp/enigma2-plugin-extensions-radio-warder-evolution_0.1.9-test1_all.ipk
```

Potom reštartuj GUI a otvor Warder Radio. Verzia má byť `0.1.9-test1`. Balík aktualizuje iba vlastné súbory pluginu a dokumentáciu. Nastavenia, obľúbené, história, vlastné stanice a používateľské picony sa ponechávajú. Starý balík neodinštaluj a nemaž priečinky s dátami. Závislosti sa používajú z nakonfigurovaných feedov prijímača.

## Čo fyzicky preveriť

1. Po štarte skontroluj zachovanie obľúbených staníc, histórie, nastavení a vlastných piconov. Spusť jednu zo svojich obľúbených staníc.
2. V hlavnom ľavom menu otvor sťahovanie piconov. Over všetkých 219 krajín, označenie nedostupných a čiastočne dostupných krajín a existujúci výber úložiska.
3. S vybraným SK/CZ a aspoň jednou čiastočnou krajinou vykonaj sťahovanie postupne pre transparentné, biele a čierne pozadie. Rozmer v prijímači je iba 220 × 132. Vlastný picon má zostať zachovaný.
4. Pri každom pozadí zopakuj sťahovanie bez zmeny výberu. Picony majú byť aktuálne bez opätovného sťahovania ZIPov. Po zmene pozadia sa stiahne zvolená varianta.
5. Zatvor a znovu otvor plugin; over uložené krajiny, pozadie, úložisko a prehrávanie. Skontroluj odozvu ovládania počas sťahovania.

Do výsledku zapíš model prijímača, presnú verziu OpenATV/OpenPLi, umiestnenie piconov a prípadnú chybu alebo crashlog. Natívne replaye a CI nenahrádzajú fyzickú skúšku.

## Doložené automatické kontroly

Prešlo 159 jednotkových testov, 73 natívnych replayov na každom z OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next, kontrola IPK a gramatiky Python 3.9. Živý downloader pri každom pozadí nainštaloval 490 piconov, zachoval jeden vlastný, nastavenia a obľúbené aj históriu; opakovanie vyžiadalo nula ZIPov. Overil 15 kolekcií / 45 skutočných ZIPov. Výstup CI je bajtovo zhodný s lokálnym IPK.

[Úspešný testovací beh](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42227033576). [Podrobný záznam a kontrolný súčet](releases/radio-0.1.9-test1.json).

Stabilné vydanie ani aktualizačné kanály sa nemenili. Testovací balík sa dodáva priamo a ako CI artifact, bez GitHub Release.
