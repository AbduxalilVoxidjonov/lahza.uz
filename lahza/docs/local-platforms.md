# Instagram va YouTube eksport profillari

2026-10-24 holatiga tekshirildi. Platforma profili fayl tayyorlashga yordam beradi;
bu uploader yoki platformada qabul qilinish kafolati emas. Akkaunt, musiqa huquqlari,
reklama joylashuvi va tavsiya algoritmi alohida shartlarga ega.

| Profil | Lahza boshlang'ich formati | Asosiy farq |
| --- | --- | --- |
| Instagram Reels | 1080×1920, 9:16, 30 fps | Tik kompozitsiya, interfeys uchun ehtiyotkor matn zonasi |
| YouTube Shorts | 1080×1920, 9:16, 30 fps | Kvadrat yoki tik, ko'pi bilan 180 soniya |
| YouTube video | 1920×1080, 16:9, 30 fps | Oddiy keng video, Shorts davomiylik chegarasi qo'llanmaydi |
| Custom | Joriy format | Eski timeline va foydalanuvchi sozlamalari bilan moslik |

1080×1920/1920×1080 va 30 fps — ilovaning boshlang'ich sozlamalari.
YouTube manba fps'ini saqlashni tavsiya qiladi; 24/25/50/60 fps kabi manba bilan
ishlasangiz formatni shunga moslang. 16:9 YouTube'ning standart player nisbati,
boshqa nisbatlarni yuklash ham mumkin.

Profilni tanlash va tavsiya etilgan formatni qo'llash alohida amallar. Davomiylik
avtomatik qisqartirilmaydi. Tik/keng formatga o'tgach kadr kesimi, matn va stiker
joylashuvini preview'da tekshiring. Safe zone chiziqlari ilovaning kompozitsiya
yo'riqnomasi; barcha qurilmalar yoki organik postlar uchun rasmiy qat'iy chegaralar emas.

YouTube Shorts'ning 180 soniya va kvadrat/tik sharti eksportdan oldin tekshiriladi.
YouTube video profilida tik/kvadrat qisqa video Shorts sifatida tasniflanishi mumkin.
Profil tanlash bu platforma tasnifini o'zgartirmaydi.

Instagram uchun 180 soniyalik qisqa kontent tavsiyasi yuklash maksimumi deb
talqin qilinmaydi. Eski 4 GB/90 soniya kabi tekshirilmagan universal chegaralar
qat'iy qoida sifatida ishlatilmaydi. Meta Help/Developers sahifalari bu tekshiruvda
429 yoki login qaytardi; ular orqali joriy organik yuklash maksimumi tasdiqlanmadi.
Reklama qoidalari va API orqali yuborish talablari organik ilova yuklashidan farq qiladi.

Rasmiy manbalar:

* [YouTube Shorts tasnifi va uch daqiqa](https://support.google.com/youtube/answer/15424877)
* [YouTube format/kodek/fps tavsiyalari](https://support.google.com/youtube/answer/1722171)
* [YouTube uzun video va akkaunt chegaralari](https://support.google.com/youtube/answer/71673)
* [Meta Reels ads: 9:16, audio va safe zone](https://www.facebook.com/business/ads/facebook-instagram-reels-ads)
* [Instagram nisbatlar yordam sahifasi — ochish cheklangan](https://help.instagram.com/1038071743007909)

Lahza videoni lokal MP4 sifatida tayyorlaydi. Platformaga kirish, avtomatik joylash,
Content ID yoki Instagram tavsiya kafolati bu profilning vazifasi emas.

Texnik manba: `render/profiles.py` — tiplangan markaziy profil metama'lumotlari va
tekshiruvlar; `GET /v1/export-profiles` hamda `POST /v1/export-profiles:check`.
`render/platform_limits.json` eski integratsiyalar uchun compatibility tavsifi;
eskirgan blog limitlari amaldagi qat'iy siyosat sifatida ishlatilmaydi.
Asl TZ'dagi Instagram limitlari haqidagi taxminlar shu sanalangan tekshiruv bilan
almashtirildi; organik Instagram yuklash maksimumini qayta tekshirish ochiq qoladi.

## Haqiqiy paket sinovi

Yig'ilgan `.app` engine'i va uning FFmpeg'i bilan foydalanuvchi videosidan 6 soniyali
uch variant chiqarildi: Reels/Shorts 1080×1920, YouTube Video 1920×1080. Har biri
30 fps, H.264 video va AAC audio ekanligi ffprobe orqali tekshirildi. Caption,
stiker va stop-kadr preview'lari ham yaratildi. Keng Shorts eksporti vazifa
navbatiga qo'yilishidan oldin 400 bilan rad etildi.

Artefaktlar (Git'ga kirmaydi): `build/local-verification/platform-report.json`,
`build/local-demo/platforms/*.mp4` va shu papkadagi JPEG preview'lar. Shorts'da
stikerning guide'dan chiqishi ogohlantirildi; ilova uni ruxsatsiz ko'chirmadi.
