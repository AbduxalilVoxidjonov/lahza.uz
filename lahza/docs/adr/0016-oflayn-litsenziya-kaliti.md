# ADR-0016: Oflayn litsenziya kaliti — Ed25519 imzolangan payload, standart holatda o'chiq

* Holat: Taklif (kod tayyor, bayroq o'chiq; tijorat qarori kutilmoqda)
* Sana: 2026-10-26
* TZ bo'limi: 19 (Litsenziyalash, tijorat versiya bo'lsa); NFR-01 (oflayn)

## Kontekst
TZ 19-bo'lim server talab qilmaydigan oflayn kalitni ko'zda tutadi: imzolangan ma'lumot (egasi, tarif, muddat, qurilmalar). Ilova tarmoqsiz ishlaydi (NFR-01), shuning uchun faollashtirish serveri, onlayn tekshiruv va bekor qilish ro'yxatini yuklash mumkin emas. Tijorat qarori (tariflar, sinov muddati, narx) hali qabul qilinmagan — mexanizm tayyor bo'lishi, lekin hozirgi bepul foydalanishga hech qanday ta'sir qilmasligi kerak. Katalog imzosi uchun `cryptography` (Ed25519) allaqachon bog'liqlik.

## Qaror
* Kalit = `0x01 || zlib(kanonik JSON payload)` + Ed25519 imzo (domen ajratuvchi `lahza-license/1\0`), foydalanuvchiga `LAHZA-` + base32 5 belgilik guruhlar ko'rinishida beriladi. Payload: `id`, `licensee`, `edition`, `issued`, `expires|null`, `max_devices?`, `devices[]?` (qurilma barmoq izi), `min_version?`/`max_version?`.
* Ochiq kalit(lar) kodga joylanadi (`licensing/keys.py`, bir nechta — almashtirish uchun); maxfiy kalit repozitoriydan tashqarida, `scripts/license_issue.py` bilan kalit chiqariladi. Test kaliti alohida va hech qachon avtomatik ishonchli emas.
* Engine tekshiradi (imzo → qurilma → versiya → muddat), holatni kutubxonaning mavjud `settings` jadvalida saqlaydi; soat orqaga surilishiga qarshi `last_seen` (48 soat tolerans, faqat muddatli kalitlarda).
* `Settings.licensing_enabled = False` (standart): `disabled` holati, `allows()` doim `True`, UI paneli ko'rinmaydi, PUT/DELETE 409. Ochiq kalit kiritilmagan build'da ham bloklanmaydi (`not_configured`).
* Kutubxona: mavjud `cryptography` — yangi bog'liqlik yo'q.

## Oqibatlar
* Ijobiy: server va tarmoq yo'q; kalit o'z-o'zini tasdiqlaydi; tijorat qarori qabul qilinsa, faqat bayroq va `keys.py` dagi ochiq kalit o'zgaradi.
* Salbiy: oflayn himoyani kodni o'zgartirib chetlab o'tish mumkin; `max_devices` sanab bo'lmaydi (faqat `devices` bilan qat'iy bog'lash); bekor qilish faqat yangi reliz orqali; ~400 belgilik kalit qo'lda terish uchun uzun (nusxalash nazarda tutilgan).
* Vazifalar: tijorat qarorida — tariflar va qaysi imkoniyat `allows()` bilan yopilishini aniqlash, ishlab chiqarish kalit juftini yaratish (`keygen --embed`), maxfiy kalitni saqlash tartibini tasdiqlash (docs/litsenziya-kaliti.md).

## Ko'rib chiqilgan muqobillar
| Variant | Nega tanlanmadi |
| --- | --- |
| Onlayn faollashtirish serveri | NFR-01 (oflayn) ga zid, server infratuzilmasi talab qiladi |
| JWT/PASETO kutubxonasi | Qo'shimcha bog'liqlik; kerakli qism (Ed25519 + JSON) `cryptography` bilan bir necha qator |
| PyNaCl yoki sof-Python Ed25519 | `cryptography` allaqachon o'rnatilgan va katalog imzosida ishlatiladi |
| HMAC (simmetrik) kalit | Tekshirish kaliti ilovada bo'lgani uchun har kim kalit yasay oladi |
| base64url matn | Qisqaroq, lekin katta-kichik harfga sezgir — qo'lda kiritishda xato ko'p; base32 tanlandi |
| Bayroqsiz, darhol majburiy | Tijorat qarori yo'q; hozirgi bepul foydalanuvchilarni bloklamaslik kerak |
