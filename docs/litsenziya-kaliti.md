# Oflayn litsenziya kaliti (V1-3)

TZ 19-bo'lim ("Litsenziyalash, tijorat versiya bo'lsa"), qaror: [ADR-0016](adr/0016-oflayn-litsenziya-kaliti.md). API: [04-engine-api.md → Litsenziya](04-engine-api.md#litsenziya-v1-3-adr-0016).

> **Holat:** kod to'liq, lekin **standart holatda O'CHIQ**. Tijorat qarori (tariflar, sinov muddati, narx) hali qabul qilinmagan. Bayroq o'chiq bo'lsa ilova hozirgidek bepul ishlaydi, hech narsa tekshirilmaydi va bloklanmaydi, Sozlamalardagi "Litsenziya" paneli ko'rinmaydi.

## Yoqish

* Engine: `Settings.licensing_enabled` (`engine/src/lahza_engine/config.py`). Dasturchi sinovi: `LAHZA_LICENSING=1`.
* Ochiq kalit build'ga kiritilmagan bo'lsa (`licensing/keys.py` → `PRODUCTION_PUBLIC_KEYS = ()`), holat `not_configured` — bloklamaydi.
* Hozircha hech bir imkoniyat litsenziyaga bog'lanmagan. Kelajakda pullik imkoniyat `LicenseManager.allows()` orqali tekshiriladi (bayroq o'chiq bo'lsa doim `True`).

## Kalit formati

Payload (JSON, `LicensePayload`):

| Maydon | Ma'nosi |
| --- | --- |
| `v` | format versiyasi (`1`) |
| `id` | litsenziya raqami (chiqaruvchi jurnali uchun) |
| `licensee` | litsenziat (egasi) |
| `edition` | nashr/tarif (masalan `pro`) |
| `issued` | berilgan sana (`YYYY-MM-DD`) |
| `expires` | amal qilish muddati (shu kun oxirigacha, UTC) yoki `null` — abadiy |
| `max_devices` | qurilmalar soni — ma'lumot uchun (oflayn sanab bo'lmaydi), ixtiyoriy |
| `devices` | qurilma barmoq izlari; bo'sh bo'lmasa kalit faqat shu kompyuterlarda ishlaydi |
| `min_version`, `max_version` | dastur versiyasi oralig'i (ikkalasi ham kiritilgan), ixtiyoriy |

Ikkilik ko'rinish: `raw = 0x01 || zlib(kanonik JSON)`, `imzo = Ed25519(DOMAIN || raw)` (`DOMAIN = "lahza-license/1\0"`), `blob = raw || imzo(64 bayt)`.
Matn: `LAHZA-` + base32 (RFC 4648, `=` siz), 5 belgilik guruhlar — masalan `LAHZA-AF4NU-TOOYE-FMEMA-…` (~400 belgi; nusxalab qo'yish uchun). Kiritishda katta-kichik harf, bo'shliq, qator ko'chishi va `-` farq qilmaydi; `0/1/8` → `O/I/B` tuzatiladi. Imzo payload ochilishidan oldin tekshiriladi.

Qurilma barmoq izi: OS mashina ID'si (macOS `IOPlatformUUID`, Windows `MachineGuid`, Linux `machine-id`) ning `sha256` xeshidan 16 belgi (`ABCD-EFGH-IJKL-MNOP`). Xom ID saqlanmaydi. Panelda va `license_issue.py device` buyrug'ida ko'rinadi.

## Tekshirish tartibi (engine)

1. Format va imzo (`licensing/keyformat.py`) — ishonchli ochiq kalitlardan biri bilan.
2. Qurilma (`devices` bo'lsa) → versiya oralig'i → muddat → `issued` kelajakda emasmi (48 soat tolerans).
3. **Soat himoyasi:** ko'rilgan eng katta vaqt (`license_clock.last_seen`) saqlanadi, faqat oldinga siljiydi. Muddatli kalitda joriy vaqt undan 48 soatdan ko'proq orqada bo'lsa — `clock_rollback` (soat to'g'rilanganda o'zi tiklanadi). Abadiy kalitga ta'sir qilmaydi. Bu oddiy to'siq, kuchli himoya emas.
4. Saqlash: `library.db` → `settings` (`license` — kalit matni va faollashtirilgan vaqt; `license_clock`). Har ishga tushishda saqlangan kalit qayta tekshiriladi.

## Kalit jufti va chiqarish

```bash
# 1) Bir marta: kalit jufti (maxfiy kalit REPOZITORIYDAN TASHQARIDA)
python scripts/license_issue.py keygen --out ~/.lahza-keys --embed
#    --embed ochiq kalitni engine/src/lahza_engine/licensing/keys.py ga qo'shadi -> commit qiling

# 2) Kalit chiqarish
python scripts/license_issue.py issue --key ~/.lahza-keys/license_signing.key \
  --licensee "Mijoz MChJ" --edition pro --expires 2027-12-31 \
  --max-devices 3 --min-version 1.0.0 --max-version 1.99.99 --log ~/.lahza-keys/issued.jsonl
#    abadiy: --perpetual; qurilmaga bog'lash: --device ABCD-EFGH-IJKL-MNOP (takrorlanadi)

# 3) Tekshirish
python scripts/license_issue.py verify "LAHZA-…"            # keys.py dagi kalitlar bilan
python scripts/license_issue.py verify "LAHZA-…" --pub <b64> # boshqa ochiq kalit
python scripts/license_issue.py device                      # shu kompyuter barmoq izi
```

`--log` jurnaliga faqat payload yoziladi (kalit matni emas) — qaysi kalit kimga berilganini kuzatish uchun.

## Maxfiy kalitni saqlash

* Maxfiy kalit (`license_signing.key`, base64, 32 bayt) **hech qachon repozitoriyga kirmaydi**: `.gitignore` da `*.key` va `.lahza-keys/`. Fayl `0600` huquq bilan yoziladi.
* Asosiy nusxa — parol menejeri yoki shifrlangan oflayn tashuvchi (kamida 2 nusxa, alohida joylarda). CI'ga kerak bo'lsa — faqat sir (secret) sifatida.
* Kalit chiqib ketsa: yangi juft yarating (`keygen --embed`), eski ochiq kalitni `PRODUCTION_PUBLIC_KEYS` dan **keyingi relizda** olib tashlang; buni qilsangiz eski kalit bilan chiqarilgan litsenziyalar ham yaroqsiz bo'ladi — mijozlarga yangi kalit qayta chiqariladi.
* Rejali almashtirish: yangi ochiq kalitni qo'shing, eskisini qoldiring — avvalgi litsenziyalar ishlashda davom etadi.
* Test kaliti (`keys.TEST_PUBLIC_KEY`) maxfiy urug'i kodda ochiq (`testing_private_key()`); u faqat testlarda qo'lda beriladi va `trusted_keys()` ga hech qachon kirmaydi.

## Cheklovlar

* Oflayn tizimni dastur kodini o'zgartirib chetlab o'tish mumkin — maqsad halol foydalanuvchini tartibga solish, DRM emas.
* `max_devices` oflayn sanalmaydi; qat'iy bog'lash kerak bo'lsa `--device` ishlatiladi.
* Kalit bekor qilish (revocation) ro'yxati yo'q — tarmoqsiz buning imkoni cheklangan; kerak bo'lsa keyingi versiyada `keys.py` yonida bekor qilingan `id` ro'yxati qo'shiladi.
