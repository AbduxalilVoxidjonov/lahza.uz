# Transkripsiya yo'riqnomasi (etalon matn uchun)

Etalon transkriptlar bir xil qoidada yozilmasa, WER raqamlari solishtirib bo'lmaydigan bo'lib qoladi. Har bir transkript ikki kishi tomonidan tekshiriladi.

## Umumiy

1. Eshitilgan narsani yozing — "to'g'rilangan" yoki adabiy variantini emas. Sheva so'zlari aytilganidek, lotin yozuvida.
2. Yozuv: o'zbek lotin, amaldagi rasmiy imlo. Oʻ/Gʻ uchun ʻ (U+02BB), tutuq uchun ʼ (U+02BC). Klaviaturada `'` yozilsa ham bo'ladi — baholashdan oldin `normalize()` hammasini bir xil qiladi.
3. Har spiker almashganda yangi qator: `[A] matn…`, `[B] matn…`.
4. Gap oxirida tinish belgisi: `.`, `?`, `!`. Vergul ixtiyoriy (WER'da hisobga olinmaydi).

## Raqamlar

5. Raqamlar **so'z bilan**, aytilganidek: "ikki ming yigirma oltinchi yil", "o'n besh foiz". (Ba'zi modellar raqam chiqaradi, ba'zilari so'z — raqam→so'z normallashtirish R0 vazifasi; etalon har doim so'zda.)

## Chet so'zlar va aralash nutq

6. Rus va ingliz so'zlari **o'zbek lotin yozuvida, eshitilganidek**: "voobshe", "startap", "kontent". Brend va ismlar umumiy qabul qilingan yozuvda: "Instagram", "YouTube".
7. Butun gap boshqa tilda bo'lsa — o'sha tilning lotin transliteratsiyasida, boshiga `{ru}` yoki `{en}` belgisi.

## Nutqdan tashqari tovushlar

8. To'ldiruvchilar yoziladi: `ee`, `mm`, `aa`.
9. Kulgi, olqish, musiqa — kvadrat qavsda: `[kulgi]`, `[olqish]`, `[musiqa]`. WER hisobida e'tiborga olinmaydi, lekin kulgi detektorini baholashda ishlatiladi.
10. Tushunib bo'lmaydigan joy: `[tushunarsiz]`. Ustma-ust gapirish: ikkala spikerni ham alohida qatorda, oldiga `[ustma-ust]`.

## So'z chegaralari (Align-Eval)

11. Chegaralar to'lqin shaklida, so'z birinchi tovushining boshi va oxirgi tovushining oxiri bo'yicha qo'yiladi; nafas va pauza so'zga kirmaydi.

## Highlight belgilash (UzHighlight-Eval)

12. Har mutaxassis epizodni mustaqil ko'radi va 5–10 ta "Reels uchun yaxshi" lahzani belgilaydi: boshlanish va tugash (gap chegarasida), qisqa sabab, 1–5 baho.
13. Boshqa mutaxassislarning belgilarini ko'rmaydi.
