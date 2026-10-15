# Baholash (R0 va har reliz)

Bu papka — modellarni **o'z podkastlarimizda** o'lchash uchun (TZ 5, 7, 15-bo'limlar). Audio va video repozitoriyga kiritilmaydi (`.gitignore`), faqat izohlar va natijalar.

```
eval/
  YORIQNOMA.md                 transkripsiya yo'riqnomasi (etalon matn qanday yoziladi)
  data/
    uzpodcast/                 <id>.wav + <id>.txt (etalon transkript)
    align/                     <id>.wav + <id>.words.json  [{"text", "start_ms", "end_ms"}]
    highlight/                 <epizod>.gold.json  [{"annotator", "start_ms", "end_ms"}]
  results/                     <model_id>.json - o'lchov natijalari
  run_asr_eval.py              WER, CER, RTF
  run_align_eval.py            so'z chegarasi xatosi (median, p95)
  run_highlight_eval.py        precision@k, topish ulushi
```

## ASR

```bash
python eval/run_asr_eval.py --data eval/data/uzpodcast --hyp-dir /tmp/hyp --model-id asr-piyola-v2
```

`--hyp-dir` — modelning `<id>.txt` chiqishlari (model qaysi runtime'da ishlatilgani muhim emas). Agar `--engine-asr` berilsa, skript o'rnatilgan engine ASR'ini o'zi chaqiradi va vaqtni o'lchab RTF hisoblaydi.

## Qaror qoidasi (TZ 5-bo'lim)

Daraja bo'yicha tezlik maqsadiga sig'adigan modellar ichidan eng past WER — asosiy; eng tezi — zaxira. Natija katalogda `eval.score` sifatida yoziladi (`docs/06-model-katalogi.md`).
