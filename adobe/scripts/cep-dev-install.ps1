# Lahza After Effects CEP paneli — dev o'rnatish (Windows).
#   * foydalanuvchi extensions papkasiga junction: %APPDATA%\Adobe\CEP\extensions\uz.lahza.ae
#   * imzosiz panel uchun: HKCU\Software\Adobe\CSXS.<N>  PlayerDebugMode = "1" (String)
# Manba: Adobe-CEP/CEP-Resources, CEP_12.x "CEP 12 HTML Extension Cookbook".
# Faqat joriy foydalanuvchi (HKCU, %APPDATA%) — administrator huquqi kerak emas (junction admin talab qilmaydi).
#
# Foydalanish:  powershell -ExecutionPolicy Bypass -File adobe\scripts\cep-dev-install.ps1 [-Uninstall] [-Csxs 11,12]
param(
  [switch]$Uninstall,
  [int[]]$Csxs = @(11, 12)
)
$ErrorActionPreference = "Stop"

$BundleId = "uz.lahza.ae"
$Src = (Resolve-Path (Join-Path $PSScriptRoot "..\after-effects")).Path
$ExtDir = Join-Path $env:APPDATA "Adobe\CEP\extensions"
$Link = Join-Path $ExtDir $BundleId

if ($Src.Contains("#")) { Write-Warning "Yo'lda '#' bor — CEP bunday papkani yuklamaydi (Cookbook)." }

if ($Uninstall) {
  if (Test-Path $Link) {
    $item = Get-Item $Link -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      # junction'ni o'chirish manba papkaga tegmaydi
      $item.Delete()
      Write-Host "O'chirildi: $Link"
    } else {
      Write-Error "$Link junction emas — qo'lda tekshiring."
    }
  } else { Write-Host "Junction yo'q: $Link" }
  Write-Host "PlayerDebugMode o'zgartirilmadi. Qaytarish: Remove-ItemProperty HKCU:\Software\Adobe\CSXS.<N> -Name PlayerDebugMode"
  exit 0
}

if (-not (Test-Path (Join-Path $Src "dist\main.js"))) {
  Write-Error "dist\ yo'q — avval: cd adobe\after-effects; npm install; npm run build"
}

New-Item -ItemType Directory -Force -Path $ExtDir | Out-Null
if (Test-Path $Link) {
  $item = Get-Item $Link -Force
  if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    Write-Error "$Link mavjud va junction emas — o'chirmayman."
  }
  $item.Delete()
}
New-Item -ItemType Junction -Path $Link -Target $Src | Out-Null
Write-Host "Junction: $Link -> $Src"

foreach ($v in $Csxs) {
  $key = "HKCU:\Software\Adobe\CSXS.$v"
  if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
  New-ItemProperty -Path $key -Name "PlayerDebugMode" -Value "1" -PropertyType String -Force | Out-Null
  Write-Host "PlayerDebugMode=1: $key"
}

Write-Host ""
Write-Host "Tayyor. After Effects'ni qayta ishga tushiring: Window > Extensions > Lahza."
Write-Host "Debug: Chrome'da http://localhost:8098 (adobe\after-effects\.debug)."
