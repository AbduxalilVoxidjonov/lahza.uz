# Lahza Adobe plaginlari + mustaqil "Lahza Engine" servisi — o'rnatish (Windows, ADB-7).
# Bu imzolangan o'rnatuvchi EMAS (u ADB-9). Tartib va izohlar: docs/12-adobe-plaginlar.md, 3.3-bo'lim.
#
#   1. Engine servisi: `lahza install-service` -> Task Scheduler vazifasi \Lahza\Engine (kirishda, joriy foydalanuvchi,
#      LeastPrivilege — administrator kerak emas).
#   2. After Effects paneli (CEP): adobe\scripts\cep-dev-install.ps1 (junction + PlayerDebugMode).
#   3. Premiere paneli (UXP): -Ccx berilsa UPIA bilan, aks holda yo'riqnoma.
#
# Foydalanish:
#   powershell -ExecutionPolicy Bypass -File scripts\install_adobe_engine.ps1 `
#       [-AppDir "$env:LOCALAPPDATA\Lahza Studio"] [-Ccx file.ccx] [-SkipPlugins] [-DryRun] [-Uninstall]
#   -AppDir  o'rnatilgan Lahza Studio papkasi (lahza-engine.exe shu yerda); berilmasa — repo'dagi engine\.venv (dev).
# ESLATMA: Windows'da hali qo'lda sinalmagan (docs/12 3.3 "Windows'da qo'lda sinash").
param(
  [string]$AppDir = "",
  [string]$Ccx = "",
  [switch]$SkipPlugins,
  [switch]$DryRun,
  [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Upia = Join-Path ${env:ProgramFiles} "Common Files\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe"

function Invoke-Step([string]$Exe, [string[]]$ArgList) {
  if ($DryRun) { Write-Host "[dry-run] $Exe $($ArgList -join ' ')" } else { & $Exe @ArgList }
}

# ---- Engine buyrug'i ---------------------------------------------------------------------------
if ($AppDir) {
  $EngineExe = Join-Path $AppDir "lahza-engine.exe"
  if (-not (Test-Path $EngineExe)) { Write-Error "Sidecar topilmadi: $EngineExe" }
  $EnginePre = @()
  # Desktop sidecar'i bilan bir xil resurslar (Tauri resource_dir = o'rnatish papkasi).
  $env:LAHZA_BIN_DIR = Join-Path $AppDir "bin"
  $env:LAHZA_CATALOG = Join-Path $AppDir "catalog\catalog.json"
} else {
  $EngineExe = Join-Path $Root "engine\.venv\Scripts\python.exe"
  if (-not (Test-Path $EngineExe)) { Write-Error "engine\.venv yo'q — avval engine muhitini o'rnating (scripts\dev.ps1)." }
  $EnginePre = @("-m", "lahza_engine")
  # Shu repo'dagi engine kodi; PYTHONPATH servis muhitiga ham o'tadi (service-env.json).
  $env:PYTHONPATH = Join-Path $Root "engine\src"
}

# Chiqish Out-Host'ga: funksiya natijasi faqat chiqish kodi bo'lsin.
function Invoke-Engine([string[]]$ArgList) { & $EngineExe @($EnginePre + $ArgList) | Out-Host; return $LASTEXITCODE }

if ($Uninstall) {
  $a = @("uninstall-service"); if ($DryRun) { $a += "--dry-run" }
  $null = Invoke-Engine $a
  if (-not $SkipPlugins) {
    Invoke-Step "powershell" @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "adobe\scripts\cep-dev-install.ps1"), "-Uninstall")
    Write-Host "Premiere paneli: Creative Cloud Desktop > Plugins orqali o'chiriladi."
  }
  exit 0
}

# ---- 1. Engine servisi -------------------------------------------------------------------------
Write-Host "== 1/3 Lahza Engine servisi (Task Scheduler \Lahza\Engine)"
$a = @("install-service"); if ($DryRun) { $a += "--dry-run" }
if ((Invoke-Engine $a) -ne 0) { Write-Error "install-service xato bilan tugadi" }
if (-not $DryRun) { Start-Sleep -Seconds 3; $null = Invoke-Engine @("service-status") }

if ($SkipPlugins) { exit 0 }

# ---- 2. After Effects (CEP) --------------------------------------------------------------------
Write-Host "== 2/3 After Effects paneli (CEP)"
if (Test-Path (Join-Path $Root "adobe\after-effects\dist\main.js")) {
  Invoke-Step "powershell" @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "adobe\scripts\cep-dev-install.ps1"))
} else {
  Write-Host "O'tkazib yuborildi: adobe\after-effects\dist yo'q — cd adobe\after-effects; npm install; npm run build"
}

# ---- 3. Premiere Pro (UXP) ---------------------------------------------------------------------
Write-Host "== 3/3 Premiere Pro paneli (UXP)"
if ($Ccx) {
  if (Test-Path $Upia) { Invoke-Step $Upia @("/install", $Ccx) }
  else { Write-Host "UPIA topilmadi. .ccx faylini ikki marta bosing: $Ccx" }
} else {
  Write-Host "Dev rejim: Premiere > Settings > Plugins > Developer Mode; UXP Developer Tool > adobe\premiere\dist\manifest.json > Load."
}

Write-Host ""
Write-Host "Tayyor. Panel engine'ni %LOCALAPPDATA%\Lahza Studio\engine.json orqali topadi."
Write-Host "Holat: lahza service-status · O'chirish: scripts\install_adobe_engine.ps1 -Uninstall"
