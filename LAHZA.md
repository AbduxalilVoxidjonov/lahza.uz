# Lahza Studio — yangi kompyuterda ishga tushirish

Bu repo ikki qismdan iborat:

| Papka | Nima | Texnologiya |
|---|---|---|
| `apps/desktop/` | Lahza Studio montaj dasturi (timeline, effektlar, MCP server) — WeftCut asosida | Electron + React + Rust |
| `lahza/` | Lahza engine: o'zbekcha ASR, highlight, 9:16 Reels, karaoke subtitr | Python (FastAPI), PyInstaller sidecar |

Eski Tauri versiyasi `tauri-legacy` branchida saqlanadi; `lahza/` o'sha tarix bilan birga qo'shilgan.

## 1. Talablar (Windows)

- **Git**, **Node 24+**, **Python 3.12**
- **Rust** (`rustup`, stable) va **Visual Studio Build Tools (C++)**, **CMake**
- Batafsil: [`docs/setup.md`](docs/setup.md) (montaj dasturi), [`lahza/docs/03-dasturchi-muhiti.md`](lahza/docs/03-dasturchi-muhiti.md) (engine)

## 2. Klon qilish

```powershell
git clone https://github.com/AbduxalilVoxidjonov/lahza.uz.git
cd lahza.uz
```

## 3. Montaj dasturi

```powershell
npm install        # JS paketlari
npm run bootstrap  # bir marta: ffmpeg yuklash + Rust addonlarni yig'ish
npm run dev        # dasturni ochish
```

Shu bosqichda dastur ishlaydi; Lahza paneli esa engine yig'ilmaguncha ishlamaydi (engine topilmagani haqida xabar chiqadi).

## 4. Lahza engine (o'zbekcha AI qismi)

```powershell
cd lahza
.\scripts\dev.ps1 setup                 # Python venv + engine paketlari
pwsh scripts\build_runtimes.ps1         # FFmpeg (libass) + llama-server — bir marta, uzoq davom etadi
.\scripts\dev.ps1 sidecar               # lahza-engine.exe ni yig'ish
cd ..
npm run lahza:stage                     # engine'ni dasturga joylash (apps/desktop/resources/lahza/win)
npm run dev
```

Modellar repoga kirmaydi: dastur birinchi tahlilda imzolangan katalogdan kompyuterga mosini o'zi yuklaydi.

O'rnatuvchi (`.exe`) kerak bo'lsa: `npm run package` → `apps/desktop/release/LahzaStudio-win-x64.exe`.

## 5. Claude'ni MCP orqali ulash

Lahza Studio ichida MCP server bor: Claude timeline'ni o'qiy, kesa, subtitr qo'ya va `lahza_*` vositalari bilan
tahlil/highlight/Reels eksport qila oladi.

1. Lahza Studio'ni oching.
2. **Sozlamalar → AI yordamchi** bo'limini oching, **Claude** ni tanlang.
3. Ko'rsatilgan buyruqni nusxalab terminalda ishga tushiring — u shunday ko'rinadi:

   ```powershell
   claude mcp add weftcut -s user -e ELECTRON_RUN_AS_NODE=1 -e WEFTCUT_USERDATA=... -- "...\LahzaStudio.exe" "...\cli\weftcut-mcp.cjs"
   ```

   Claude Desktop uchun esa o'sha yerdagi **Sozlamani nusxalash** tugmasi `mcpServers` JSON beradi —
   uni `claude_desktop_config.json` ga qo'ying.
4. Claude'da `weftcut_status` vositasini chaqiring: dastur ochiq bo'lsa barcha vositalar paydo bo'ladi,
   yopiq bo'lsa `launch_weftcut` uni o'zi ochadi.

Buyruq kompyuterga xos yo'llarni o'z ichiga oladi, shuning uchun har bir kompyuterda bir marta shu bo'limdan oling.
Serverning nomi (`weftcut`) — ichki texnik nom, Lahza Studio'ning o'zi.

Batafsil: [`docs/mcp.md`](docs/mcp.md).

## Litsenziya

Montaj qismi WeftCut (MIT) asosida — muallif ma'lumoti **Haqida** oynasida saqlangan.
Engine litsenziyalari: [`lahza/LICENSES-THIRD-PARTY.md`](lahza/LICENSES-THIRD-PARTY.md).
