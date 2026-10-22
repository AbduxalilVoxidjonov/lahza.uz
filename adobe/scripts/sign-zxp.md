# Lahza AE panelini `.zxp` qilib imzolash (ZXPSignCmd)

Manbalar (tekshirilgan, 2026-10-22):
* ZXPSignCmd yuklab olish: <https://github.com/Adobe-CEP/CEP-Resources/tree/master/ZXPSignCMD> (papkalar `4.1.1`, `4.1.2`, `4.1.3`, `4.1.103`; eng yangisini oling).
* Buyruqlar sintaksisi: <https://github.com/Adobe-CEP/Getting-Started-guides/tree/master/Package%20Distribute%20Install>.
* Ma'lum muammo (2024-noyabr, imzo boshqa platformada "yaroqsiz" ko'rinishi): `ZXPSignCMD/KnownIssue2024.md` o'sha repoda.

Dev uchun imzo SHART EMAS — `cep-dev-install.sh`/`.ps1` (PlayerDebugMode) yetarli. Imzo — boshqalarga tarqatish uchun.

## 1. Paket papkasini tayyorlash

`.zxp` ichiga faqat ishlash uchun kerakli fayllar kiradi (`node_modules`, `src`, `test`, `.debug` — YO'Q):

```bash
cd adobe/after-effects
npm ci && npm run check            # typecheck + test + build
STAGE="$(mktemp -d)/uz.lahza.ae"
mkdir -p "$STAGE"
cp -R CSXS jsx dist index.html "$STAGE/"
```

Windows (PowerShell):

```powershell
cd adobe\after-effects
npm ci; npm run check
$Stage = Join-Path $env:TEMP "uz.lahza.ae"
New-Item -ItemType Directory -Force $Stage | Out-Null
Copy-Item -Recurse CSXS, jsx, dist, index.html $Stage
```

## 2. Sertifikat (bir marta)

O'z-o'zidan imzolangan sertifikat (Adobe Exchange'dan tashqari tarqatish uchun yetarli):

```bash
./ZXPSignCmd -selfSignedCert UZ Toshkent "Lahza Studio" "Lahza Studio" '<PAROL>' lahza-cert.p12 -validityDays 3650
```

Sintaksis: `-selfSignedCert <davlatKodi> <viloyat> <tashkilot> <commonName> <parol> <chiqish.p12> [-locality] [-orgUnit] [-email] [-validityDays]`.
`.p12` va parolni repoga qo'ymang (`adobe/after-effects/.gitignore` da `*.p12`).

## 3. Imzolash (vaqt tamg'asi bilan)

```bash
./ZXPSignCmd -sign "$STAGE" lahza-ae-0.1.0.zxp lahza-cert.p12 '<PAROL>' -tsa http://time.certum.pl/
```

Sintaksis: `-sign <kirishPapka> <chiqish.zxp> <p12> <parol> [-tsa <URL>]`. Hujjat misollaridagi TSA: `http://time.certum.pl/`,
`http://timestamp.comodoca.com/rfc3161`. Vaqt tamg'asi DOIM qo'shilsin: busiz sertifikat muddati tugagach `.zxp` o'rnatilmaydi/yuklanmaydi.

## 4. Tekshirish

```bash
./ZXPSignCmd -verify lahza-ae-0.1.0.zxp -certinfo
```

`-certinfo` — sertifikat, vaqt tamg'asi va bekor qilinganlik holati; `-skipOnlineRevocationChecks` (faqat `-certinfo` bilan).
ZXPSignCmd faqat imzoni tekshiradi, kengaytma mazmunini emas.

## 5. O'rnatish (foydalanuvchi)

* Adobe'ning `UPIA` (Creative Cloud bilan keladi) yoki uchinchi tomon ZXP o'rnatuvchilari.
* Imzolangan panel uchun PlayerDebugMode kerak emas. Agar KnownIssue2024 holatiga tushsa (bo'sh panel) — vaqtinchalik yechim
  sifatida o'sha hujjatdagi PlayerDebugMode ko'rsatmasi.
