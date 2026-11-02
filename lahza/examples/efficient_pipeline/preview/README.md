# Lahza: render kutmasdan preview uchun integratsiya namunasi

Bu papka production frontendga ulanmagan mustaqil **integration reference**. `app/`,
uning package/lock/config fayllari o‘zgarmaydi. Python export/cleaner bu namunaning vazifasi emas.
Bu yerda video/proxy/JPG prerender qilinmaydi. Media ochilishi, dekodlanishi va seek uchun
baribir vaqt kerak; uzluksiz 60 FPS yoki sample-exact A/V kafolati berilmaydi.

## Aniq API

`index.ts` eksportlari:

```ts
export { MontagePreview, type MontagePreviewProps } from './Preview';
export { PreviewEngine, type PreviewOptions, type PreviewState } from './engine';
export { timelineAss, type AssFactory, type AssRenderer, type JassubPort } from './ass';
export { adaptTimeline, type Interval, type SimpleColor, type PreviewPlan } from './model';
export type { MusicBuffers } from './audio';
```

| `MontagePreview` props | Kontrakt |
| --- | --- |
| `timeline` | Mavjud `app/src/api/types.ts` dagi `MontageTimeline`; ikkinchi JSON schema yo‘q |
| `revision` | `string \| number`; har editda yangilansin; immutable snapshot afzal |
| `mediaURLs` | `Readonly<Record<mediaId, string>>`; haqiqiy media baytlari URL’i |
| `sourceVAD?` | `Readonly<Record<mediaId, readonly {startMs:number; endMs:number}[]>>`; **manba** millisekundlarida |
| `musicBuffers?` | `ReadonlyMap<string, AudioBuffer>`; media ID bo‘yicha oldindan dekodlangan musiqa |
| `createAss?` | `(canvas, onError) => AssRenderer`; captions enabled bo‘lsa majburiy |
| `color?` | `{brightness:number; contrast:number; saturation:number}`; har biri 0..2; faqat preview adjustment |

`AssRenderer`: `ready: Promise<void>`, `setCurrentTime(outputMs):void`,
`setIsPaused(paused):void`, `destroy():Promise<void>`. Bu metodlar adapterimizniki.
JASSUB 2 da `setCurrentTime` metodini chaqirmaymiz: haqiqiy public API —
`manualRender({expectedDisplayTime,width,height,mediaTime}, repaint?)`.

`PreviewEngine(host, options)` imperativ API: `seek(outputMs):Promise<void>`,
`play():Promise<void>`, `pause():void`, `dispose():Promise<void>`.
Options: `plan`, `musicBuffers`, ixtiyoriy `createAss`/`color`,
`onTime(outputMs)` va `onState('seeking'|'paused'|'playing'|'error', message?)`.
`onTime` React state’ga yozilmasin: component uni bevosita slider/output DOM’iga yozadi.

## Ulanish: haqiqiy JASSUB 2 adapteri

Asosiy TypeScript tekshiruvi repo’dagi React/TS bilan ishlaydi. Preview’ni ishga
tushiradigan host React/ReactDOM va bundler bilan ta’minlanadi. **Ixtiyoriy ASS dependency —
`jassub@2.5.23`**; bu taskda paket/WASM yuklanmadi va app dependency qo‘shilmadi.
ASS kerak bo‘lmasa, `timeline.captions.enabled = false`, `createAss` berilmaydi.
Quyidagi snippet ASS kerak bo‘lgan host uchun; JASSUB importi faqat bir marta, modul boshida.

