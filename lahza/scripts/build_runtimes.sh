#!/usr/bin/env bash
# macOS (va Linux dasturchi muhiti) uchun native runtime'larni yig'ish.
# Versiyalar: third_party/runtimes.toml (bo'sh `ref` - to'xtaydi).
# Natija: app/src-tauri/resources/bin/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/app/src-tauri/resources/bin"
SRC="$ROOT/build/runtimes"
mkdir -p "$OUT" "$SRC"

# Desktop inference uses bundled CTranslate2, not whisper-cli. The macOS
# installers pin artifact hashes and relocate the complete native dylib closure.
if [[ "$(uname)" == "Darwin" ]]; then
  LAHZA_BUILD_PYTHON="${LAHZA_BUILD_PYTHON:-$ROOT/engine/.venv/bin/python}"
  if [[ ! -x "$LAHZA_BUILD_PYTHON" ]]; then LAHZA_BUILD_PYTHON=python3; fi
  "$LAHZA_BUILD_PYTHON" "$ROOT/scripts/setup_local_render.py" --stage "$OUT"
  "$LAHZA_BUILD_PYTHON" "$ROOT/scripts/setup_local_llm.py" --stage "$OUT" --consent
  exit 0
fi

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

# --- dav1d (BSD-2, statik; FFmpeg AV1 dekoderi) ------------------------------
# Talab: meson, ninja (pip install meson ninja), nasm (x86_64 uchun).
DAV1D_VERSION="$(toml dav1d version)"
DAV1D_TAR="$SRC/downloads/dav1d-$DAV1D_VERSION.tar.xz"
DAV1D_PREFIX="$SRC/dav1d-install"
mkdir -p "$SRC/downloads"
if [[ ! -f "$DAV1D_TAR" ]]; then curl -fL --retry 3 -o "$DAV1D_TAR.part" "$(toml dav1d url)" && mv "$DAV1D_TAR.part" "$DAV1D_TAR"; fi
echo "$(toml dav1d sha256)  $DAV1D_TAR" | sha256sum -c - || { echo "XATO: dav1d SHA-256 mos emas: $DAV1D_TAR" >&2; exit 1; }
rm -rf "$SRC/dav1d-$DAV1D_VERSION" && tar -xJf "$DAV1D_TAR" -C "$SRC"
# shellcheck disable=SC2046
meson setup "$SRC/dav1d-$DAV1D_VERSION/build" "$SRC/dav1d-$DAV1D_VERSION" --prefix="$DAV1D_PREFIX" $(toml dav1d meson_options)
ninja -C "$SRC/dav1d-$DAV1D_VERSION/build" install
# Arxivni mutlaq yo'l bilan bog'lash: tizimdagi shared libdav1d tanlanib qolmasin.
sed -i.bak "s|-L\${libdir} -ldav1d|$DAV1D_PREFIX/lib/libdav1d.a|" "$DAV1D_PREFIX/lib/pkgconfig/dav1d.pc"
cp "$SRC/dav1d-$DAV1D_VERSION/COPYING" "$OUT/dav1d.COPYING"
export PKG_CONFIG_PATH="$DAV1D_PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

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
if ! "$OUT/ffmpeg" -hide_banner -decoders | grep -qw libdav1d; then
  echo "XATO: FFmpeg'da libdav1d (AV1) dekoderi yo'q" >&2; exit 1
fi
echo "Tayyor: $OUT"
