# AI IME v0.4 Deployment Script
# Must run in ADMIN PowerShell (Program Files (x86) requires admin)
#
# Usage:
#   1. Right-click Start menu -> "Windows PowerShell (Admin)" or "Terminal (Admin)"
#   2. Run: powershell -NoProfile -ExecutionPolicy Bypass -File "<path-to-this-script>"

$ErrorActionPreference = "Stop"

# Use $PSScriptRoot to avoid Chinese path encoding issues (UTF-8 vs GBK)
$src = Join-Path $PSScriptRoot "ai_ime"
$dst = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime"

Write-Host "=== AI IME v0.4 Deployment ===" -ForegroundColor Cyan
Write-Host "Source: $src"
Write-Host "Target: $dst"
Write-Host ""

# Check admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Admin privileges required! Right-click Start menu -> 'Windows PowerShell (Admin)' and rerun." -ForegroundColor Red
    exit 1
}

# Files to copy
$filesToCopy = @(
    @{ Src = "$src\ai_ime_ime.py"; Dst = "$dst\ai_ime_ime.py"; Name = "ai_ime_ime.py" },
    @{ Src = "$src\config.py"; Dst = "$dst\config.py"; Name = "config.py" },
    @{ Src = "$src\pinyin\candidates.py"; Dst = "$dst\pinyin\candidates.py"; Name = "pinyin\candidates.py" },
    @{ Src = "$src\pinyin\dict_loader.py"; Dst = "$dst\pinyin\dict_loader.py"; Name = "pinyin\dict_loader.py" },
    @{ Src = "$src\data\base_dict.txt"; Dst = "$dst\data\base_dict.txt"; Name = "data\base_dict.txt" }
)

Write-Host "[1/4] Checking source files..." -ForegroundColor Yellow
foreach ($f in $filesToCopy) {
    if (-not (Test-Path $f.Src)) {
        Write-Host "  [ERROR] Source not found: $($f.Src)" -ForegroundColor Red
        exit 1
    }
    $size = (Get-Item $f.Src).Length
    Write-Host "  OK $($f.Name) size=$size"
}

# Backup current deployment
Write-Host ""
Write-Host "[2/4] Backup current version..." -ForegroundColor Yellow
$backupDir = "$dst.v03.bak"
if (-not (Test-Path $backupDir)) {
    Copy-Item -Path $dst -Destination $backupDir -Recurse -Force
    Write-Host "  Backed up to: $backupDir"
} else {
    Write-Host "  Backup already exists, skip: $backupDir"
}

# Copy files
Write-Host ""
Write-Host "[3/4] Copying v0.4 files..." -ForegroundColor Yellow
foreach ($f in $filesToCopy) {
    Copy-Item -Path $f.Src -Destination $f.Dst -Force
    Write-Host "  OK $($f.Name)"
}

# Clear __pycache__ and restart PIMELauncher
Write-Host ""
Write-Host "[4/4] Clearing __pycache__ and restarting PIMELauncher..." -ForegroundColor Yellow
Remove-Item "$dst\pinyin\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$dst\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  __pycache__ cleared"

Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "C:\Program Files (x86)\PIME\PIMELauncher.exe"
Write-Host "  PIMELauncher restarted"

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Verification steps:"
Write-Host "  1. Open Notepad, switch to AI IME"
Write-Host "  2. Type 'n' -> candidates should show Chinese chars starting with n (simple pinyin)"
Write-Host "  3. Type 'nh' -> candidates should show phrase like ni-hao (phrase simple pinyin)"
Write-Host "  4. Type 'nihao' + Space -> should commit the phrase (full pinyin)"
Write-Host "  5. Press '-' / '=' to page up/down"
Write-Host "  6. Check log: %LOCALAPPDATA%\PIME\Log\ai_ime_debug.log"
Write-Host "     Should see 'Dict loaded: 74000+ entries'"
Write-Host ""
Write-Host "Quick log view command:"
Write-Host '  Get-Content "$env:LOCALAPPDATA\PIME\Log\ai_ime_debug.log" -Tail 20 -Wait'
