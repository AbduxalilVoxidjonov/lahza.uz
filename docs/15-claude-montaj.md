# Claude montaj

Foydalanuvchi kompyuterida Claude (Claude Code CLI va/yoki Claude Desktop) bo'lsa, Lahza
montaj rejasini lokal model o'rniga Claude orqali tuzishi va Claude'ga Lahza'ning MCP serverini
ulashi mumkin. Mahsulot oflayn-birinchi: funksiya **standart holatda o'chiq**, yoqilmaguncha
Claude bilan hech qanday aloqa bo'lmaydi va mavjud [lokal AI montaj](local-ai-editing.md)
o'zgarishsiz ishlaydi.

Kod: `engine/src/lahza_engine/claude_bridge/` (`detect.py`, `connect.py`, `planner.py`,
`store.py`, `proc.py`), API — `api/routes_claude.py`, testlar — `engine/tests/test_claude_bridge.py`.

## Maxfiylik: nima yuboriladi, nima yuborilmaydi

Reja tuzishda Claude'ga (Anthropic serverlariga, foydalanuvchining o'z Claude hisobi orqali)
faqat quyidagilar boradi — lokal planner bilan bir xil `compact_context` allowlist'i:

* foydalanuvchi yozgan prompt (≤ 2000 belgi);
* timeline tavsifi: davomiylik, format/profil, caption sozlamalari, rang preseti, klip ID'lari,
  ularning chiqish vaqtlari, tezligi, effekt/o'tish plagin ID'lari (12 000 belgi budjet);
* transkriptning dastlabki ≤ 200 so'zi (matn va ms vaqtlari, budjet bilan kesiladi);
* tizim prompti (amallar qoidalari, misollar, JSON sxema).

**Yuborilmaydi:** video, audio, kadrlar, fayl va papka yo'llari, media nomlari, brend/ shrift
yo'llari, loyiha bazasi, token, kelib chiqish (provenance) ma'lumotlari. Claude hech qanday
tool'siz ishga tushiriladi, shuning uchun fayl o'qiy olmaydi va buyruq bajara olmaydi.

Aniqlash (`claude --version`, fayl tizimini tekshirish) tarmoqsiz va funksiya o'chiq bo'lsa ham
holat ko'rsatish uchun bajariladi. `check-auth` tarmoqqa chiqadi (kichik headless so'rov) va
faqat yoqilgan holatda, foydalanuvchi bosganda ishlaydi.

## Aniqlash

* CLI: avval `PATH`, so'ng `~/.local/bin` (rasmiy o'rnatuvchi), `~/.claude/local`,
  `/opt/homebrew/bin`, `/usr/local/bin`; Windows'da `%APPDATA%\npm`, `%LOCALAPPDATA%\Programs\claude`,
  `%LOCALAPPDATA%\claude` (`claude.exe`, `claude.cmd`). macOS GUI ilovalariga shell `PATH`i
  berilmagani uchun qo'shimcha papkalar zarur. Versiya — `claude --version` (`2.1.310 (Claude Code)`).
* Desktop: macOS `/Applications/Claude.app`, `~/Applications/Claude.app`; Windows
  `%LOCALAPPDATA%\AnthropicClaude`. Linux uchun yo'q.
* Natija 15 soniya keshlanadi (`GET /v1/claude/status?refresh=true` keshni yangilaydi).

## Ishlatilgan `claude` bayroqlari

`claude --help` va `claude mcp --help` (Claude Code 2.1.310) chiqishidan olingan:

