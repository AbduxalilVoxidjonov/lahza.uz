# Windows x64 uchun native runtime'larni yig'ish.
# Talab: Visual Studio Build Tools (C++), CMake, Git, (ixtiyoriy) CUDA Toolkit, Vulkan SDK.
# FFmpeg (LGPL) portativ MSYS2 (UCRT64) ichida yig'iladi - admin huquqi kerak emas, MSYS2 o'zi yuklanadi.
#   pwsh scripts/build_runtimes.ps1                     # hammasi
#   pwsh scripts/build_runtimes.ps1 -FFmpegOnly         # faqat FFmpeg (+ dav1d)
#   pwsh scripts/build_runtimes.ps1 -FFmpegOnly -Rebuild -OutDir C:\tmp\bin
# $env:LAHZA_MSYS2 - MSYS2 ildizi (...\msys64); standart: build\runtimes\msys2\msys64.
param(
  [switch]$FFmpegOnly,  # whisper/llama'siz, faqat FFmpeg
  [switch]$Rebuild,     # FFmpeg'ni qayta yig'ish (aks holda build\runtimes\ffmpeg-win qayta tekshirilib ishlatiladi)
  [string]$OutDir       # natija papkasi (standart: app\src-tauri\resources\bin)
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\.."
$Out = if ($OutDir) { [IO.Path]::GetFullPath($OutDir) } else { Join-Path $Root "app\src-tauri\resources\bin" }
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

# ------------------------------------------------------------------ FFmpeg (LGPL, ADR-0004)
# dav1d (BSD-2) statik yig'iladi va avcodec DLL ichiga kiradi; libass/freetype/harfbuzz/fribidi -
# MSYS2 paketlarining DLL'lari, ular bog'liqliklari bilan ffmpeg.exe yoniga ko'chiriladi. Har bir
# ko'chirilgan DLL'ning paketi va litsenziyasi tekshiriladi (GPL - to'xtaydi, GCC runtime istisnosi bundan
# mustasno) va litsenziya matnlari bin\licenses\local-render\<paket>\ ga yoziladi (gen_licenses.py o'qiydi).

$Utf8 = New-Object System.Text.UTF8Encoding $false

# MSYS2 bash ichida bajariladigan yig'ish qismi; parametrlar LZ_* muhit o'zgaruvchilari orqali keladi.
$FFmpegBuildSh = @'
set -euo pipefail
export LC_ALL=C
work="$(cygpath -u "$LZ_WORK")"
rm -rf "$work" && mkdir -p "$work"
exec >"$work.log" 2>&1
jobs="$(nproc)"

echo "== dav1d $LZ_DAV1D_VERSION (statik)"
tar -xJf "$(cygpath -u "$LZ_DAV1D_TAR")" -C "$work"
d="$work/dav1d-$LZ_DAV1D_VERSION"
dprefix="$work/dav1d-install"
# shellcheck disable=SC2086
meson setup "$d/build" "$d" --prefix="$(cygpath -m "$dprefix")" $LZ_DAV1D_MESON
ninja -C "$d/build" -j"$jobs" install
pc="$dprefix/lib/pkgconfig/dav1d.pc"
[[ -f "$dprefix/lib/libdav1d.a" && -f "$pc" ]] || { echo "XATO: dav1d statik kutubxonasi chiqmadi"; exit 1; }
# Faqat statik arxiv: GNU ld'ning "-l:libdav1d.a" shakli shared libdav1d (.dll.a) ni tanlamaydi.
# (macOS'dagi mutlaq .a yo'li bu yerda ishlamaydi: FFmpeg configure uni obyekt fayldan oldin qo'yadi.)
sed -i 's|-L${libdir} -ldav1d|-L${libdir} -l:libdav1d.a|' "$pc"
grep -qF -- '-l:libdav1d.a' "$pc" || { echo "XATO: dav1d.pc Libs qatori kutilmagan: $pc"; exit 1; }
PKG_CONFIG_PATH="$(cygpath -m "$dprefix/lib/pkgconfig")"
export PKG_CONFIG_PATH

echo "== FFmpeg $LZ_FFMPEG_VERSION"
tar -xJf "$(cygpath -u "$LZ_FFMPEG_TAR")" -C "$work"
prefix="$work/install"
cd "$work/ffmpeg-$LZ_FFMPEG_VERSION"
# shellcheck disable=SC2086
./configure --prefix="$prefix" $LZ_FFMPEG_FLAGS
make -j"$jobs"
make install
cp COPYING.LGPLv2.1 LICENSE.md "$work/"
cp "$d/COPYING" "$work/dav1d.COPYING"

echo "== DLL yopilmasi (MSYS2 $MSYSTEM)"
bin="$work/bin"
lic="$work/licenses"
mkdir -p "$bin" "$lic"
cp "$prefix/bin/ffmpeg.exe" "$prefix/bin/ffprobe.exe" "$prefix/bin/"*.dll "$bin/"
printf 'dll\tpackage\tversion\tlicense\n' >"$work/dlls.tsv"
queue=("$bin"/*.exe "$bin"/*.dll)
while ((${#queue[@]})); do
  file="${queue[0]}"
  queue=("${queue[@]:1}")
  while read -r dll; do
    [[ -e "$bin/$dll" ]] && continue
    from="$MINGW_PREFIX/bin/$dll"
    [[ -f "$from" ]] || continue  # Windows tizim DLL'i (KERNEL32, mfplat, ...)
    cp "$from" "$bin/"
    queue+=("$bin/$dll")
    pkg="$(pacman -Qqo "$from")"
    name="${pkg#"$MINGW_PACKAGE_PREFIX"-}"
    version="$(pacman -Q "$pkg" | cut -d' ' -f2)"
    license="$(pacman -Qi "$pkg" | sed -n 's/^Licenses *: *//p' | sed 's/spdx://g; s/  \+/ AND /g')"
    printf '%s\t%s\t%s\t%s\n' "$dll" "$name" "$version" "$license" >>"$work/dlls.tsv"
    mkdir -p "$lic/$name"
    { pacman -Qlq "$pkg" | grep -E '/share/licenses/.+[^/]$' || true; } | while read -r f; do cp "$f" "$lic/$name/"; done
    printf '{"packages":[{"name":"%s","versionInfo":"%s","licenseConcluded":"%s"}]}\n' \
      "$name" "$version" "$license" >"$lic/$name/sbom.spdx.json"
  done < <(objdump -p "$file" | sed -n 's/^[[:space:]]*DLL Name: //p' | tr -d '\r')
done
pacman -Q >"$work/msys2-packages.txt"
echo "== tayyor"
'@

function Get-Pin($name) {
  # FFmpeg versiyasi macOS bilan bir xil - yagona manba scripts/setup_local_render.py (gen_licenses.py ham shunday o'qiydi).
  $m = Select-String -Path "$Root\scripts\setup_local_render.py" -Pattern "^$name = `"(.+)`"" | Select-Object -First 1
  if (-not $m) { throw "scripts/setup_local_render.py da $name topilmadi" }
  return $m.Matches[0].Groups[1].Value
}

function Get-Download($url, $file, $sha256) {
  # Bir marta yuklanadi; SHA-256 har safar (qayta ishlatishda ham) tekshiriladi.
  if (-not (Test-Path $file)) {
    $ProgressPreference = "SilentlyContinue"
    # Windows PowerShell 5.1 standart holda eski TLS'ni taklif qilishi mumkin.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile "$file.part" -UseBasicParsing
    Move-Item -Force "$file.part" $file
  }
  if ((Get-FileHash -Algorithm SHA256 $file).Hash -ne $sha256) { throw "SHA-256 mos emas: $file (o'chirib qayta urining)" }
  return $file
}

function Get-MsysRoot { if ($env:LAHZA_MSYS2) { $env:LAHZA_MSYS2 } else { Join-Path $Src "msys2\msys64" } }

function Stop-Msys {
  # gpg-agent va boshqa fon jarayonlari papkani band qilib qolmasin.
  $msys = Get-MsysRoot
  Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($msys, [StringComparison]::OrdinalIgnoreCase) } |
    Stop-Process -Force -ErrorAction SilentlyContinue
}

function Initialize-Msys2 {
  $msys = Get-MsysRoot
  $bash = Join-Path $msys "usr\bin\bash.exe"
  $env:MSYSTEM = Get-Toml "msys2" "msystem"
  $env:CHERE_INVOKING = "1"
  $env:MSYS2_PATH_TYPE = "minimal"  # Windows PATH (Python, Git, ...) yig'ishga aralashmasin
  if (-not (Test-Path $bash)) {
    if ((Split-Path $msys -Leaf) -ne "msys64") { throw "LAHZA_MSYS2 ...\msys64 bilan tugashi kerak: $msys" }
    $dl = Join-Path $Src "downloads"
    New-Item -ItemType Directory -Force -Path $dl | Out-Null
    $sfx = Get-Download (Get-Toml "msys2" "url") "$dl\msys2-base-x86_64-$(Get-Toml 'msys2' 'version').sfx.exe" (Get-Toml "msys2" "sha256")
    $parent = Split-Path $msys -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    & $sfx -y "-o$parent" | Out-Null
    if (-not (Test-Path $bash)) { throw "MSYS2 ochilmadi: $msys" }
    # Birinchi ishga tushirish kalitlarni yaratadi; yadro yangilanishi bash'ni yopadi (chiqish kodi e'tiborsiz).
    # Out-Host: chiqish funksiya natijasiga ($bash) aralashmasin.
    & $bash -lc "pacman -Syuu --noconfirm --noprogressbar" | Out-Host
    Stop-Msys
  }
  & $bash -lc "pacman -Syuu --noconfirm --noprogressbar" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "pacman -Syuu xato bilan tugadi" }
  & $bash -lc "pacman -S --needed --noconfirm --noprogressbar $(Get-Toml 'msys2' 'packages')" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "MSYS2 paketlari o'rnatilmadi" }
  return $bash
}

function Get-FFmpegFlags {
  "$(Get-Toml 'ffmpeg' 'configure_common') $(Get-Toml 'ffmpeg' 'configure_windows') $(Get-Toml 'msys2' 'ffmpeg_extra')"
}

function Test-NonGplLicense([string]$expr) {
  # SPDX ifoda: AND qismlarining har biri GPL bo'lmagan muqobilga ega bo'lishi kerak.
  # LGPL va "GPL ... WITH GCC-exception" (libgcc/libstdc++ runtime) ruxsat etiladi. MSYS2'ning
  # "documentation:GPL-3.0" kabi doiraviy yozuvlari DLL'ga emas, paketdagi boshqa fayllarga tegishli.
  if (-not $expr.Trim()) { return $false }
  foreach ($part in (($expr -replace '[()]', ' ') -split '\s+AND\s+')) {
    if ($part.Trim() -match '^[a-z-]+:') { continue }
    $ok = $false
    foreach ($alt in ($part -split '\s+OR\s+')) {
      if ($alt -notmatch '(?<!L)GPL' -or $alt -match 'WITH\s+GCC-exception') { $ok = $true }
    }
    if (-not $ok) { return $false }
  }
  return $true
}

function Measure-Bright($file, $size) {
  $bytes = [IO.File]::ReadAllBytes($file)
  if ($bytes.Length -ne $size) { return 0 }
  $n = 0
  foreach ($b in $bytes) { if ($b -gt 100) { $n++ } }
  return $n
}

function Invoke-Native($exe, [string[]]$argv) {
  # Argumentlar massiv sifatida (PowerShell "-c:v" ni o'zining parametri deb o'qimasin); nol bo'lmagan kod - xato.
  & $exe @argv
  if ($LASTEXITCODE -ne 0) { throw "$([IO.Path]::GetFileName($exe)) xato bilan tugadi ($LASTEXITCODE): $argv" }
}

function Test-FFmpegLgpl($bin) {
  # setup_local_render.py validate() + smoke_test() ning Windows nusxasi. PATH faqat System32 -
  # bin papkasidan tashqaridagi (MSYS2) DLL'larga bog'liqlik qolmaganini ham isbotlaydi.
  $ff = Join-Path $bin "ffmpeg.exe"
  $probe = Join-Path $bin "ffprobe.exe"
  $savedPath = $env:Path
  $env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
  try {
    $conf = (& $ff -hide_banner -buildconf) -join "`n"
    if ($LASTEXITCODE -ne 0 -or -not $conf) { throw "ffmpeg.exe ishga tushmadi (DLL yetishmaydimi?): $ff" }
    $flags = $conf -split '\s+'
    foreach ($flag in "--enable-gpl", "--enable-nonfree", "--enable-version3") {
      if ($flags -contains $flag) { throw "FFmpeg konfiguratsiyasi rad etildi: $flag" }
    }
    $license = (& $ff -L) -join "`n"
    if (($license -replace '\s+', ' ') -notmatch "GNU Lesser General Public License") { throw "FFmpeg LGPL litsenziyasini ko'rsatmadi" }
    $filters = foreach ($line in (& $ff -hide_banner -filters)) {
      $p = -split $line
      if ($p.Count -ge 3 -and $p[2] -like "*->*") { $p[1] }
    }
    if ($filters -notcontains "ass" -or $filters -notcontains "subtitles") { throw "FFmpeg'da ass va subtitles filtrlari bo'lishi shart" }
    $decoders = foreach ($line in (& $ff -hide_banner -decoders)) { $p = -split $line; if ($p.Count -ge 2) { $p[1] } }
    if ($flags -notcontains "--enable-libdav1d" -or $decoders -notcontains "libdav1d") { throw "FFmpeg'da libdav1d (AV1) dekoderi yo'q" }
    if (Get-ChildItem $bin -Filter "*dav1d*.dll") { throw "dav1d alohida DLL bo'lib qolgan; statik kutilgan" }
    $encoders = foreach ($line in (& $ff -hide_banner -encoders)) { $p = -split $line; if ($p.Count -ge 2) { $p[1] } }
    $hw = @("h264_mf", "h264_amf", "h264_qsv", "hevc_mf", "hevc_amf", "hevc_qsv") | Where-Object { $encoders -contains $_ }
    if ($hw -notcontains "h264_mf") { throw "FFmpeg'da h264_mf (Media Foundation) enkoderi yo'q" }

    # Smoke test: o'zbekcha matn subtitles va ass filtrlari bilan yoqiladi, kadrda yorug' piksellar bo'lishi shart.
    $work = Join-Path (Split-Path $bin -Parent) "smoke"
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    Copy-Item "$Root\engine\src\lahza_engine\subtitle\fonts\Inter.ttf" $work
    $uz = [regex]::Unescape("O\u02BBzbekiston g\u02BBururi \u040E\u045E \u049A\u049B \u0492\u0493 \u04B2\u04B3 \u00D6\u00F6 \u011E\u011F \u015E\u015F \u00C7\u00E7")
    [IO.File]::WriteAllText("$work\sample.srt", "1`n00:00:00,000 --> 00:00:01,000`n$uz`n", $Utf8)
    $ass = @(
      "[Script Info]", "ScriptType: v4.00+", "PlayResX: 640", "PlayResY: 360", "",
      "[V4+ Styles]",
      "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
      "Style: Default,Inter,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,10,10,10,1", "",
      "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
      "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,$([regex]::Unescape('O\u02BBzbekcha sinov'))")
    [IO.File]::WriteAllText("$work\sample.ass", (($ass -join "`n") + "`n"), $Utf8)
    $source = @("-hide_banner", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=5:d=1")
    Push-Location $work
    try {
      # Nisbiy yo'llar: filtr argumentidagi ':' va bo'shliqlar muammo qilmaydi.
      Invoke-Native $ff ($source + @("-vf", "subtitles=sample.srt:fontsdir=.:force_style='FontName=Inter,FontSize=26'",
                                     "-c:v", "mpeg4", "-q:v", "3", "subtitled.mp4"))
      Invoke-Native $ff @("-v", "error", "-y", "-i", "subtitled.mp4", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "subtitled.gray")
      if ((Measure-Bright "$work\subtitled.gray" (640 * 360)) -lt 100) { throw "Subtitle smoke test: matn ko'rinmadi" }
      Invoke-Native $ff ($source + @("-vf", "ass=sample.ass:fontsdir=.", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "ass.gray"))
      if ((Measure-Bright "$work\ass.gray" (640 * 360)) -lt 100) { throw "ASS smoke test: matn ko'rinmadi" }
      Invoke-Native $probe @("-v", "error", "-show_streams", "subtitled.mp4") | Out-Null
      # h264_mf ishlashi apparat/MFT'ga bog'liq - natija faqat yoziladi (render/encoders.py o'zi tekshiradi).
      $quiet = @("-hide_banner", "-v", "quiet") + $source[3..($source.Count - 1)]
      & $ff @($quiet + @("-vf", "ass=sample.ass:fontsdir=.", "-c:v", "h264_mf", "-pix_fmt", "nv12", "h264_mf.mp4"))
      $mfOk = ($LASTEXITCODE -eq 0)
    } finally { Pop-Location }
  } finally { $env:Path = $savedPath }
  return [ordered]@{ buildconf = $conf; license = $license; hw_encoders = $hw; h264_mf_smoke = $mfOk }
}

function Install-FFmpeg($stage, $dest) {
  # Faqat o'zimizning fayllar almashtiriladi: boshqa runtime (llama, VC++) DLL'i bilan nom to'qnashuvi - xato.
  $listFile = Join-Path $dest "licenses\local-render\files.txt"
  $previous = @(if (Test-Path $listFile) { Get-Content $listFile })
  $files = @(Get-ChildItem $stage -File)
  foreach ($f in $files) {
    $t = Join-Path $dest $f.Name
    if ($f.Extension -eq ".dll" -and (Test-Path $t) -and $previous -notcontains $f.Name -and
        (Get-FileHash $t).Hash -ne (Get-FileHash $f.FullName).Hash) {
      throw "DLL nomi to'qnashuvi: $t boshqa runtime'ga tegishli va farq qiladi"
    }
  }
  foreach ($old in $previous) {
    if ($files.Name -notcontains $old) { Remove-Item (Join-Path $dest $old) -Force -ErrorAction SilentlyContinue }
  }
  $files | Copy-Item -Destination $dest -Force
  $notices = Join-Path $dest "licenses\local-render"
  if (Test-Path $notices) { Remove-Item $notices -Recurse -Force }
  New-Item -ItemType Directory -Force -Path (Split-Path $notices -Parent) | Out-Null
  Copy-Item (Join-Path $stage "licenses\local-render") $notices -Recurse
}

function Build-FFmpeg {
  $work = Join-Path $Src "ffmpeg-win"
  $ffVersion = Get-Pin "VERSION"
  $ffUrl = "https://ffmpeg.org/releases/ffmpeg-$ffVersion.tar.xz"
  $dav1dVersion = Get-Toml "dav1d" "version"
  $flags = Get-FFmpegFlags
  if ($Rebuild -or -not (Test-Path "$work\bin\ffmpeg.exe")) {
    $bash = Initialize-Msys2
    $dl = Join-Path $Src "downloads"
    New-Item -ItemType Directory -Force -Path $dl | Out-Null
    $env:LZ_FFMPEG_TAR = Get-Download $ffUrl "$dl\ffmpeg-$ffVersion.tar.xz" (Get-Pin "SHA256")
    $env:LZ_DAV1D_TAR = Get-Download (Get-Toml "dav1d" "url") "$dl\dav1d-$dav1dVersion.tar.xz" (Get-Toml "dav1d" "sha256")
    $env:LZ_FFMPEG_VERSION = $ffVersion
    $env:LZ_DAV1D_VERSION = $dav1dVersion
    $env:LZ_DAV1D_MESON = Get-Toml "dav1d" "meson_options"
    $env:LZ_FFMPEG_FLAGS = $flags
    $env:LZ_WORK = $work
    $sh = Join-Path $Src "ffmpeg-win.sh"
    [IO.File]::WriteAllText($sh, ($FFmpegBuildSh -replace "`r`n", "`n"), $Utf8)
    Write-Host "FFmpeg $ffVersion + dav1d $dav1dVersion yig'ilmoqda (MSYS2 $env:MSYSTEM); log: $work.log"
    & $bash -l ($sh -replace '\\', '/')
    $code = $LASTEXITCODE
    Stop-Msys
    if ($code -ne 0) { Get-Content "$work.log" -Tail 40; throw "FFmpeg yig'masi xato bilan tugadi; log: $work.log" }
  }

  # Litsenziya darvozasi: GPL DLL ilovaga kirmaydi.
  # Paket litsenziyasi paketdagi barcha fayllarni qamraydi; DLL'ning o'z litsenziyasi boshqacha bo'lsa,
  # runtimes.toml [msys2].dll_license_overrides da asos bilan yoziladi (manifest'da ikkalasi ham saqlanadi).
  $overrides = @{}
  foreach ($o in (-split (Get-Toml "msys2" "dll_license_overrides"))) { $k, $v = $o -split "=", 2; $overrides[$k] = $v }
  $dlls = @(Import-Csv "$work\dlls.tsv" -Delimiter "`t")
  foreach ($row in $dlls) {
    $row | Add-Member -NotePropertyName package_license -NotePropertyValue $row.license
    if ($overrides.ContainsKey($row.dll)) {
      $row.license = $overrides[$row.dll]
      $sbom = @{ packages = @(@{ name = $row.package; versionInfo = $row.version; licenseConcluded = $row.license }) }
      [IO.File]::WriteAllText("$work\licenses\$($row.package)\sbom.spdx.json", ($sbom | ConvertTo-Json -Depth 4), $Utf8)
    }
    if (-not (Test-NonGplLicense $row.license)) { throw "GPL (yoki noma'lum) litsenziyali DLL: $($row.dll) - $($row.package): '$($row.license)'" }
  }
  # Litsenziya matni MSYS2 paketida bo'lmasa (masalan libass) - runtimes.toml [msys2].license_urls dan
  # ({version} = paket versiyasi). Matnsiz paket qolsa - xato (ISC/MIT/BSD matnni ilova bilan berishni talab qiladi).
  $licenseUrls = @{}
  foreach ($o in (-split (Get-Toml "msys2" "license_urls"))) { $k, $v = $o -split "=", 2; $licenseUrls[$k] = $v }
  foreach ($row in $dlls) {
    $dir = "$work\licenses\$($row.package)"
    if (Get-ChildItem $dir -File | Where-Object Name -ne "sbom.spdx.json") { continue }
    if (-not $licenseUrls.ContainsKey($row.package)) { throw "$($row.package) paketida litsenziya matni yo'q - [msys2].license_urls ga qo'shing" }
    $url = $licenseUrls[$row.package] -replace '\{version\}', ($row.version -replace '-\d+$', '')
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $url -OutFile "$dir\$([IO.Path]::GetFileName($url))" -UseBasicParsing
  }
  $stage = Join-Path $work "bin"
  $notices = Join-Path $stage "licenses\local-render"
  if (Test-Path $notices) { Remove-Item $notices -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $notices | Out-Null
  Copy-Item "$work\COPYING.LGPLv2.1", "$work\LICENSE.md", "$work\dav1d.COPYING" $notices
  Get-ChildItem "$work\licenses" -Directory | Copy-Item -Destination $notices -Recurse

  # Boshqa (bo'shliqli) papkaga ko'chirib tekshirish: DLL'lar faqat exe yonidan yuklanishi shart.
  $relocated = Join-Path $work "relocated test"
  if (Test-Path $relocated) { Remove-Item $relocated -Recurse -Force }
  New-Item -ItemType Directory -Force -Path "$relocated\bin" | Out-Null
  Get-ChildItem $stage -File | Copy-Item -Destination "$relocated\bin"
  $check = Test-FFmpegLgpl "$relocated\bin"

  $manifest = [ordered]@{
    platform = "windows-x86_64"
    source = $ffUrl; sha256 = Get-Pin "SHA256"; version = $ffVersion
    configure = $flags
    buildconf = $check.buildconf; license = $check.license
    hw_encoders = $check.hw_encoders; h264_mf_smoke = $check.h264_mf_smoke
    dav1d = [ordered]@{ version = $dav1dVersion; source = Get-Toml "dav1d" "url"; sha256 = Get-Toml "dav1d" "sha256";
                        license = "BSD-2-Clause"; linkage = "static (avcodec DLL)"; av1_smoke_test = $false }
    msys2 = [ordered]@{ base = Get-Toml "msys2" "version"; msystem = Get-Toml "msys2" "msystem";
                        packages = [IO.File]::ReadAllLines("$work\msys2-packages.txt") }  # Get-Content PSPath'larni JSON'ga qo'shadi
    dlls = $dlls
    binary_sha256 = (Get-FileHash "$stage\ffmpeg.exe").Hash.ToLower()
  }
  [IO.File]::WriteAllText("$notices\manifest.json", ($manifest | ConvertTo-Json -Depth 6), $Utf8)
  [IO.File]::WriteAllText("$notices\files.txt", ((Get-ChildItem $stage -File).Name -join "`n") + "`n", $Utf8)
  Install-FFmpeg $stage $Out
  Write-Host "FFmpeg (LGPL) tayyor: $Out (DLL: $($dlls.Count) ta MSYS2 + FFmpeg; apparat enkoderlari: $($check.hw_encoders -join ', '))"
}

if ($FFmpegOnly) { Build-FFmpeg; exit 0 }

# CUDA bo'lsa NVIDIA uchun, aks holda Vulkan (AMD/Intel) yig'masi.
$Gpu = if ($env:LAHZA_GPU) { $env:LAHZA_GPU } else { "vulkan" }
$GgmlFlag = if ($Gpu -eq "cuda") { "-DGGML_CUDA=ON" } else { "-DGGML_VULKAN=ON" }
# Statik CRT (/MT): exe VC++ runtime DLL'lariga bog'lanmaydi - foydalanuvchi kompyuteridagi eski
# msvcp140.dll (masalan 14.28) llama/ggml ni access violation bilan qulatadi.
$CrtFlags = @("-DCMAKE_POLICY_DEFAULT_CMP0091=NEW", "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded")
# OpenMP o'chiq: MSVC'da vcomp140.dll (clang-cl'da libomp.dll) import qilinardi - /MT uni yo'qotmaydi;
# ggml o'z thread pool'ini ishlatadi. GGML_NATIVE=OFF: yig'ish kompyuterining CPU buyruqlari (AVX-512 va h.k.)
# boshqa kompyuterda "illegal instruction" bermasin.
$CrtFlags += @("-DGGML_OPENMP=OFF", "-DGGML_NATIVE=OFF")

$w = Checkout "whisper_cpp" "whisper.cpp"
cmake -S $w -B "$w\build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF $GgmlFlag @CrtFlags
cmake --build "$w\build" --config Release --target whisper-cli
Copy-Item "$w\build\bin\Release\whisper-cli.exe" $Out

$l = Checkout "llama_cpp" "llama.cpp"
cmake -S $l -B "$l\build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF $GgmlFlag @CrtFlags
cmake --build "$l\build" --config Release --target llama-server
Copy-Item "$l\build\bin\Release\llama-server.exe" $Out

Build-FFmpeg
Write-Host "whisper-cli, llama-server va FFmpeg tayyor: $Out"
