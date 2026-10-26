# 15b. Lahza MCP server (`lahza-engine mcp`)

> "Claude montaj" bo'limining MCP qismi. Ro'yxatdan o'tkazish (`claude mcp add`, Claude Desktop
> konfiguratsiyasi) va Claude planner'i — `docs/15-claude-montaj.md`. Kod:
> `engine/src/lahza_engine/mcp_server/`, testlar: `engine/tests/test_mcp_server.py`.

## 1. Nima va qanday ishlaydi

`lahza-engine mcp` (dev muhitda `lahza mcp` yoki `python -m lahza_engine mcp`) — **stdio MCP
server**. Claude Code yoki Claude Desktop uni bola jarayon sifatida ishga tushiradi va stdin/stdout
orqali MCP JSON-RPC 2.0 xabarlarini (har qatorda bitta JSON) almashadi.

* **Engine ichida ishlamaydi.** Har chaqiruvda ishlayotgan engine discovery fayli
  `<data_dir>/engine.json` orqali topiladi (`service.runtime.find_live_engine`: pid tirik +
  `/v1/health` token bilan 200). So'ng `http://127.0.0.1:<port>` HTTP API'ga
  `Authorization: Bearer <token>` bilan murojaat qilinadi. Token hech qachon tool javobiga yoki
  logga chiqmaydi. Tizim proksisi chetlab o'tiladi.
* Engine topilmasa — har tool `isError: true` bilan aniq matn qaytaradi:
  "Lahza engine topilmadi (ishlamayapti). Lahza Studio'ni oching yoki `lahza-engine install-service`
  qiling." Engine qayta ishga tushsa (yangi port/token), server avtomatik qayta topadi.
* `data_dir` — `LAHZA_DATA_DIR` yoki tizim standarti; `--data-dir D` bilan almashtiriladi.
* **stdout faqat protokol uchun.** Ishga tushganda `sys.stdout` stderr'ga yo'naltiriladi; barcha
  loglar (`lahza-mcp ...`) stderr'da.
* Bog'liqliksiz minimal implementatsiya (venv'da rasmiy `mcp` paketi yo'q, pyproject o'zgarmagan).

### Protokol

| Metod | Javob |
|---|---|
| `initialize` | `protocolVersion` muzokarasi: `2025-06-18`, `2025-03-26` qo'llanadi; boshqa versiya so'ralsa `2025-06-18` taklif qilinadi. `capabilities: {tools: {listChanged: false}}`, `serverInfo`, `instructions` |
| `notifications/initialized`, `notifications/cancelled` | javob yo'q |
| `ping` | `{}` |
| `tools/list` | 13 tool, har biri `inputSchema` (JSON Schema, `additionalProperties: false`) va `annotations` bilan |
| `tools/call` | `{content: [...], isError}`; argumentlar sxema bo'yicha tekshiriladi |
| noma'lum metod | `-32601`; buzuq JSON `-32700`; noto'g'ri so'rov/batch `-32600`; noma'lum tool `-32602` |

## 2. Tool'lar

| Tool | API endpoint(lar) | Annotatsiya | Tavsif |
|---|---|---|---|
| `lahza_status` | `GET /v1/health` | readOnly | Ulanish, engine versiyasi, qo'llanadigan tahrir operatsiyalari, eksport papkasi |
| `list_projects` | `GET /v1/projects` | readOnly | Loyihalar (id, name) |
| `list_episodes` | `GET /v1/projects/{id}/episodes` | readOnly | Epizodlar (id, title, status) — papka yo'llarisiz |
| `list_montages` | `GET /v1/montages[?project_id=]` | readOnly | Montajlar (tahrirlanadigan timeline'lar) |
| `list_clips` | `GET /v1/episodes/{eid}/clips` | readOnly | Kliplar: vaqt, sarlavha, ball, holat; `status` filtri, `offset/limit` (≤100) |
| `get_transcript` | `GET /v1/episodes/{eid}/transcript` | readOnly | Gaplar (id, vaqt, speaker, matn); `offset/limit` (≤200), `max_chars` (≤50 000), `start_ms/end_ms` oynasi, `next_offset` |
| `get_timeline` | `GET /v1/montages/{mid}` | readOnly | Editing-agent'ga beriladigan chegaralangan tavsif (`planner.compact_context`: media yo'llarisiz, ≤12 000 belgi) + `base_revision` (`executor.revision`) |
| `propose_edit_plan` | `POST /v1/editing-agent:preview` | readOnly | Rejani `editing_agent/model.py::EditPlan` bo'yicha tekshiradi va engine executor'ida quruq ishlatadi — **qo'llamaydi**. Natija: `valid`, `errors[]`, `changes[]`, `warnings[]` |
| `apply_edit_plan` | `GET /v1/montages/{mid}` → `POST /v1/editing-agent:preview` (draft) → `PUT /v1/montages/{mid}/timeline` | write | `base_revision` majburiy; eskirgan bo'lsa "409 Conflict" matni. Muvaffaqiyatda yangi `base_revision` va undo yozuvi |
| `undo_last_edit` | `PUT /v1/montages/{mid}/timeline` | write | Shu MCP sessiyasidagi oxirgi `apply_edit_plan` ni qaytaradi (stek, 20 ta). Montaj keyin boshqa joyda (UI) o'zgartirilgan bo'lsa — rad etadi (409) |
| `render_preview` | `POST /v1/montages/{mid}:preview` yoki `POST /v1/episodes/{eid}/clips/{cid}:preview` | readOnly | Bitta JPEG kadr: MCP `image` kontenti (≤4 MB) + server boshqaradigan fayl yo'li (`$TMPDIR/lahza-mcp/previews/`, 0600, oxirgi 20 tasi saqlanadi) |
| `export_clip` | `POST /v1/episodes/{eid}/clips/{cid}:export` yoki `POST /v1/montages/{mid}:render` | **destructive** | Faqat `confirm: true` bilan (aks holda engine'ga murojaat ham bo'lmaydi). Papkani Claude tanlamaydi |
| `job_status` | `GET /v1/jobs/{id}` | readOnly | Eksport vazifasi holati (natijadan faqat skalyar maydonlar) |

