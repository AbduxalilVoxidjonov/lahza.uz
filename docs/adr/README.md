# Arxitektura qarorlari (ADR)

Har bir ADR: kontekst → qaror → oqibatlar → ko'rib chiqilgan muqobillar. Qaror o'zgarsa, eski ADR o'chirilmaydi — yangisi yoziladi va eskisi "Almashtirildi: ADR-NNNN" deb belgilanadi.

| ID | Qaror | Holat |
| --- | --- | --- |
| [0001](0001-tauri-python-sidecar.md) | Tauri 2 qobig'i + Python engine sidecar | Qabul qilindi |
| [0002](0002-oflayn-model-katalogi.md) | Modellarsiz o'rnatish, imzolangan katalogdan avtomatik to'plam | Qabul qilindi |
| [0003](0003-native-runtimelar.md) | Inference uchun native runtime'lar (whisper.cpp, llama.cpp, ONNX Runtime) | Qabul qilindi |
| [0004](0004-lgpl-ffmpeg-apparat-enkoder.md) | LGPL FFmpeg + apparat enkoderlari | Qabul qilindi |
| [0005](0005-llm-gap-id.md) | LLM vaqt emas, gap ID'larini qaytaradi | Qabul qilindi |
| [0006](0006-sqlite-epizod-papkasi.md) | Har epizod — o'z papkasi va SQLite bazasi | Qabul qilindi |
| [0007](0007-ass-yagona-manba.md) | Subtitr uchun yagona manba — ASS fayl | Qabul qilindi |
| [0008](0008-ichki-imlo-rasmiy.md) | Ichki saqlash rasmiy imloda, o'girish faqat render paytida | Qabul qilindi |
| [0009](0009-sendcmd-dinamik-crop.md) | Dinamik kadr uchun FFmpeg `sendcmd` + `crop` | Qabul qilindi |
| [0010](0010-youtube-havola-import.md) | YouTube havolasidan import — yagona foydalanuvchi boshlaydigan tarmoq amali | Taklif |
| [0011](0011-deklarativ-plaginlar.md) | Montaj plaginlari — kod emas, ma'lumot (deklarativ manifest) | Qabul qilindi |
| [0012](0012-lahza-timeline.md) | Lahza Timeline — yagona montaj modeli, OpenTimelineIO bilan muvofiq | Qabul qilindi (qisman: montaj Timeline orqali; Reels klip renderi keyin o'tadi) |
| [0013](0013-haqiqiy-kadr-tamoyili.md) | "Haqiqiy kadr" tamoyili — yangi kadr generatsiya qilinmaydi | Qabul qilindi |
| [0014](0014-adobe-plaginlar.md) | Adobe plaginlari: Premiere — UXP, After Effects — CEP + ExtendScript; umumiy engine va host-reja | Taklif |
| [0015](0015-pyavsiz-asr-dekod.md) | ASR audio dekodi PyAV'siz — LGPL FFmpeg orqali numpy massiv; `av` sidecar'ga kirmaydi | Qabul qilindi |

Yangi ADR shabloni: [`0000-shablon.md`](0000-shablon.md).
