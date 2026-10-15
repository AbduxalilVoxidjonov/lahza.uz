# ADR-0006: Har epizod — o'z papkasi va SQLite bazasi

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 12

## Kontekst
Desktop dastur uchun server bazasi (PostgreSQL) va navbat (RabbitMQ) ortiqcha. Loyiha boshqa kompyuterga ko'chishi kerak.

## Qaror
`Epizod.lahza/` papkasi: `project.db` (SQLite, WAL), `cache/`, `thumbs/`. Umumiy narsalar `Library/library.db` da. Vaqt — butun son ms; matn — NFC, rasmiy imlo. Sxema versiyalanadi; migratsiyadan oldin zaxira nusxa.

## Oqibatlar
* Loyihani ko'chirish = papkani nusxalash; manba video yo'li topilmasa dastur qayta so'raydi.
* Bir vaqtda bitta yozuvchi — engine ichida ulanishlar qisqa umrli.
