#!/usr/bin/env bash
# Lahza Adobe plaginlari + mustaqil "Lahza Engine" servisi — o'rnatish (macOS, ADB-7).
# Bu imzolangan o'rnatuvchi EMAS (u ADB-9): dasturchi/ichki sinovchi uchun tartibni bitta skriptga yig'adi.
# Tartib va izohlar: docs/12-adobe-plaginlar.md, 3.3-bo'lim.
#
#   1. Engine servisi: `lahza install-service` -> ~/Library/LaunchAgents/uz.lahza.engine.plist (gui/<uid> domeni).
#   2. After Effects paneli (CEP): adobe/scripts/cep-dev-install.sh (symlink + PlayerDebugMode).
#   3. Premiere paneli (UXP): --ccx berilsa UPIA bilan o'rnatiladi, aks holda yo'riqnoma chiqariladi.
#
# Foydalanish:
#   scripts/install_adobe_engine.sh [--app "/Applications/Lahza Studio.app"] [--ccx FILE.ccx]
#                                   [--skip-plugins] [--dry-run] [--uninstall]
#   --app      o'rnatilgan Lahza Studio'ning sidecar'i servis sifatida ishlatiladi (tavsiya);
#              berilmasa — repo'dagi engine (engine/.venv) ishlatiladi (dev).
#   --dry-run  hech narsa yozilmaydi/ishga tushirilmaydi: servis rejasi (plist) va qadamlar chiqariladi.
# sudo kerak emas va ishlatilmaydi.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Bu skript macOS uchun. Windows: scripts/install_adobe_engine.ps1" >&2
  exit 1
fi
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "sudo bilan ishga tushirmang — servis foydalanuvchi darajasida (LaunchAgent) o'rnatiladi." >&2
  exit 1
fi

APP=""
CCX=""
SKIP_PLUGINS=0
DRY=0
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --app) APP="$2"; shift 2 ;;
    --ccx) CCX="$2"; shift 2 ;;
    --skip-plugins) SKIP_PLUGINS=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "noma'lum argument: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPIA="/Library/Application Support/Adobe/Adobe Desktop Common/RemoteComponents/UPI/UnifiedPluginInstallerAgent/UnifiedPluginInstallerAgent.app/Contents/MacOS/UnifiedPluginInstallerAgent"

run() {  # dry-run'da faqat chiqaradi
  if [[ $DRY -eq 1 ]]; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}

# ---- Engine buyrug'i -------------------------------------------------------------------------
if [[ -n "$APP" ]]; then
  ENGINE=("$APP/Contents/MacOS/lahza-engine")
  [[ -x "${ENGINE[0]}" ]] || { echo "Sidecar topilmadi: ${ENGINE[0]}" >&2; exit 1; }
  # Ilova resurslari (Tauri `resource_dir` = Contents/Resources) - desktop sidecar'i bilan bir xil muhit.
  export LAHZA_BIN_DIR="$APP/Contents/Resources/bin"
  export LAHZA_CATALOG="$APP/Contents/Resources/catalog/catalog.json"
else
  PY="${LAHZA_PYTHON:-$ROOT/engine/.venv/bin/python}"  # LAHZA_PYTHON - boshqa venv
  [[ -x "$PY" ]] || { echo "engine/.venv yo'q — avval: cd engine && uv venv && uv pip install -e '.[dev]'" >&2; exit 1; }
  ENGINE=("$PY" -m lahza_engine)
  # Shu repo'dagi engine kodi (venv boshqa checkout'ga editable o'rnatilgan bo'lishi mumkin);
  # PYTHONPATH servis muhitiga ham o'tadi (plist EnvironmentVariables).
  export PYTHONPATH="$ROOT/engine/src${PYTHONPATH:+:$PYTHONPATH}"
fi

if [[ $UNINSTALL -eq 1 ]]; then
  if [[ $DRY -eq 1 ]]; then "${ENGINE[@]}" uninstall-service --dry-run; else "${ENGINE[@]}" uninstall-service; fi
  if [[ $SKIP_PLUGINS -eq 0 ]]; then
    run "$ROOT/adobe/scripts/cep-dev-install.sh" --uninstall
    echo "Premiere paneli: Creative Cloud > Stock & Marketplace > Plugins (yoki UPIA --remove 'Lahza') orqali o'chiriladi."
  fi
  exit 0
fi

# ---- 1. Engine servisi -----------------------------------------------------------------------
echo "== 1/3 Lahza Engine servisi (LaunchAgent uz.lahza.engine)"
if [[ $DRY -eq 1 ]]; then
  "${ENGINE[@]}" install-service --dry-run
else
  "${ENGINE[@]}" install-service
  sleep 2
  "${ENGINE[@]}" service-status || true
fi

if [[ $SKIP_PLUGINS -eq 1 ]]; then exit 0; fi

# ---- 2. After Effects (CEP) ------------------------------------------------------------------
echo "== 2/3 After Effects paneli (CEP)"
if [[ -f "$ROOT/adobe/after-effects/dist/main.js" ]]; then
  run "$ROOT/adobe/scripts/cep-dev-install.sh"
else
  echo "O'tkazib yuborildi: adobe/after-effects/dist yo'q — (cd adobe/after-effects && npm install && npm run build) va qayta ishga tushiring."
fi

# ---- 3. Premiere Pro (UXP) -------------------------------------------------------------------
echo "== 3/3 Premiere Pro paneli (UXP)"
if [[ -n "$CCX" ]]; then
  if [[ -x "$UPIA" ]]; then
    run "$UPIA" --install "$CCX"
  else
    echo "UPIA topilmadi (Creative Cloud Desktop o'rnatilmagan?). .ccx faylini ikki marta bosing: $CCX"
  fi
else
  cat <<MSG
.ccx berilmadi. Dev rejim: Premiere > Settings > Plugins > Developer Mode, so'ng UXP Developer Tool'da
adobe/premiere/dist/manifest.json > Load. Paket: adobe/premiere/README.md (.ccx).
MSG
fi

echo
echo "Tayyor. Panel engine'ni ~/Library/Application Support/Lahza Studio/engine.json orqali topadi."
echo "Holat: lahza service-status · O'chirish: scripts/install_adobe_engine.sh --uninstall"
