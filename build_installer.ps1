# Build installer - one-click packaging EXE (standalone)
# Usage: .\build_installer.ps1
# Requires: Inno Setup 6 (auto-download), PIME 1.3.0 installed (for runtime extraction)

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI IME - Build Installer (Standalone)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ===== [1/5] Check Inno Setup =====
$innoPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $innoPath)) {
    Write-Host "[1/5] Installing Inno Setup 6..." -ForegroundColor Yellow
    $innoInstaller = [string]::Concat($env:TEMP, "\inno-setup.exe")
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://files.jrsoftware.org/is/6/innosetup-6.3.3.exe" -OutFile $innoInstaller -UseBasicParsing
        Start-Process $innoInstaller -ArgumentList "/SILENT", "/ALLUSERS" -Wait
        Remove-Item $innoInstaller -Force -ErrorAction SilentlyContinue
        Write-Host "  Inno Setup installed" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Inno Setup install failed: $_" -ForegroundColor Red
        Write-Host "  Please install manually: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "[1/5] Inno Setup found" -ForegroundColor Green
}

# ===== [2/5] Check PIME runtime =====
Write-Host ""
$pimeRuntimeDir = Join-Path $src "pime_runtime"
$pimeNeedExtract = $false

if (Test-Path $pimeRuntimeDir) {
    $criticalFiles = @(
        (Join-Path $pimeRuntimeDir "PIMELauncher.exe"),
        (Join-Path $pimeRuntimeDir "x86\PIMETextService.dll"),
        (Join-Path $pimeRuntimeDir "x64\PIMETextService.dll"),
        (Join-Path $pimeRuntimeDir "python\server.py"),
        (Join-Path $pimeRuntimeDir "python\python3\python.exe")
    )
    $missingRuntime = @()
    foreach ($cf in $criticalFiles) {
        if (-not (Test-Path $cf)) {
            $missingRuntime += $cf
        }
    }
    if ($missingRuntime.Count -eq 0) {
        $rtSizeRaw = (Get-ChildItem $pimeRuntimeDir -Recurse | Measure-Object -Property Length -Sum).Sum
        $rtSize = [math]::Round($rtSizeRaw / 1MB, 1)
        Write-Host ([string]::Format("[2/5] PIME runtime ready ({0} MB)", $rtSize)) -ForegroundColor Green
    } else {
        $pimeNeedExtract = $true
    }
} else {
    $pimeNeedExtract = $true
}

if ($pimeNeedExtract) {
    Write-Host "[2/5] Extracting PIME runtime..." -ForegroundColor Yellow
    $extractScript = Join-Path $src "extract_pime_runtime.ps1"
    if (-not (Test-Path $extractScript)) {
        Write-Host "  [ERROR] extract_pime_runtime.ps1 not found" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    & $extractScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] PIME runtime extraction failed" -ForegroundColor Red
        Write-Host "  Make sure PIME is installed: https://github.com/EasyIME/PIME/releases" -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# ===== [3/5] Check model files =====
Write-Host ""
Write-Host "[3/5] Checking model files..." -ForegroundColor Yellow

$modelDir = Join-Path $src "models"
$hasModel = $false
if (Test-Path $modelDir) {
    $modelFile = Get-ChildItem (Join-Path $modelDir "*.gguf") -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($modelFile) {
        $hasModel = $true
        $modelSizeMB = [math]::Round($modelFile.Length / 1MB, 0)
        Write-Host ([string]::Format("  Model: {0} ({1} MB)", $modelFile.Name, $modelSizeMB)) -ForegroundColor Green
    }
}

if (-not $hasModel) {
    Write-Host "  [WARN] No model file found" -ForegroundColor Yellow
    Write-Host "  Installer will not include local AI model (users can use cloud API instead)" -ForegroundColor Gray
    $answer = Read-Host "  Continue? (Y/n)"
    if ($answer -eq "n" -or $answer -eq "N") { exit 0 }
}

# ===== [4/5] Check input method files =====
Write-Host ""
Write-Host "[4/5] Checking input method files..." -ForegroundColor Yellow

$requiredFiles = @(
    "ai_ime\ai_ime_ime.py",
    "ai_ime\config.py",
    "ai_ime\user_memory.py",
    "ai_ime\__init__.py",
    "ai_ime\ime.json",
    "ai_ime\ai\__init__.py",
    "ai_ime\ai\cloud_client.py",
    "ai_ime\ai\local_llm_client.py",
    "ai_ime\ai\ollama_client.py",
    "ai_ime\ai\predictor.py",
    "ai_ime\ai\lexicon_expander.py",
    "ai_ime\pinyin\__init__.py",
    "ai_ime\pinyin\candidates.py",
    "ai_ime\pinyin\dict_loader.py",
    "ai_ime\pinyin\parser.py",
    "ai_ime\pinyin\syllables.py",
    "ai_ime\data\base_dict.txt",
    "local_llm_server.py"
)

$missing = @()
foreach ($f in $requiredFiles) {
    if (-not (Test-Path (Join-Path $src $f))) {
        $missing += $f
    }
}

if ($missing.Count -gt 0) {
    Write-Host "  [ERROR] Missing files:" -ForegroundColor Red
    foreach ($f in $missing) { Write-Host "    $f" -ForegroundColor Red }
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ([string]::Format("  All files ready ({0} files)", $requiredFiles.Count)) -ForegroundColor Green

# ===== [5/5] Compile installer =====
Write-Host ""
Write-Host "[5/5] Compiling installer..." -ForegroundColor Yellow

$outputDir = Join-Path $src "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$issFile = Join-Path $src "setup.iss"

& $innoPath $issFile /O"$outputDir" 2>&1 | ForEach-Object {
    if ($_ -match "Successful|Error|Warning") {
        $color = "Green"
        if ($_ -match "Error") { $color = "Red" }
        elseif ($_ -match "Warning") { $color = "Yellow" }
        Write-Host "  $_" -ForegroundColor $color
    }
}

# Check result
$setupFile = Get-ChildItem (Join-Path $outputDir "AI*_Setup_*.exe") -ErrorAction SilentlyContinue | Select-Object -First 1
if ($setupFile) {
    $setupSizeMB = [math]::Round($setupFile.Length / 1MB, 1)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Build successful!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host ([string]::Format("  Installer: {0}", $setupFile.FullName)) -ForegroundColor Cyan
    Write-Host ([string]::Format("  Size: {0} MB", $setupSizeMB)) -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Features:" -ForegroundColor Gray
    Write-Host "  - Standalone: no need to install PIME separately" -ForegroundColor Gray
    Write-Host "  - Embedded: PIME runtime + Python 3.8" -ForegroundColor Gray
    Write-Host "  - Only registers AI IME, no PIME built-in methods" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Upload to GitHub Releases:" -ForegroundColor Gray
    Write-Host "  1. Create GitHub Release (e.g. v1.1.0)" -ForegroundColor Gray
    Write-Host ([string]::Format("  2. Upload {0}", $setupFile.Name)) -ForegroundColor Gray
    Write-Host "  3. Users download, install, Win+Space to switch" -ForegroundColor Gray
} else {
    Write-Host "  [ERROR] Build failed, check setup.iss" -ForegroundColor Red
}
