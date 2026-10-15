# ADR-0004: LGPL FFmpeg + apparat enkoderlari

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 10, 16

## Kontekst
libx264/libx265 GPL — ular FFmpeg'ni GPL'ga o'tkazadi; yopiq tijorat dasturga qo'shib bo'lmaydi. H.264 patentlari masalasi ham bor.

## Qaror
FFmpeg `--enable-gpl` siz yig'iladi (libass, freetype, harfbuzz, fribidi bilan). Kodlash — operatsion tizim/GPU enkoderlari: `h264_videotoolbox`, `h264_nvenc`, `h264_amf`, `h264_qsv`, `h264_mf`. Mavjudligi `-encoders` + 1 kadrlik sinov bilan tekshiriladi (`render/encoders.py`). libx264/mpeg4 faqat dasturchi muhiti va CI uchun.

## Oqibatlar
* NVENC'ning LGPL yig'mada `--enable-nonfree` talabi bo'yicha yurist xulosasi kerak (TZ 19-bo'lim).
* GPU'siz Windows uchun dasturiy H.264 zaxirasi — ochiq savol.
