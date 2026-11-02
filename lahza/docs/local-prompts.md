# Qisqa montaj promptlari

Montaj muharriridagi prompt maydoni lokal buyruqlardan tahrir rejasini tuzadi.
Bu sahifa **Lokal buyruqlar** rejimiga tegishli. Alohida **AI yordamchi** rejimi
haqiqiy lokal modeldan foydalanadi: [AI ko'rsatmalar](local-ai-editing.md).
Hozir bu chegaralangan buyruq yordamchisi: erkin ijodiy matnni tushunadigan LLM
o'rnatilgan deb da'vo qilinmaydi. Tarmoq so'rovi, skript ishga tushirish yoki fayl
yuklash bajarilmaydi. Tushunilmagan buyruq ochiq ko'rsatiladi.

Ishlatish:

1. Montajni oching. Stop-kadr kerak bo'lsa tegishli videoni tanlang.
2. Qisqa buyruq yozing, masalan:

   ```text
   reels formati; subtitr kattaroq
   tanlangan klipning 3-soniyasida 1 soniya stop-kadr
   iliq rang
   subtitr "Yangi lavha" 1s–3s
   ```

3. Reja tugmasini bosing: format, caption va effekt o'zgarishlari ko'rsatiladi.
4. Natijani qo'llang. Barcha o'zgarishlar bitta undo qadami bo'ladi; so'ng
   preview'ni ko'ring va saqlang.

`reels formati`, `shorts formati`, `youtube formati` — muqobil tanlovlar; bir
promptda zid formatlarni bermang. Format prompti platforma profilini va uning
tavsiya etilgan kadrini qo'llaydi, davomiylikni o'zi kesmaydi.

`subtitr yoq/o'chir` va `subtitr kattaroq/kichikroq` haqiqiy ASR karaoke
captionlarini boshqaradi. Qo'lda kiritilgan matn/SRT elementlari alohida qatlamlar;
ularning ko'rinishi inspektorda tahrirlanadi. Qo'shilgan yangi caption vaqti umumiy
montaj vaqtiga, stop-kadr vaqti esa tanlangan klipning chiqish vaqtiga tegishli.
Tezlik va manba chegaralari hisobga olinadi; yaroqsiz yoki ustma-ust freeze rad etiladi.

Prompt rejasidan keyin timeline, tanlov yoki prompt o'zgarsa, reja qayta tuzilishi
kerak. Tushunilmagan yoki zid buyruq bo'lsa, qisman o'zgarishlar jim qo'llanmaydi.
Muharrirdagi `Misollar` bo'limi aynan qo'llanadigan buyruqlarni ko'rsatadi.

Tabiiyroq yozuvlar ham bor: `videoni Reels formatida qil`,
`captionni kattalashtir`, `3-soniyada stop-kadr qo'y` (tanlangan klipda standart
1 soniya). `iliq rang`/`warm color` va `kino rangi`/`cinematic color` rendererning
tekshirilgan warm/film presetlariga ulanadi. Buyruqlarni nuqtali vergul yoki yangi
qator bilan ajratish eng aniq; qo'shtirnoq ichidagi matn o'z holicha saqlanadi.

Haqiqiy sinovda UI parseri Reels + 72→80 px caption + klipning 7-soniyasida
1 soniyali freeze + warm rang rejasini yaratdi. Shu timeline yig'ilgan `.app`
engine'ida MP4/SRT sifatida eksport qilindi; namunaga `gentle-zoom` skill'i ham
qo'llangan. Artefaktlar: `build/local-verification/prompt-plan.json`,
`build/local-verification/prompt-flow-report.json`,
`build/local-demo/packaged-export/lahza-prompt-demo.mp4`.

Butun montajni erkin tabiiy tildan yaratish, o'zboshimcha Adobe plaginini chaqirish,
musiqa qidirish yoki barcha ijodiy topshiriqlarni bajarish bu lokal yordamchiga kirmaydi.
