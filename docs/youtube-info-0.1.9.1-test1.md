# Warder Radio 0.1.9.1-test1 – skúška YouTube hlásenia

Pracovný kandidát nad stabilnou 0.1.9, bez publikovania do aktualizačných kanálov.

1. Nainštalovať testovacie IPK a reštartovať GUI. Zachovať priečinky používateľských dát; nič nemažte.
2. Pri rádiu bez údajov o aktuálnej skladbe stlačiť YouTube. Očakávané okno: **YouTube – Warder Radio**, text **Pre aktuálnu skladbu sa nepodarilo nájsť video na YouTube.**, pätička **OK / EXIT · Zavrieť**. Rovnaké okno sa zobrazí po platnom vyhľadávaní bez videa.
3. Overiť zatvorenie cez OK, cez EXIT a samostatne automaticky približne po 8 sekundách. Po zatvorení má hrať rovnaká stanica bez prerušenia; obľúbené, história, nastavenia aj vlastné picony zostávajú zachované.
4. Pri úspešnom vyhľadaní musí pôvodné prehrávanie videa a návrat do rádia fungovať rovnako. Kontrola aktualizácie naďalej používa pôvodné stavy a zelené potvrdenie inštalácie; jej výsledok sa automaticky nezatvára.
5. Overiť hlavné okno, 219 krajín, počty piconov a navigáciu. Tieto obrazovky ani produkčný online manifest sa nemenili.

Automatické replaye používajú pripnuté natívne widgety OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next. Ide o automatické testy, fyzická skúška tejto opravy je ešte potrebná.

Číslo 0.1.9.1-test1 sa v plugine aj opkg radí medzi 0.1.9 a 0.1.10. Stabilný Release 0.1.9, stable v2, testing v2 (migračná test3) a starý testing manifest zostávajú nezmenené.

[Úspešné CI a testovacie artefakty](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/42240635603): 159 úspešných jednotkových testov, 4 preskočené migračné testy špecifické pre 0.1.9, po 85 natívnych testov na každom z troch základov. CI IPK a lokálne IPK sú bajtovo totožné.

IPK: `enigma2-plugin-extensions-radio-warder-evolution_0.1.9.1-test1_all.ipk`, 3 177 972 B. SHA-256: `519034d8bcbb78128531a46f50f0f630ef4d9011bb079881260105e531d0d4ba`.
