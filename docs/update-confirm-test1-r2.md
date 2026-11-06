# Warder Radio – fyzická skúška potvrdenia aktualizácie

Testovacie IPK: runtime **0.1.9.1-test1**, revízia **2**, súbor `enigma2-plugin-extensions-radio-warder-evolution_0.1.9.1-test1-2_all.ipk`. Vyššia IPK revízia nahradí pôvodný test1; viditeľná verzia pluginu ostáva test1 zámerne, aby stále našiel existujúcu reálnu migračnú test2. Stabilný Release 0.1.9.1 ani feedy sa nemenia.

1. Nainštalovať IPK a reštartovať GUI. Nastavenia, obľúbené, história a picony sa nemažú.
2. Otvoriť Nastavenia → Aktualizovať. Výsledok ponúkne existujúcu 0.1.9.1-test2. Stlačiť zelené tlačidlo.
3. Očakávané samostatné modré okno: **Aktualizovať · Radio Warder Evolution**, **Verzia: 0.1.9.1-test2**, text **Je dostupná nová verzia. Chcete ju nainštalovať?**, možnosti **Áno / Nie**. Predvolené je Nie, vybraná možnosť má svetlomodré zvýraznenie a ukazovatele.
4. Šípky ←/→ aj ↑/↓ menia iba vybranú možnosť. OK pri Nie zatvorí okno bez inštalácie. EXIT zatvorí okno aj pri vybranom Áno. Rádio pokračuje. Kontrolu možno opakovať.
5. OK pri Áno (alebo zelené pri vybranom Áno) skutočne potvrdí inštaláciu existujúcej migračnej 0.1.9.1-test2 a otvorí pôvodný priebeh. Po úspechu a reštarte už beží ponúkaný pôvodný migračný balík, ktorý novú vizuálnu opravu ešte neobsahuje. Ďalšie Aktualizovať vedie na stabilnú 0.1.9.1. Nový vzhľad preto najprv overte cez Nie/EXIT a až potom prípadne dokončite reálnu inštaláciu.

Automatické kontroly používajú pripnuté natívne widgety OpenPLi 9.2, OpenATV 8.1 a OpenATV 8.0-next. Nevydáva sa nová stabilná verzia; jej povýšenie čaká na fyzické potvrdenie používateľa.
