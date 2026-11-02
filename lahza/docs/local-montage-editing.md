# Lokal montajni qo'lda tahrirlash

Montajni oching, timeline'dan video, matn yoki stikerni tanlang. Preview engine'ning
haqiqiy kadrini ko'rsatadi; saqlanmagan tahrir ham preview'ga yuboriladi. Hozir bu
kadrli preview: uzluksiz ijro va ovoz to'lqini mavjud emas.

## Captionlarni tuzatish

* `Subtitr qo'shish` vaqtli matn qatlamini yaratadi. Matn, boshlanish/tugash,
  joylashish va ko'rinishini tanlangan element inspektorida o'zgartiring.
* `Transkript so'zlari` bo'limida ASR so'zlarini va ularning millisekunddagi
  vaqtlarini tuzating. Asl matn `original_text` maydonida saqlanadi.
* SRT import alohida vaqtli matn elementlarini yaratadi. SRT'da so'z vaqti yo'q,
  shuning uchun u avtomatik karaoke so'zlariga aylantirilmaydi.

## Video bo'laklari

* Inspektorda manba boshlanishi/tugashi, tezlik, ovoz va tartibni o'zgartirish,
  nusxalash yoki o'chirish mumkin.
* `Ko'rsatkichda bo'lish`: videoni tanlab, ko'rsatkichni uning ichiga qo'ying.
  Ikki bo'lak bir xil manbaga tayanadi; tezlik va manba vaqti hisobga olinadi.
* FX mavjud klip yoki o‘tish ichida bo'lish bloklanadi. Avval FXni olib tashlash
  yoki kesish nuqtasini ko'chirish kerak. Bu noto'g'ri ko'rinishni jim saqlamaydi.
* `Oraliqni yopib o'chirish`: tanlangan klip ketadi, keyingi video bo'laklari va
  caption/matn/stiker vaqtlari oldinga suriladi. O'chirilgan oraliq ichidagi
  overlay olib tashlanadi, kesishganlari qisqaradi. Musiqa o'z joyida qoladi.
  Qo'shni o'tishlar bo'lsa bu amal bloklanadi.
* Oddiy `O'chirish` faqat tanlangan elementni olib tashlaydi; global caption,
  matn va stiker vaqtlarini moslab surmaydi. Trim va tartib almashtirishdan keyin
  ushbu qatlamlarning vaqtlarini tekshiring.

## Tarix va saqlash

Undo/redo tugmalari yoki Cmd/Ctrl+Z va Cmd/Ctrl+Shift+Z bilan 100 qadamgacha
qaytish mumkin. Matn maydonida bu tugmalar odatiy matn undo'sini bajaradi.
`Saqlash` timeline'ni lokal kutubxonaga yozadi; eksport saqlangan tahrirni oladi.
Tarix joriy muharrir sessiyasi uchun; ilovani qayta ochganda undo tarixi tiklanmaydi.

Tekshiruv: `cd app && node --test tests/montage-edit.test.mjs`,
`npm run typecheck`, `npm run build`. Desktop oynasida to'liq interaktiv sinov
hali bajarilmagan; [lokal alfa holati](local-alpha.md)ga qarang.
