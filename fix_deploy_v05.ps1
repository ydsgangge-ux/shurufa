# Fix deployment: copy v0.5 files to correct locations
# The deploy_v05.ps1 put files in ai_ime\ai_ime\ instead of ai_ime\
# This script copies from the nested dir to the correct level
#
# Run in ADMIN PowerShell:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<path>"

$ErrorActionPreference = "Stop"

$dst = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime"
$src = $PSScriptRoot

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Admin privileges required!" -ForegroundColor Red
    exit 1
}

Write-Host "=== Fix v0.5 Deployment ===" -ForegroundColor Cyan

# Remove the wrongly nested ai_ime\ai_ime\ directory
$nestedDir = Join-Path $dst "ai_ime"
if (Test-Path $nestedDir) {
    Write-Host "Removing nested ai_ime\ai_ime\ directory..."
    Remove-Item $nestedDir -Recurse -Force
    Write-Host "  Removed." -ForegroundColor Green
}

# Copy all source files to correct locations
Write-Host "Copying v0.5 files from source..." -ForegroundColor Yellow

$copyMap = @{
    "ai_ime\ai_ime_ime.py" = "ai_ime_ime.py"
    "ai_ime\config.py" = "config.py"
    "ai_ime\user_memory.py" = "user_memory.py"
    "ai_ime\pinyin\candidates.py" = "pinyin\candidates.py"
    "ai_ime\pinyin\dict_loader.py" = "pinyin\dict_loader.py"
    "ai_ime\pinyin\parser.py" = "pinyin\parser.py"
    "ai_ime\data\base_dict.txt" = "data\base_dict.txt"
}

foreach ($entry in $copyMap.GetEnumerator()) {
    $srcFile = Join-Path $src $entry.Key
    $dstFile = Join-Path $dst $entry.Value
    $dstDir = Split-Path $dstFile -Parent
    if (-not (Test-Path $srcFile)) {
        Write-Host "  [ERROR] Missing source: $($entry.Key)" -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }
    Copy-Item -Path $srcFile -Destination $dstFile -Force
    $size = (Get-Item $dstFile).Length
    Write-Host "  OK $($entry.Value) ($size bytes)"
}

# Clear __pycache__
Write-Host "Clearing __pycache__..." -ForegroundColor Yellow
$pycacheDirs = @(
    "$dst\__pycache__",
    "$dst\pinyin\__pycache__"
)
foreach ($d in $pycacheDirs) {
    if (Test-Path $d) {
        Remove-Item $d -Recurse -Force
        Write-Host "  Cleared: $d"
    }
}

# Restart PIMELauncher
Write-Host "Restarting PIMELauncher..." -ForegroundColor Yellow
Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "C:\Program Files (x86)\PIME\PIMELauncher.exe"
Write-Host "  PIMELauncher restarted." -ForegroundColor Green

Write-Host ""
Write-Host "=== Fix Complete ===" -ForegroundColor Green
Write-Host "Try typing in Notepad now."