Tahrir rejasi (`lahza.edit-plan/1`) — `schema` ixtiyoriy (avtomatik qo'yiladi):

```json
{"base_revision": "<get_timeline natijasidan>",
 "commands": [{"tool": "set_color", "args": {"preset": "warm"}},
              {"tool": "freeze_clip", "args": {"clip_id": "v1", "at_ms": 7000, "duration_ms": 1000}}],
 "unresolved": []}
```

Operatsiyalar: `set_format{profile}`, `set_captions{enabled,font_size}`,
`add_caption{text,start_ms,end_ms}`, `set_color{preset}`, `freeze_clip{clip_id,at_ms,duration_ms}`
(qat'iy, ortiqcha maydon taqiqlangan — `docs/local-ai-editing.md`).

Tavsiya etilgan oqim: `list_montages` → `get_timeline` → `propose_edit_plan` → (foydalanuvchi bilan
kelishib) `apply_edit_plan` → `render_preview` → kerak bo'lsa `undo_last_edit` → rozilik bilan
`export_clip` → `job_status`.

## 3. Ulanish misollari

Rasmiy ro'yxatdan o'tkazishni A agent (`claude_bridge/`) bajaradi; qo'lda:

```bash
# Claude Code (foydalanuvchi darajasida)
claude mcp add --scope user lahza -- "/Applications/Lahza Studio.app/Contents/MacOS/lahza-engine" mcp

# Dev muhit
claude mcp add lahza -e PYTHONPATH=$PWD/engine/src -- $PWD/engine/.venv/bin/python -m lahza_engine mcp
```

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{"mcpServers": {"lahza": {"command": "/Applications/Lahza Studio.app/Contents/MacOS/lahza-engine",
                          "args": ["mcp"]}}}
```

Konfiguratsiyani o'zgartirmasdan bir martalik sinov:

```bash
claude -p --strict-mcp-config --mcp-config /tmp/lahza-mcp.json \
  --allowedTools mcp__lahza__lahza_status -- "lahza_status tool'ini chaqir"
```

Engine ishlashi shart: Lahza Studio ochiq (`serve --discovery`) yoki servis o'rnatilgan
(`lahza-engine install-service`).

## 4. Xavfsizlik

* **Ixtiyoriy fayl yo'li yo'q.** Hech bir tool `path`/`out_dir`/`filename` qabul qilmaydi
  (sxemada `additionalProperties: false` — test bilan qo'riqlanadi). Eksport papkasi
  `LAHZA_MCP_EXPORT_DIR` (foydalanuvchi muhiti) yoki `~/Movies/Lahza` (macOS) / `~/Videos/Lahza`.
  Preview kadri server boshqaradigan vaqtinchalik papkaga yoziladi.
* **Media baytlari qaytarilmaydi.** Video/audio/proksi endpointlari (`/proxy`, `/waveform`,
  `/thumb`) xaritalanmagan; yagona binar javob — preview JPEG (≤4 MB, magic bayt tekshiriladi).
* **Javob hajmi cheklangan.** Engine javobi ≤16 MB o'qiladi; tool matni ≤60 000 belgi (ortig'i
  "truncated" belgisi bilan kesiladi); ro'yxatlar sahifalanadi; timeline tavsifi media yo'llarisiz.
* **ID'lar URL-kodlanadi** (`../` bilan boshqa endpointga chiqib bo'lmaydi).
* **Faqat 127.0.0.1**, token faqat discovery faylidan (0600), proksi chetlab o'tiladi.
* **Tahrirlar xavfsiz:** `base_revision` (sha256) eskirgan rejani rad etadi; reja engine
  executor'ida atomik tekshiriladi; `undo_last_edit` boshqa joyda qilingan o'zgarishni ezmaydi.
* **Eksport** — `destructiveHint: true` va `confirm: true` majburiy; `confirm` bo'lmasa engine'ga
  so'rov yuborilmaydi.
* Takroriy so'rov faqat ulanish rad etilganda (engine qayta ishga tushgan) — timeout'da takror yo'q,
  ikki marta eksport bo'lmaydi.

## 5. Cheklovlar

* Undo stek MCP jarayoni xotirasida — Claude sessiyasi yopilsa yo'qoladi.
* `tools/call` sinxron (bitta stdio sessiya); `notifications/cancelled` e'tiborsiz qoldiriladi.
* Montaj yaratish/qayta rejalash, transkript tahriri MCP orqali hali yo'q.
