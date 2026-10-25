# Windows dasturchi buyruqlari:
#   .\scripts\dev.ps1 setup | test | test-offline | lint | check-versions | licenses | ci | engine | ui | sidecar
param([Parameter(Mandatory = $true)]
  [ValidateSet("setup", "test", "test-offline", "lint", "check-versions", "licenses", "ci", "engine", "ui", "sidecar")]
  [string]$Cmd)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\.."
$Py = Join-Path $Root "engine\.venv\Scripts\python.exe"

# Tashqi buyruq xato bilan tugasa to'xtash ($ErrorActionPreference native buyruqlarga ta'sir qilmaydi).
function Invoke-Checked([scriptblock]$Block) {
  & $Block
  if ($LASTEXITCODE -ne 0) { throw "Buyruq xato bilan tugadi (kod $LASTEXITCODE)" }
}

function Test-Engine {
  Push-Location "$Root\engine"
  try { Invoke-Checked { & $Py -m pytest } } finally { Pop-Location }
}

function Invoke-Lint {
  Push-Location $Root
  try { Invoke-Checked { & $Py -m ruff check engine/src engine/tests eval scripts } } finally { Pop-Location }
}

function Test-Versions { Invoke-Checked { & $Py "$Root\scripts\check_versions.py" } }

switch ($Cmd) {
  "setup" {
    Invoke-Checked { python -m venv (Join-Path $Root "engine\.venv") }
    Invoke-Checked { & $Py -m pip install -e "$Root\engine[dev,onnx,fonts]" }
    Push-Location "$Root\app"; try { Invoke-Checked { npm ci } } finally { Pop-Location }
  }
  "test" {
    Test-Engine
    Push-Location "$Root\app"; try { Invoke-Checked { node --test tests/*.test.mjs }; Invoke-Checked { npm run typecheck } } finally { Pop-Location }
  }
  "test-offline" {
    $env:LAHZA_NO_NETWORK = "1"
    try { Test-Engine } finally { Remove-Item Env:LAHZA_NO_NETWORK }
  }
  "lint" { Invoke-Lint }
  "check-versions" { Test-Versions }
  "licenses" { Invoke-Checked { & $Py "$Root\scripts\gen_licenses.py" } }
  "ci" {
    Test-Versions
    Invoke-Lint
    $env:LAHZA_NO_NETWORK = "1"
    try { Test-Engine } finally { Remove-Item Env:LAHZA_NO_NETWORK }
    Push-Location "$Root\app"; try { Invoke-Checked { node --test tests/*.test.mjs }; Invoke-Checked { npm run build } } finally { Pop-Location }
  }
  "engine" {
    $env:LAHZA_DEV = "1"; $env:LAHZA_TOKEN = "dev-token"
    $env:LAHZA_CATALOG = Join-Path $Root "catalog\catalog.json"
    & $Py -m lahza_engine serve --port 8765
  }
  "ui" {
    $env:VITE_ENGINE_URL = "http://127.0.0.1:8765"; $env:VITE_ENGINE_TOKEN = "dev-token"
    Push-Location "$Root\app"; npm run dev; Pop-Location
  }
  "sidecar" { Invoke-Checked { & $Py "$Root\scripts\build_sidecar.py" } }
}
