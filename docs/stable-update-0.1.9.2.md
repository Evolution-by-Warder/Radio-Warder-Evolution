# Warder Radio 0.1.9.2 – aktualizácia priamo v plugine

Používateľ fyzicky potvrdil nové modré potvrdenie aj následné okno inštalácie z testovacej 0.1.9.1-test1 revízie 2 a výslovne schválil stabilné vydanie po automatických kontrolách. Vzhľad, ovládanie aj bezpečnostná logika sa nemenia.

Otvorte **Nastavenia → Aktualizovať**. Po nájdení verzie 0.1.9.2 stlačte **zelené tlačidlo**. Potvrdenie má predvolené **Nie**; šípkou vyberte **Áno** a potvrďte **OK**. EXIT ruší potvrdenie. Z inštalácií, ktoré už používajú schválené modré okno, sa jeho vzhľad zachová; ostatné ho dostanú po tejto aktualizácii. Následný pôvodný priebeh overí stiahnuté IPK a výslednú inštaláciu; po úspechu reštartuje GUI.

Stabilné 0.1.9/0.1.9.1, pôvodný test1 a fyzicky overená revízia 2 aj migračná 0.1.9.1-test2 môžu prejsť **priamo na 0.1.9.2**. Vyššie číselné označenie odstráni potrebu ďalšieho migračného balíka alebo downgrade. Oba v2 kanály poskytujú rovnakú stabilnú 0.1.9.2; balíky predošlých vydaní a legacy bridge zostávajú nemenné.

Historické 0.1.8 a 0.1.9-test2 môžu po úspešnej inštalácii nesprávne hlásiť neúplný stav kvôli platnému `install user installed`; v tomto presnom prípade jednorazovo reštartujte GUI. Ide o chybu pôvodného overovača, nie stratu balíka. Ručné stiahnutie ani kopírovanie IPK netreba.

Nastavenia, obľúbené, história, vlastné stanice, používateľské picony a cache katalógu zostávajú zachované. Katalóg obsahuje 219 krajín, online manifest a počty piconov. Do skinu ani satelitných piconov sa nezasahuje.
