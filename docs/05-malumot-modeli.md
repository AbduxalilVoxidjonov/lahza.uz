# Ma'lumot modeli

Ikki SQLite baza (WAL rejimi). Sxemalar: `engine/src/lahza_engine/db/library.sql` va `project.sql`. Vaqt — butun son ms; matn — Unicode NFC, rasmiy imlo (ADR-0008).

```mermaid
erDiagram
  shows ||--o{ episodes : "o'z ichiga oladi"
  shows ||--o{ show_speakers : "taniydi"
  shows ||--o{ lexicon : "lug'at"
  media ||--o{ sentences : ""
  sentences ||--o{ words : ""
  media ||--o{ clips : ""
  clips ||--o{ clip_cuts : "matn orqali o'chirilgan"
  clips ||--o{ reframe_keyframes : ""
  clips ||--o{ exports : ""
  clips ||--o{ feedback : ""
```

## library.db (Kutubxona)

| Jadval | Maqsad |
| --- | --- |
| `shows` | Shou (loyiha) |
| `episodes` | Epizod: sarlavha, `project_dir`, holat (`new / analyzing / ready / failed`), `highlight_mode` (`llm / lite`, v2) |
| `show_speakers` | Shou darajasidagi spikerlar va ovoz embeddinglari (keyingi epizodlarda avtomatik tanish) |
| `lexicon` | `term`, `variants_json`, `kind` (`ism / brend / atama`), `show_id` (`NULL` — umumiy). Tahlilga `hotwords` (atamalar) va `lexicon_map` (variant → atama) bo'lib uzatiladi |
| `style_templates` | Brend shablonlari: `name`, `json` (StyleTemplate), `updated_at` (v2) |
| `settings` | Kalit-qiymat sozlamalar |

## project.db (Epizod)

| Jadval | Muhim maydonlar | Izoh |
| --- | --- | --- |
| `media` | path, hash, duration_ms, fps, width, height | Asl fayl ko'chirilmaydi, faqat havola |
| `stage_runs` | stage, version, model_id, param_hash, cache_key, status, result_path | Kesh va qayta ishga tushirish |
| `sentences` | id, start_ms, end_ms, speaker_id, text | LLM shu ID'lar bilan ishlaydi (ADR-0005) |
| `words` | sentence_id, ord, text, start_ms, end_ms, confidence, edited, original_text | `edited = 1` qayta tahlilda saqlanadi. So'z o'chirilsa/bo'linsa gap so'zlari qayta yoziladi, `ord` 0..n-1 |
| `clips` | start/end, sentence ID'lar, title, caption, hashtags_json, kind, score, scores_json, reason, status, source, user_edited | `user_edited = 1` yoki `status != nomzod` qayta tahlilda saqlanadi |
| `clip_cuts` | start_ms, end_ms | Manba vaqtida |
| `speakers` | id (= label), label, display_name | Spiker yorlig'iga foydalanuvchi bergan ism |
| `reframe_keyframes` | t_ms (chiqish vaqti), layout, cx, cy, zoom, lane (a/b), source (`avto / qolda`) | API PUT barcha kalit kadrlarni `qolda` bilan almashtiradi; eksport `qolda` ni ustun qo'yadi |
| `exports` | path, profile_json, status, error, job_id (v2), finished_at (v2) | Har eksport so'rovi: `queued → running → done / failed / cancelled` |
| `feedback` | action (qabul/rad/tahrir), metrics_json | Ball vaznlarini o'rganish (Pro) |
| `corrections` | audio_chunk_path (`cache/audio16k.wav#<start>-<end>`), before_text, after_text, media_id (v2), sentence_id (v2) | So'z tahriri: gap matni oldin/keyin (ASR'ni yaxshilash, Pro) |

## Fayl tuzilmasi

```
Library/
  library.db
  <Shou>/
    <Epizod>-<id>.lahza/
      project.db
      cache/          audio16k.wav, proxy.mp4, <bosqich>-<kalit>.json
      work/<clip>/    render ish papkasi (graph.txt, *.cmd, subs.ass) - render'dan keyin o'chiriladi
      thumbs/
```

## Migratsiya

`db/store.py`: ikki baza alohida versiyalanadi — `LIBRARY_SCHEMA_VERSION` + `LIBRARY_MIGRATIONS` va `PROJECT_SCHEMA_VERSION` + `PROJECT_MIGRATIONS` (`{versiya: SQL}`; `SCHEMA_VERSION`/`MIGRATIONS` — loyiha bazasi uchun orqaga moslik nomlari). Eski baza ochilganda avval SQLite backup API bilan `<baza>.v<N>.bak` (masalan `project.v1.bak`, `library.v1.bak`) zaxira nusxa olinadi (WAL'dagi yozuvlar ham kiradi), so'ng migratsiyalar ketma-ket qo'llanadi. Yangiroq versiyada yaratilgan baza ochilmaydi (aniq xabar). Yangi bazalar `*.sql` dan to'g'ridan-to'g'ri oxirgi versiyada yaratiladi — `.sql` va migratsiya natijasi bir xil ustunlarga ega bo'lishi testda tekshiriladi.

### v2 (M2)

| Baza | O'zgarish |
| --- | --- |
| library | `episodes.highlight_mode` (`llm / lite`); `style_templates.updated_at`; `idx_lexicon_show` indeksi |
| project | `exports.job_id`, `exports.finished_at`; `corrections.media_id`, `corrections.sentence_id` |
