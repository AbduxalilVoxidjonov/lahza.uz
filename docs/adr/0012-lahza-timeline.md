# ADR-0012: Lahza Timeline — yagona montaj modeli, OpenTimelineIO bilan muvofiq

* Holat: Qabul qilindi — qisman (2026-10-20): montaj Timeline orqali (`montage/model.py`, `render/montage_render.py`); Reels klip renderi keyin o'tadi
* Sana: 2026-10-18
* TZ bo'limi: [`11-montaj-platformasi.md`](../11-montaj-platformasi.md) 7, 10.2

## Kontekst

Hozir klip `clips` + `clip_cuts` + `reframe_keyframes` jadvallarida saqlanadi va `render/graph.py` dagi `RenderJob` orqali render qilinadi. Yangi talablar uchun bu yetarli emas:

* bir nechta manba (multicam, video to'plami);
* plaginlar va o'tishlar;
* musiqa treki;
* montaj dasturlariga eksport (FCP7 XML, OTIO, EDL);
* montaj hisoboti (`_edl.json`).

Tekshirilgan faktlar:

* **OpenTimelineIO** — ASWF, Apache-2.0, PyPI'da bor (oxirgi reliz 0.18.1) ([repo](https://github.com/AcademySoftwareFoundation/OpenTimelineIO), [PyPI](https://pypi.org/project/OpenTimelineIO/)).
* **Adapterlar.** FCP7 XML va CMX 3600 adapterlari `OpenTimelineIO-Plugins` paketida ([adapterlar](https://opentimelineio.readthedocs.io/en/latest/tutorials/adapters.html)). FCPXML adapteri o'tish, effekt va rangni o'tkazmaydi ([otio-fcpx-xml-adapter](https://github.com/OpenTimelineIO/otio-fcpx-xml-adapter)).
* **Montaj dasturlari.** DaVinci Resolve OTIO'ni 18.5 dan import qiladi. Premiere Pro, Resolve va Filmora FCP7 XML'ni import qiladi. Premiere FCPXML'ni ochmaydi. Manbalar [`11-montaj-platformasi.md`](../11-montaj-platformasi.md) 7-bo'limida.

## Qaror

* **Bitta model.** `lahza.timeline/1` JSON modeli preview, render, NLE eksporti va montaj hisoboti uchun yagona manba bo'ladi.
* **Vaqt** millisekundda saqlanadi. Kadrga moslash render va eksport bosqichida fps bo'yicha bajariladi.
* **OTIO muvofiqligi.** Model OTIO'ga yo'qotishsiz o'giriladi (trek, klip, o'tish, metadata). Lahza'ga xos maydonlar `metadata["lahza"]` da saqlanadi. FCP7 XML va EDL OTIO adapterlari orqali yoziladi.
* **Saqlash.** Timeline `project.db` dagi `timelines` jadvalida versiyali JSON sifatida turadi. Qo'lda tahrir `user_edited` bilan belgilanadi.
* **Render.** `render/graph.py` Timeline → FFmpeg graf kompilyatoriga aylanadi. Hozirgi `RenderJob` uning xususiy holati bo'ladi va regressiya testlari saqlanadi.

## Oqibatlar

* Multicam, retsept, avtomontaj va NLE eksporti bitta model ustida quriladi.
* Migratsiya kerak: mavjud kliplar Timeline'ga o'giriladi. `clips` jadvali galereya uchun qoladi.
* OTIO adapterlari alohida paketlarda, shuning uchun versiyalari `engine/pyproject.toml` da mahkamlanadi.
* Ba'zi Lahza effektlari formatlarda ifodalanmaydi. Ular pishirilgan qatlam sifatida eksport qilinadi.

## Ko'rib chiqilgan muqobillar

| Variant | Nega tanlanmadi |
| --- | --- |
| OTIO'ni to'g'ridan-to'g'ri ichki model qilish | Lahza'ga xos tuzilmalar (trigger, retsept, reframe kalit kadrlari) metadata ichida qoladi va validatsiya qiyinlashadi; ichki model OTIO'ga o'girilishi yetarli |
| Har eksport formatiga alohida generator | Takrorlanish; OTIO adapterlari tayyor va keng ishlatiladi |
| Hozirgi `RenderJob` ni kengaytirish | Ko'p manba va trek tushunchasi yo'q |
