# Warder Radio 0.1.9 — aktualizácie priamo v plugine

Oficiálne stabilné IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.9/enigma2-plugin-extensions-radio-warder-evolution_0.1.9_all.ipk

## Existujúca inštalácia

Otvor **Nastavenia → Aktualizovať** alebo položku **Aktualizovať** v ľavom menu. Keď sa otvorí informačné okno s dostupnou verziou, stlač zelené tlačidlo a následne potvrď inštaláciu. OK/EXIT iba zatvárajú informačné okno. Stiahnutie a kontrolu IPK vykoná plugin.

- **0.1.8 → 0.1.9:** priamy prechod zo stabilného kanála.
- **0.1.9-test1/test2 → 0.1.9-test3 → 0.1.9:** prvý krok poskytne migračný updater. Po reštarte GUI znovu otvor Aktualizovať, čím sa ponúkne stabilná 0.1.9. Nie je potrebné ručne kopírovať IPK.
- **0.1.9 → ďalšie stabilné verzie:** štandardne cez stabilný kanál a tú istú položku Aktualizovať.

## Jednorazové obmedzenie pôvodného overovača

Starý updater 0.1.8/test2 prijíma iba stav opkg `install ok installed`. Reálny opkg po úspešnej inštalácii označuje ručne zvolený balík aj platným stavom `install user installed`. Starý kód preto môže po dokončenej inštalácii zobraziť presnú chybu **Warder Radio package is not completely installed** a nevykonať automatický reštart.

Ak nastane táto presná chyba prvého prechodu, jednorazovo reštartuj GUI. Nová verzia balíka už je nainštalovaná; po reštarte sa načíta opravený overovač. Pri test2 potom znova použi Aktualizovať na prechod z test3 do 0.1.9. Pri inej chybe treba preveriť jej konkrétnu príčinu; nepredpokladaj automaticky úspešnú inštaláciu.

Nový overovač vyžaduje presný názov a verziu balíka, zhodnú runtime verziu a úplný stav installed. Prijíma legitímne príznaky ok/user, ale odmieta unpacked, chyby a reinstreq. Kontrolné súčty, veľkosť, URL, explicitné potvrdenie a overenie inštalácie ostávajú povinné. Výnimka opkg pre poradie test3 → 0.1.9 je obmedzená na tento jediný prechod.

## Kanály a dáta

Stabilný kanál `update/v2/stable.json` poskytuje 0.1.9. Testovací kanál `update/v2/testing.json` cielene poskytuje 0.1.9-test3 pre starý test2 updater. Jeho migračný kód potom číta stabilný kanál. Starý kanál `update/testing.json` zostáva na pôvodnom kompatibilitnom balíku 0.1.0-test11.

Obľúbené, história, vlastné stanice, nastavenia, cache a picony sa neodstraňujú. Zoznam 219 krajín, online manifest, počty piconov a fyzicky overený dizajn/navigácia test2 zostávajú zachované. Nová krajina naďalej nevyžaduje nový IPK.

[Presný záznam vydania a automatických skúšok](releases/radio-0.1.9.json). Skúšky zahŕňajú pôvodné IPK a updater kódy a skutočný opkg 0.3.3/0.6.1 v izolovaných offline koreňoch. Ide o automatické inštalačné skúšky; fyzické potvrdenie používateľa sa vzťahuje na rozhranie test2.
