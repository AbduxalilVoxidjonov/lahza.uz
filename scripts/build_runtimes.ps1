# Windows x64 uchun native runtime'larni yig'ish.
# Talab: Visual Studio Build Tools (C++), CMake, Git, (ixtiyoriy) CUDA Toolkit, Vulkan SDK.
# FFmpeg'ni Windows'da yig'ish MSYS2 talab qiladi - pastdagi izohga qarang.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\.."
$Out = Join-Path $Root "app\src-tauri\resources\bin"
$Src = Join-Path $Root "build\runtimes"
New-Item -ItemType Directory -Force -Path $Out, $Src | Out-Null

function Get-Toml($section, $key) {
  python -c "import tomllib;d=tomllib.load(open(r'$Root\third_party\runtimes.toml','rb'));v=d['$section']['$key'];print(' '.join(v) if isinstance(v,list) else v)"
}

function Checkout($section, $dir) {
  $repo = Get-Toml $section "repo"
  $ref = Get-Toml $section "ref"
  if (-not $ref) { throw "third_party/runtimes.toml [$section].ref bo'sh (R0-RT-1 da mahkamlang)" }
  $path = Join-Path $Src $dir
  if (-not (Test-Path "$path\.git")) { git clone --filter=blob:none $repo $path }
  git -C $path fetch --tags --quiet
  git -C $path checkout --quiet $ref
  return $path
}

# CUDA bo'lsa NVIDIA uchun, aks holda Vulkan (AMD/Intel) yig'masi.
$Gpu = if ($env:LAHZA_GPU) { $env:LAHZA_GPU } else { "vulkan" }
$GgmlFlag = if ($Gpu -eq "cuda") { "-DGGML_CUDA=ON" } else { "-DGGML_VULKAN=ON" }
# Statik CRT (/MT): exe VC++ runtime DLL'lariga bog'lanmaydi - foydalanuvchi kompyuteridagi eski
# msvcp140.dll (masalan 14.28) llama/ggml ni access violation bilan qulatadi.
$CrtFlags = @("-DCMAKE_POLICY_DEFAULT_CMP0091=NEW", "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded")

$w = Checkout "whisper_cpp" "whisper.cpp"
cmake -S $w -B "$w\build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF $GgmlFlag @CrtFlags
cmake --build "$w\build" --config Release --target whisper-cli
Copy-Item "$w\build\bin\Release\whisper-cli.exe" $Out

$l = Checkout "llama_cpp" "llama.cpp"
cmake -S $l -B "$l\build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF $GgmlFlag @CrtFlags
cmake --build "$l\build" --config Release --target llama-server
Copy-Item "$l\build\bin\Release\llama-server.exe" $Out

# FFmpeg (LGPL): MSYS2 MinGW64 muhitida yig'iladi. Avval dav1d (BSD-2, AV1 dekoderi) statik:
#   [dav1d] url'dan yuklab, sha256 ni tekshirib (sha256sum -c), so'ng
#   meson setup build $(meson_options) --prefix=$DAV1D_PREFIX && ninja -C build install
#   (pacman -S mingw-w64-x86_64-meson mingw-w64-x86_64-ninja mingw-w64-x86_64-nasm)
#   dav1d.pc dagi "-L${libdir} -ldav1d" ni libdav1d.a mutlaq yo'liga almashtiring, PKG_CONFIG_PATH ga qo'shing.
# So'ng:
#   ./configure $(configure_common) $(configure_windows) --target-os=mingw32 --arch=x86_64
# va ffmpeg.exe, ffprobe.exe, *.dll fayllari hamda dav1d COPYING ($Out\dav1d.COPYING) nusxalanadi.
# Tekshiruv: ffmpeg -buildconf da --enable-gpl bo'lmasligi, ffmpeg -decoders da libdav1d bo'lishi shart (ADR-0004).
Write-Host "whisper-cli va llama-server tayyor: $Out. FFmpeg uchun yuqoridagi izohga qarang."
