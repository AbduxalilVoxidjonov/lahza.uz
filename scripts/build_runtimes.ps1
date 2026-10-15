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

$w = Checkout "whisper_cpp" "whisper.cpp"
cmake -S $w -B "$w\build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF $GgmlFlag
cmake --build "$w\build" --config Release --target whisper-cli
Copy-Item "$w\build\bin\Release\whisper-cli.exe" $Out

$l = Checkout "llama_cpp" "llama.cpp"
cmake -S $l -B "$l\build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF $GgmlFlag
cmake --build "$l\build" --config Release --target llama-server
Copy-Item "$l\build\bin\Release\llama-server.exe" $Out

# FFmpeg (LGPL): MSYS2 MinGW64 muhitida quyidagi bayroqlar bilan yig'iladi:
#   ./configure $(configure_common) $(configure_windows) --target-os=mingw32 --arch=x86_64
# so'ng ffmpeg.exe, ffprobe.exe va *.dll fayllari $Out ga nusxalanadi.
# Tekshiruv: ffmpeg -buildconf natijasida --enable-gpl bo'lmasligi shart (ADR-0004).
Write-Host "whisper-cli va llama-server tayyor: $Out. FFmpeg uchun yuqoridagi izohga qarang."
