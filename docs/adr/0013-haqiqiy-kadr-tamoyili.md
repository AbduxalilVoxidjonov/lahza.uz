# ADR-0013: "Haqiqiy kadr" tamoyili — Lahza yangi kadr generatsiya qilmaydi

* Holat: Qabul qilindi (2026-10-20; `_edl.json` da `"haqiqiy_kadr": true`)
* Sana: 2026-10-18
* TZ bo'limi: [`11-montaj-platformasi.md`](../11-montaj-platformasi.md) 1, 8

## Kontekst

Talab: Higgsfield'dan namuna olish, lekin farqi bilan — yo'q narsani bor qilish emas, mavjud kadrlarni montaj qilish. Higgsfield esa kalit kadr va promptdan yangi video generatsiya qiladi. Uning video muharriri ham yuklangan klipni generativ modellar bilan o'zgartiradi ([ai-video-editor](https://higgsfield.ai/ai-video-editor), [DoP](https://higgsfield.ai/creator-hub/help-center/ai-models/how-do-i-use-dop)).

## Qaror

Lahza chiqargan har bir piksel quyidagi ikki manbadan biridan keladi:

* foydalanuvchi bergan videoning deterministik o'zgartirilgani: kesish, vaqt, crop/zoom/pan/aylantirish, rang, aralashtirish, xiralashtirish, kompozitsiya;
* grafik qatlam: matn, subtitr, logo, shakl yoki foydalanuvchi bergan rasm.

**Taqiqlanadi:** matndan yoki rasmdan video, outpainting, yuz almashtirish, lab-sinxron, ovoz klonlash, yangi odam yoki obyekt qo'shish.

**Ehtiyotkor toifa** (standart holatda o'chiq, eksport hisobotida belgilanadi): oraliq kadr sintezi (slow-motion), keyinchalik super-resolution.

AI faqat tushunish va qaror qilish uchun ishlatiladi: ASR, diarizatsiya, highlight, kadr tasnifi, effekt joyini tanlash.

## Oqibatlar

* Har eksport bilan birga `_edl.json` montaj hisoboti beriladi; har bir kadrni manbasigacha kuzatish mumkin.
* Bitta kirish va bitta retsept doim bir xil natija beradi; generatsiya xarajati va "qayta generatsiya" yo'q.
* Ba'zi kamera harakatlari (orbit, bullet time, dolly zoom) qilinmaydi, chunki ular yangi nuqtai nazarni talab qiladi.
* CI testi render grafida generativ komponent yo'qligini va faqat oq ro'yxatdagi filtrlar borligini tekshiradi.

## Ko'rib chiqilgan muqobillar

| Variant | Nega tanlanmadi |
| --- | --- |
| Generativ modullarni ixtiyoriy plagin qilish | Mahsulot farqini yo'qotadi; oflayn apparatda og'ir; huquqiy va axloqiy xavf (yuz, ovoz) |
| 9:16 uchun outpainting | Mavjud yo'l (focus, split, xira fon) yetarli, va u kadrni "o'ylab topmaydi" |
