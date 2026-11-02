# ADR-0001: Tauri 2 qobig'i + Python engine sidecar

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 3

## Kontekst
Dastur macOS va Windows'da ishlashi, kichik o'rnatuvchiga ega bo'lishi kerak. ML ekotizimi (ASR, diarizatsiya, alignment) asosan Python'da. Video preview, timeline va subtitr preview uchun web-ekotizim boy.

## Qaror
UI — Tauri 2 (Rust) ichidagi React + TypeScript. Barcha hisob — PyInstaller bilan yig'ilgan Python "Lahza Engine" sidecar jarayonida; UI u bilan faqat lokal HTTP/WebSocket API orqali gaplashadi. Sidecar'ni faqat Rust yadro ishga tushiradi va boshqaradi.

## Oqibatlar
* Engine API barqaror shartnoma: UI almashtirilsa ham engine qayta yozilmaydi; engine CLI sifatida ham ishlaydi (M1).
* Ikki jarayon: ishga tushish vaqti va qulash holatini boshqarish kerak (qayta ishga tushirish mantig'i `engine.rs` da).
* Sidecar fayli `nom-<target-triple>` ko'rinishida bo'lishi shart (Tauri talabi); NSIS'da eski sidecar qolib ketish holati qayd etilgan — CI har buildda toza yig'adi va xeshni tekshiradi.

## Ko'rib chiqilgan muqobillar
| Variant | Nega tanlanmadi |
| --- | --- |
| Electron | Yetuk, lekin o'rnatuvchi va xotira og'irroq |
| Flutter desktop | Subtitr preview va video timeline uchun tayyor kutubxonalar kamroq |
| Butunlay native (Swift + C#) | Ikki alohida UI kod bazasi — jamoa resursi ikki baravar |