```tsx
import JASSUB from 'jassub'; // hostda pin: 2.5.23, appga bu taskda qo‘shilmagan
import { useMemo } from 'react';
import { MontagePreview, timelineAss, type AssFactory,
  type MontagePreviewProps } from './index';

type Props = Omit<MontagePreviewProps, 'createAss' | 'color'> & {
  assText: string; // Engine tayyorlagan OUTPUT-clock ASS; PlayRes/crop/format mos
  interURL: string; // Lokal, host serve qiladigan Inter.ttf
};

export function PreviewWithASS({ assText, interURL, ...props }: Props) {
  const w = props.timeline.format.w, h = props.timeline.format.h;
  const createAss = useMemo<AssFactory>(() => (canvas, onError) => {
    const instance = new JASSUB({
      canvas, // video BERMANG: source timestamps har kesimda sakraydi!
      subContent: assText,
      fonts: [interURL],
      availableFonts: { inter: interURL },
      defaultFont: 'inter',
      queryFonts: false, // lokal OS font qidirish ham yo‘q, Google Fonts ham yo‘q
      maxRenderHeight: 720,
    });
    const scale = Math.min(1, 1280 / w, 720 / h);
    return timelineAss(instance, Math.max(1, Math.round(w * scale)),
      Math.max(1, Math.round(h * scale)), onError);
  }, [assText, interURL, w, h]);
  return <MontagePreview {...props} createAss={createAss} />;
}
```

`assText` aynan shu revision uchun engine eksport qilgan ASS bo‘lsin. U allaqachon
kesim/tezlikdan keyingi **chiqish vaqtida** bo‘lishi shart. Na manba `currentTime`,
na qo‘lda yasalgan CSS caption karaoke uchun ishlatiladi. Masalan, `src=7000 ms`
bo‘lishi mumkin, ammo bu namuna timeline’da `output=2500 ms`ni libass’ga `2.5` soniya qilib beradi.

Worker va WASM lokal paket assetlaridan serve/bundle qilinadi, CDN kerak emas.
JASSUB 2.5.23 source’ining default yo‘llari: `dist/worker/worker.js`,
`dist/wasm/jassub-worker.wasm`, `dist/wasm/jassub-worker-modern.wasm`.
Bundler bu relative assetlarni ko‘chirishini tekshiring; qo‘lda serve qilinsa
paketning `dist` asset daraxtini saqlang va konstruktorga `workerUrl`, `wasmUrl`,
`modernWasmUrl` lokal URL’larini bering. README’dagi eski flat `dist/jassub-worker.*`
misollarini boshqa versiya bilan aralashtirmang.

JASSUB worker’iga kirishdan oldin `ready` kutiladi. Adapter bir vaqtning o‘zida bitta
`manualRender`ni `await` qiladi va navbatdagi eng yangi vaqtni saqlaydi; cheksiz IPC
navbati yig‘ilmaydi. `setIsPaused` worker’ning source-video soatini ishga tushirmaydi:
adapterda avtonom soat yo‘q, pauzada ham seek yangi output vaqtini yuborishi mumkin.

