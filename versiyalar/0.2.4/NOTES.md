# Lahza Studio 0.2.4

- **Sana:** 2026-10-26 21:55 +05
- **Git commit:** `4d04b0059bba` (Sidecar GPL tekshiruvi: excludes ro'yxatidagi 'av' ni PyAV yozuvi deb hisoblamaydi (ADR-0015)) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.2.4

## O'zgarishlar

- **Yangi — Claude montaj (standart o'chiq):** foydalanuvchi kompyuteridagi Claude Code/Desktop topiladi; montaj panelida Lokal/Claude reja tanlovi, Lahza MCP serveri (`lahza-engine mcp`, 13 tool) Claude'ga bir tugma bilan ulanadi. Claude'ga faqat timeline tavsifi va transkript matni boradi (`claude_bridge/`, `/v1/claude/*`, docs/15-claude-montaj.md).
- **Yaxshilash — LLM highlight tezligi:** 10 daqiqalik videoda 498 s → 43 s (M3-PERF-2).
- **Yaxshilash — xotira:** WAV oqimli o'qiladi; 4 soatlik podkastda RSS 2242 → 210 MB (V1-1).
- **Yangi — aktiv spiker:** LR-ASD ONNX backend + diarizatsiya, eksportda kadr gapirayotgan odamga yo'naltiriladi (R0-VIS-2, M3-RF-1).
- **Yangi — mustaqil Lahza Engine servisi:** macOS LaunchAgent / Windows Task Scheduler; Studio va Adobe plaginlari bitta engine'ni discovery orqali topadi (ADB-7).
- **Yangi — shaxsiy lug'at va ball vaznlari:** real natijalardan o'rganadi (PRO-1, PRO-6).
- **Yangi — oflayn litsenziya kaliti:** Ed25519, standart holatda o'chiq (V1-3, ADR-0016).
- **Litsenziya — ASR PyAV'siz:** dekod LGPL FFmpeg orqali, GPL libx264/libx265 li `av` sidecar'dan chiqarildi (ADR-0015).
- **Yaxshilash — import kartasi:** fayl va YouTube havolasi bitta sahifada.
- **Sifat:** chidamlilik testlari, tezlik benchmarki, platforma limitlari (V1-1, M3-PERF-1, V1-6); navbat `shutdown()` dagi poyga holati tuzatildi.

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 1172 passed, 11 skipped, 2 deselected (134 s) |
| `make test-ui` | 124 passed, 0 failed (1 s) |
| `make typecheck` | ok (2 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.3 daqiqa)
- `Lahza Studio.app`: 193.9 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.4-macos-arm64.zip`: 116.1 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
