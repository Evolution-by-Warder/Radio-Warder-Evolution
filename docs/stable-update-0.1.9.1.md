# Aktualizácia na Warder Radio 0.1.9.1

Používateľ fyzicky overil YouTube informačné okno z 0.1.9.1-test1 a schválil jeho stabilné vydanie. Rovnaký komponent, farby, rozloženie, OK/EXIT aj 8-sekundové zatváranie sú zachované.

Zo stabilnej 0.1.9 zvoľte **Nastavenia → Aktualizovať**, v samostatnom informačnom okne stlačte **zelené tlačidlo** a potvrďte inštaláciu. Po overenej inštalácii sa GUI reštartuje.

Z testovacej 0.1.9.1-test1 najprv dostanete migračnú **0.1.9.1-test2**. Po automatickom reštarte zvoľte Aktualizovať znova; následne sa nainštaluje stabilná **0.1.9.1**. Dôvodom je rozdiel medzi poradím test/stable v plugine a opkg. Nie je potrebné ručne kopírovať IPK. Presná výnimka z opkg ochrany pred downgrade platí iba v migračnej verzii a po overení integrity.

Staršie 0.1.8 a 0.1.9-test2 môžu po úspešnej prvej inštalácii nesprávne hlásiť chybu dokončenia kvôli odmietnutiu platného opkg stavu `install user installed`. Vtedy jednorazovo reštartujte GUI; následne sa používa opravený overovač. V prípade starého test2 po reštarte zvoľte Aktualizovať znova. Existujúca 0.1.9-test3 smeruje rovno na stabilný kanál.

Balík vlastní iba súbory pluginu a jeho dokumentáciu. Nastavenia, obľúbené, história, vlastné stanice, používateľské picony, cache katalógu a online katalóg 219 krajín zostávajú zachované. Testovaný dizajn hlavného okna a vyhľadávanie/prehrávanie YouTube sa nemenia.

[Stabilné vydanie 0.1.9.1](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/tag/warder-radio-v0.1.9.1) je publikované. [Priame IPK](https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.9.1/enigma2-plugin-extensions-radio-warder-evolution_0.1.9.1_all.ipk), 3 178 024 B, SHA-256 `99386f0db84588b60e3540e48ae5a0452bf144a517333836597c79494a4d95d3`. Obe aktualizačné vetvy sú verejne overené po publikovaní.
