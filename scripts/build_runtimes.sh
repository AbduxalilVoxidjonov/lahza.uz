#!/usr/bin/env bash
# macOS (va Linux dasturchi muhiti) uchun native runtime'larni yig'ish.
# Versiyalar: third_party/runtimes.toml (bo'sh `ref` - to'xtaydi).
# Natija: app/src-tauri/resources/bin/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/app/src-tauri/resources/bin"
SRC="$ROOT/build/runtimes"
mkdir -p "$OUT" "$SRC"

toml() { python3 -c "import tomllib,sys;d=tomllib.load(open('$ROOT/third_party/runtimes.toml','rb'));v=d['$1']['$2'];print(' '.join(v) if isinstance(v,list) else v)"; }

need_ref() {
  local ref; ref="$(toml "$1" ref)"
  if [[ -z "$ref" ]]; then
    echo "XATO: third_party/runtimes.toml [$1].ref bo'sh (R0-RT-1 da mahkamlang)" >&2; exit 1
  fi
  echo "$ref"
}

checkout() {  # $1=bo'lim $2=papka
  local repo ref; repo="$(toml "$1" repo)"; ref="$(need_ref "$1")"
  if [[ ! -d "$SRC/$2/.git" ]]; then git clone --filter=blob:none "$repo" "$SRC/$2"; fi
  git -C "$SRC/$2" fetch --tags --quiet
  git -C "$SRC/$2" checkout --quiet "$ref"
}

# --- whisper.cpp (Apple'da Metal standart yoqilgan) -------------------------
checkout whisper_cpp whisper.cpp
cmake -S "$SRC/whisper.cpp" -B "$SRC/whisper.cpp/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
cmake --build "$SRC/whisper.cpp/build" --config Release -j --target whisper-cli
cp "$SRC/whisper.cpp/build/bin/whisper-cli" "$OUT/"

# --- llama.cpp ---------------------------------------------------------------
checkout llama_cpp llama.cpp
cmake -S "$SRC/llama.cpp" -B "$SRC/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF
cmake --build "$SRC/llama.cpp/build" --config Release -j --target llama-server
cp "$SRC/llama.cpp/build/bin/llama-server" "$OUT/"

# --- FFmpeg (LGPL) -----------------------------------------------------------
# Talab: libass, freetype, harfbuzz, fribidi (macOS: brew install libass pkg-config nasm)
checkout ffmpeg ffmpeg
EXTRA="$(toml ffmpeg configure_common)"
if [[ "$(uname)" == "Darwin" ]]; then EXTRA="$EXTRA $(toml ffmpeg configure_macos)"; fi
( cd "$SRC/ffmpeg" && ./configure --prefix="$SRC/ffmpeg-install" $EXTRA && make -j"$(getconf _NPROCESSORS_ONLN)" && make install )
cp "$SRC/ffmpeg-install/bin/ffmpeg" "$SRC/ffmpeg-install/bin/ffprobe" "$OUT/"
cp -P "$SRC/ffmpeg-install/lib/"*.dylib "$OUT/" 2>/dev/null || cp -P "$SRC/ffmpeg-install/lib/"*.so* "$OUT/"

# GPL tekshiruvi: yig'mada --enable-gpl bo'lmasligi shart (ADR-0004)
if "$OUT/ffmpeg" -hide_banner -buildconf | grep -q -- "--enable-gpl"; then
  echo "XATO: FFmpeg GPL bilan yig'ilgan" >&2; exit 1
fi
echo "Tayyor: $OUT"
