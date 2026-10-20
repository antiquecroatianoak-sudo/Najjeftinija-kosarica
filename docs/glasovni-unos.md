# Glasovno nabrajanje — 20.10.2026.

Prvi pritisak mikrofona otvara sesiju nabrajanja. Drugi završava i dodaje prepoznate artikle. Nova sesija dopunjava postojeći popis. Kratke pauze ne dovršavaju unos: ako mobilni preglednik završi prepoznavanje, aplikacija ga ponovno pokreće samo dok je sesija aktivna. Napuštanje stranice završava sesiju.

Prepoznati tekst prikazuje se tijekom govora. Rezultati se ne dupliciraju pri ponovljenim događajima. Poznati nazivi služe za razdvajanje nabrajanja bez zareza; višerječni nazivi poput sok od naranče i crno vino ostaju zajedno. Nepoznato nabrajanje može trebati ručnu doradu. Pristup mikrofonu ovisi o pregledniku i korisničkoj dozvoli.

Provjere: node tests/glasovni-unos.cjs (simulirano prepoznavanje: četiri artikla, drugi i treći unos bez gubitka popisa, pauze i automatski nastavak, završetak tijekom pauze, ponovljeni rezultati, odbijena dozvola); node tests/kosarica.cjs; node tests/skupine.cjs; Playwright postojeći unos, količine, trgovine i prikaz na više širina. Stvarni korisnikov mikrofon nije ispitan.
