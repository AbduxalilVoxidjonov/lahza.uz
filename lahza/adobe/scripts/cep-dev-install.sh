#!/usr/bin/env bash
# Lahza After Effects CEP paneli — dev o'rnatish (macOS).
#   * foydalanuvchi extensions papkasiga symlink:  ~/Library/Application Support/Adobe/CEP/extensions/uz.lahza.ae
#   * imzosiz panel uchun PlayerDebugMode=1:        defaults write com.adobe.CSXS.<N> PlayerDebugMode 1
# Manba: Adobe-CEP/CEP-Resources, CEP_12.x "CEP 12 HTML Extension Cookbook" (Extension Folders, Debugging Unsigned Extensions).
# Faqat foydalanuvchining o'z papkalari/sozlamalari; sudo kerak emas va ishlatilmaydi.
#
# Foydalanish:  adobe/scripts/cep-dev-install.sh [--uninstall] [--csxs "11 12"]
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Bu skript macOS uchun. Windows: adobe/scripts/cep-dev-install.ps1" >&2
  exit 1
fi
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "sudo bilan ishga tushirmang — skript faqat foydalanuvchi papkasiga yozadi." >&2
  exit 1
fi

BUNDLE_ID="uz.lahza.ae"
# CEP 12 = After Effects 25.x+ (CSXS.12). 11 — AE 2022–2024 da eski panel sinovi uchun (manifest baribir CSXS 12 talab qiladi).
CSXS_VERSIONS="11 12"
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall) UNINSTALL=1; shift ;;
    --csxs) CSXS_VERSIONS="$2"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "noma'lum argument: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$SCRIPT_DIR/../after-effects" && pwd)"
EXT_DIR="$HOME/Library/Application Support/Adobe/CEP/extensions"
LINK="$EXT_DIR/$BUNDLE_ID"

if [[ "$SRC" == *"#"* ]]; then
  echo "Ogohlantirish: yo'lda '#' bor — CEP bunday papkani yuklamaydi (Cookbook)." >&2
fi

if [[ $UNINSTALL -eq 1 ]]; then
  if [[ -L "$LINK" ]]; then rm "$LINK"; echo "O'chirildi: $LINK"; else echo "Symlink yo'q: $LINK"; fi
  echo "PlayerDebugMode o'zgartirilmadi (boshqa panellar ham ishlatishi mumkin). Qaytarish:"
  for v in $CSXS_VERSIONS; do echo "  defaults delete com.adobe.CSXS.$v PlayerDebugMode"; done
  exit 0
fi

if [[ ! -f "$SRC/dist/main.js" ]]; then
  echo "dist/ yo'q — avval: (cd adobe/after-effects && npm install && npm run build)" >&2
  exit 1
fi

mkdir -p "$EXT_DIR"
if [[ -e "$LINK" && ! -L "$LINK" ]]; then
  echo "$LINK mavjud va symlink emas — qo'lda tekshiring (o'chirmayman)." >&2
  exit 1
fi
ln -sfn "$SRC" "$LINK"
echo "Symlink: $LINK -> $SRC"

for v in $CSXS_VERSIONS; do
  defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1
  echo "PlayerDebugMode=1: com.adobe.CSXS.$v"
done
# plist keshi (Cookbook: cfprefsd'ni to'xtatish yoki qayta kirish). cfprefsd foydalanuvchi jarayoni — avtomatik qayta ishga tushadi.
killall -u "$USER" cfprefsd 2>/dev/null || true

cat <<MSG

Tayyor. After Effects'ni qayta ishga tushiring: Window > Extensions > Lahza.
Debug: Chrome'da http://localhost:8098 (adobe/after-effects/.debug).
UI o'zgarsa: npm run build (yoki npm run watch) va panelda qayta yuklash (DevTools: Cmd+R).
MSG