| Maqsad | Bayroq |
| --- | --- |
| Headless, javobni chiqarib tugatish | `-p` / `--print` (prompt stdin'dan) |
| Bitta JSON natija | `--output-format json` → `{type: "result", subtype, is_error, result, modelUsage, …}` |
| Barcha tool'lar o'chiq | `--tools ""` |
| MCP serverlar yuklanmaydi | `--strict-mcp-config` (`--mcp-config`siz) |
| CLAUDE.md, skill, plagin, hook'lar o'chiq | `--safe-mode` (auth va model tanlash ishlaydi) |
| Slash buyruqlar o'chiq | `--disable-slash-commands` |
| Sessiya diskka yozilmaydi | `--no-session-persistence` |
| Tizim prompti | `--system-prompt-file <vaqtinchalik fayl>` (Windows `claude.cmd` uzun/ko'p qatorli argumentni kesadi) |
| Model (ixtiyoriy) | `--model <alias yoki nom>` — `LAHZA_CLAUDE_MODEL` muhit o'zgaruvchisidan |
| Auth holati (lokal) | `claude auth status --json` → `{loggedIn, …}` |
| MCP ulash | `claude mcp add --scope user lahza -e K=V … -- <buyruq>` |
| MCP uzish | `claude mcp remove --scope user lahza` |

Bu versiyada `--max-turns` yo'q; tool'lar o'chiq bo'lgani uchun javob baribir bitta tur.
`--allowedTools`/`--disallowedTools` mavjud, lekin `--tools ""` butun to'plamni o'chiradi.
`--json-schema` (structured output) ham bor — hozircha ishlatilmaydi: sxema tizim promptida
beriladi va javob engine'da qat'iy tekshiriladi.

## Reja tuzish (`planner: "claude"`)

1. `POST /v1/editing-agent:plan` tanasida `planner: "claude"`. Funksiya o'chiq — 409
   `claude_disabled`; CLI yo'q — 503 `claude_not_installed`.
2. Engine timeline'ni tekshiradi, `compact_context` tuzadi va `claude -p` ni **shell'siz**
   (argumentlar ro'yxat), bo'sh vaqtinchalik papkada ishga tushiradi; prompt stdin orqali.
3. Prompt injection'ga qarshi: foydalanuvchi matni va timeline konteksti tasodifiy nonce bilan
   belgilangan alohida bloklarda (`<<<USER_REQUEST nonce>>> … <<<END USER_REQUEST nonce>>>`);
   matndagi nonce olib tashlanadi; tizim prompti bloklar ichidagini faqat ma'lumot deb belgilaydi.
4. Javobdan JSON ajratiladi (```json``` fence va atrofdagi matnga chidamli, ≤ 64 000 belgi) →
   `Proposal` (qat'iy sxema, `extra=forbid`) → `executor.preview` (atomik, nusxada).
   `base_revision` engine'da hisoblanadi — Claude uni ko'rmaydi va yarata olmaydi.
5. Buzuq JSON, sxemadan o'tmagan yoki executor rad etgan reja — xato matni bilan **bitta qayta
   urinish**; yana yaroqsiz bo'lsa 422 `claude_bad_plan`.
6. Javob shakli lokal planner bilan bir xil (`plan`, `changes`, `warnings`, `model_id`) va
   `planner: "claude"`; `model_id` — `modelUsage` dagi model (masalan `claude-opus-5-5`).
   Qo'llash odatdagi yo'l: `:preview` → draft → undo; eskirgan reja 409.
7. Timeout 120 s (504 `claude_timeout`), bir vaqtda bitta so'rov (409 `claude_busy`),
   `POST /v1/claude/cancel` jarayonni o'ldiradi (409 `claude_cancelled`).

## Ulash tartibi

1. Sozlamalarda funksiyani yoqing (`PUT /v1/claude/settings {"enabled": true}`).
2. "Tekshirish" — `POST /v1/claude/check-auth`: avval lokal `claude auth status --json`;
   `loggedIn: false` bo'lsa `not_logged_in` (tarmoqqa chiqmaydi), aks holda kichik headless
   so'rov. Kirilmagan bo'lsa terminalda `claude` ni ishga tushirib `/login` qiling.
3. "Ulash" — avval `dry_run: true` bilan bajariladigan amallar ko'rsatiladi, so'ng tasdiqlansa
   haqiqiy ulash:
   * **Claude Code** — `claude mcp add --scope user lahza … -- <buyruq>`; allaqachon bor bo'lsa
     avval `remove` (yangilash). Holat `~/.claude.json` (yoki `$CLAUDE_CONFIG_DIR/.claude.json`)
     → `mcpServers.lahza` dan o'qiladi.
   * **Claude Desktop** — `claude_desktop_config.json` (macOS `~/Library/Application Support/Claude/`,
     Windows `%APPDATA%\Claude\`) → `mcpServers.lahza = {command, args, env}`. Boshqa yozuvlar
     saqlanadi, avval `.bak` zaxira, yozish atomik. Yaroqsiz JSON — 409 `claude_config_invalid`,
     fayl o'zgartirilmaydi. O'zgarish kuchga kirishi uchun Claude Desktop'ni qayta ishga tushiring.
4. Uzish — `POST /v1/claude/disconnect` (shu tartibda). Funksiyani o'chirish ulanishni avtomatik
   olib tashlamaydi: UI avval uzib, so'ng o'chirishi kerak (o'chiq holatda disconnect 409).

MCP buyrug'i ADB-7 servis mantiqidan (`service/spec.py`): packaged — sidecar binari + `mcp`,
dev — `python -m lahza_engine mcp`. Muhit: `LAHZA_DATA_DIR` va `service.spec.PASS_ENV` dagi
o'rnatilgan o'zgaruvchilar (token hech qachon).

## MCP server

MCP server: `lahza-engine mcp`.

## API

[Engine API → Claude](04-engine-api.md#claude-montaj).

## Cheklovlar

* Claude hisobi va tarmoq kerak; narx/limitlar foydalanuvchining Claude obunasi bo'yicha.
* Reja sifati kafolatlanmaydi: sxemadan o'tish foydalanuvchi maqsadi to'g'ri tushunilganini
  isbotlamaydi — preview'ni ko'rib qo'llang.
* "Not logged in" aniqlash CLI matniga tayanadi (`/login`, `not logged in`, `invalid api key`…);
  CLI matni o'zgarsa `claude_error` qaytishi mumkin.
* Windows'da `claude.cmd` (npm o'rnatmasi) `cmd.exe` orqali ishlaydi; native `claude.exe` afzal.
  Windows'da amaliy sinov hali bajarilmagan.
* Auth holati faqat engine xotirasida (qayta ishga tushganda `unknown`); e-pochta saqlanmaydi.

## Sinov

`engine/tests/test_claude_bridge.py` — tarmoqsiz: soxta PATH/HOME, soxta `claude` skripti,
soxta runner; foydalanuvchining haqiqiy Claude konfiguratsiyasiga tegmaydi. Jonli sinov
(opt-in): `LAHZA_CLAUDE_LIVE=1 pytest tests/test_claude_bridge.py -k live -s` — haqiqiy
`claude -p` bilan bitta kichik reja. 2026-10-26 natijasi (Claude Code 2.1.310, standart model
`claude-opus-5-5`): "Instagram Reels formatiga mosla va ranglarni iliqroq qil." →
`set_format: instagram_reels` + `set_color: warm`, 6.0 s.
