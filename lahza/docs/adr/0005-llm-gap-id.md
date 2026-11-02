# ADR-0005: LLM vaqt emas, gap ID'larini qaytaradi

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 7

## Kontekst
Kichik lokal modellar soniyalarni o'ylab topishga moyil. Vaqt xatosi so'z o'rtasida kesishga olib keladi.

## Qaror
Transkript gaplarga bo'linadi va LLM'ga `ID | spiker | davomiylik | matn` ko'rinishida beriladi. LLM faqat `start_id`, `end_id`, `hook_id` qaytaradi; javob llama-server'da JSON sxema bilan cheklanadi va pydantic bilan qayta tekshiriladi. Vaqtga aylantirish va chegaralarni pauza bo'yicha tekislash — kod (`highlight/boundaries.py`).

## Oqibatlar
* "So'z kesilmaydi" kafolati kod darajasida (testlar bilan).
* Gaplarga bo'lish sifati highlight sifatiga ta'sir qiladi — `text/sentences.py` parametrlari R0'da sozlanadi.