Rasmiy tekshirilgan API manbalari (2026-10-25):
[canvas-only README](https://raw.githubusercontent.com/ThaUnknown/jassub/master/README.md),
[public API va asset yo‘llari](https://github.com/ThaUnknown/jassub/blob/main/src/jassub.ts),
[paket versiyasi](https://github.com/ThaUnknown/jassub/blob/main/package.json).

## Media, musiqa va xavfsiz lifecycle

`mediaURLs` fayl nomi yoki `C:\\fakepath` emas. Host Tauri asset-protocol yoki
autentifikatsiyalangan lokal media endpoint orqali haqiqiy baytlarni beradi.
Endpoint seek uchun HTTP Range/206 va to‘g‘ri MIME qo‘llasin. Cross-origin bo‘lsa
`crossOrigin=anonymous` uchun aniq CORS ruxsati kerak; aks holda WebAudio jim bo‘lishi
yoki Canvas taint bo‘lishi mumkin. Token talab qilingan endpointni `<video>` header
qo‘sha olmasligini hisobga olib hostning xavfsiz URL mexanizmi bilan ulang.
Blob URL ishlatilsa u faqat host tomonidan, preview dispose bo‘lgach revoke qilinadi.

Musiqa bo‘lsa, bir marta `AudioContext.decodeAudioData` bilan olingan `AudioBuffer`ni
`new Map([[musicMediaId, decodedBuffer]])` sifatida bering. Host faqat tanlangan,
chegaralangan trekni ochsin va revisionlar orasida keshni nazorat qilsin. Bu namuna
bir trek, 120 soniya va 64 MiB PCM bilan chegaralangan; to‘liq uzun videoning audiosi
RAM’ga dekodlanmaydi. Qisqa musiqa loop qilinmaydi. Input decode context kerak bo‘lmasa
yoping; engine o‘z playback context’ini alohida ochadi.

Komponentga timeline, URL map, VAD map, music map va factory’ni stable/memoized
reference sifatida bering; o‘zgarsa yoki `revision` yangilansa engine qayta yaratiladi.
Har mountda **yangi video va ASS canvas** yaratiladi. MediaElementAudioSource bir
video element uchun faqat bir marta yaratiladi; StrictMode’da eski element qayta
ulanmaydi, oldingi OffscreenCanvas qayta transfer qilinmaydi.

Pauza/visibility/revision/unmountda play, seek, preload, rAF, rVFC, audio automation,
music source, event listener va observer to‘xtaydi. Unmountda AudioContext yopiladi,
ASS worker destroy qilinadi. Async generation/abort tekshiruvlari eski revision
kadrini yangi revisionga ko‘chirmaydi. App’ning o‘z CSP’si bu taskda o‘zgarmadi:
host `worker-src` lokal worker va `script-src` WASM compilation (odatda
`'wasm-unsafe-eval'`) hamda font/media/connect asset originlarini ruxsatlashi kerak.
COOP/COEP isolation JASSUB threading uchun tavsiya etiladi; embedder, worker va
font CORS/CORP’ni birga tekshiring. CSP’ni `*` bilan ochmang.

## Playback qoidalari

1. `VideoItem` source in/out **ms**, duration Python server bilan bir xil
   **half-even** `round((out-in)/speed)`. Masalan 1001 ms / 2 = 500 ms,
   1003 ms / 2 = 502 ms. Server davomiyligi canonical; mavjud app’dagi
   `Math.round` yordamchisi .5 da farq qiladi, u bu taskda o‘zgarmadi.
   Chiqish segmentlari ketma-ket; `[start,end)` chegarasidagi kesim keyingi klipniki.
2. Ijro vaqtining manbai — aktiv native videoning media soati. `performance.now`
   faqat JASSUB frame submission metadata’si; undan timeline hisoblanmaydi.
3. Seek/cut standby videoda bajariladi. `currentTime = target` qo‘yilishi kadr
   tayyorligini anglatmaydi: rVFC haqiqiy yaqin target kadrini bergach bufer almashadi.
   Shu paytgacha oldingi bufer/kadr va chiqish vaqti saqlanadi. 15 s timeout xato beradi.
4. Ikkita native `<video>` bor: aktiv va faqat keyingi kesimni preload qiladigan
   standby. Uchinchisi ochilmaydi. Standby DOM’da qoladi; `display:none` bilan rVFC
   tasodifan to‘xtatilmaydi. Muzlagan aktiv frame uning ustida turadi.
5. Odatdagi rejim: native DOM video + alohida ASS overlay canvas. Videoni yana Canvas’ga
   ko‘chirish yo‘q. Faqat `color` berilganda Canvas2D `drawImage` ishlaydi, video
   rVFC’ining yangi dekodlangan kadrlarida; resize’da oxirgi kadr qayta chiziladi.
   Backing store <=1280×720, **DPR=1**; landscape va portrait shu bounding box’ga sig‘adi.
   ASS `manualRender` o‘lchamlari ham shu box’ga adapter ichida cheklanadi;
   script PlayRes saqlanadi, 4K output uchun 4K worker render talab qilinmaydi.
   Bu decode resolution’ni kamaytirmaydi: 4K source hali 4K decode bo‘lishi mumkin.
6. rAF faqat yengil playhead/boundary boshqaradi, React `setState` 60 Hz ishlamaydi.
   Slow seek/stall vaqtida audio musiqa ham to‘xtaydi, davom etganda qayta anchor olinadi.
   Native seek va rAF bilan kesimda taxminan kadr miqyosidagi kechikish/overshoot
   bo‘lishi mumkin; bu eksport aniqligi haqidagi va’da emas.

## Audio va qo‘llanadigan chegaralar

Source VAD intervallari har klip bilan intersect qilinadi va speed bilan outputga
o‘tkaziladi; takroriy kliplar ham alohida map qilinadi. Source gain/mute, global fade,
musiqa gain/fade va VAD nutq davridagi ducking ishlaydi. Duck default: -12 dB,
30 ms attack, 180 ms release; qisqa tanaffuslar hangover bilan birlashtiriladi.
100 Hz control curve **start/resume/cut paytida** oldindan tuziladi, WebAudio audio
thread’ida ijro qilinadi. Har frame audio RMS/compressor hisoblash yoki polling yo‘q.

Bu **FFmpeg `sidechaincompress`ning dynamic compressor’i bilan teng emas**.
Sample-exact parity uchun alohida AudioWorklet PCM mixer kerak: bitta sample clock,
shu threshold/ratio/knee, attack/release detector recurrence, resampler va lookahead;
keyin FFmpeg fixture audio bilan qiyoslash. Bu yerda bunday parity implementatsiya
qilinmagan; HTMLMediaElement+WebAudio anchoring sample-exact deb ko‘rsatilmaydi.

Qo‘llanadi: cut-only video, 0.25–4× speed (`preservesPitch` native sifati), statik
center/manual crop, source mute/gain, bitta qisqa musiqa, haqiqiy output-clock ASS.
Duration <=10 min. `color` brightness/contrast/saturation — aniq belgilangan
**preview-only** Canvas filtrlari; FFmpeg rang fazosi/HDR/rang presetlari bilan
vizual tenglik bildirmaydi va export JSON’ga yozilmaydi.

Aniq rad etiladi: transition/crossfade, freeze/FX, global FFmpeg rang preseti/LUT,
auto/focus/blur reframe, text card, stiker, logo, LUFS, ko‘p musiqa. Unsupported narsa
sezdirmay tashlab ketilmaydi. GPU LUT/WebGL2 bu misolda yo‘q; haqiqiy 3D texture LUT
shader + colorspace transform yozilmaguncha LUT uchun render preview fallback kerak.

Native codec/container, rotation/SAR, HDR va rVFC mavjudligi hostga bog‘liq.
Native dekoder qo‘llamaydigan media uchun **fallback transcode/proxy saqlanadi**;
proxies’dan barcha kompyuterlarda butunlay voz kechish mumkin emas. Mehnati kam
mos format yo‘li tez, lekin seek ayniqsa uzun GOP’da sekinlashishi mumkin.
Past resurs rejimida software decode/yuqori resolution source uchun 720p bir martalik
proxy ham foydaliroq bo‘lishi mumkin. Hardware GPU’dagi to‘liq filtergraph va’dasi yo‘q.

## Tekshirish

Repo root’dan (yangi npm install kerak emas):

```sh
node app/node_modules/typescript/bin/tsc -p examples/efficient_pipeline/preview/tsconfig.json
node --test examples/efficient_pipeline/preview/tests.mjs
```

Testlar vaqtinchalik OS papkasiga CommonJS emit qiladi va uni o‘chiradi; source/package
o‘zgarmaydi. 9 test: mapping/rounding/boundary, VAD speed/repeat, attack/release,
crop, unsupported rejection va ASS serialized/backpressure/dispose scheduling.
ASS testidagi port — scheduling test double, haqiqiy libass emulyatsiyasi emas.

Strict TS typecheck, pure testlar va Vite library bundle tekshirildi. Alohida lint
konfiguratsiyasi yo‘q. **Jonli brauzer/Tauri, haqiqiy worker/WASM render, audio ijrosi
va FPS/issiqlik profiling bajarilmadi.** Integratsiyada tekshiring: paused seek,
ketma-ket tez scrub, sekin Range response, network stall, 0.25×/4× cut, background tab,
revision/StrictMode remount, autoplay rejection, CORS/CSP, unsupported kodek fallback.
