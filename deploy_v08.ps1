# Deploy v0.8 - Segment confirmation mode
# Files: ai_ime_ime.py, candidates.py
# Run in ADMIN PowerShell:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<path>"

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime"

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Admin privileges required!" -ForegroundColor Red
    exit 1
}

Write-Host "=== Deploy v0.8 ===" -ForegroundColor Cyan

# Remove nested dir if exists
$nestedDir = Join-Path $dst "ai_ime"
if (Test-Path $nestedDir) {
    Remove-Item $nestedDir -Recurse -Force
    Write-Host "  Removed nested dir."
}

# Copy files
$copyMap = @{
    "ai_ime\ai_ime_ime.py" = "ai_ime_ime.py"
    "ai_ime\config.py" = "config.py"
    "ai_ime\user_memory.py" = "user_memory.py"
    "ai_ime\pinyin\candidates.py" = "pinyin\candidates.py"
    "ai_ime\pinyin\dict_loader.py" = "pinyin\dict_loader.py"
    "ai_ime\pinyin\parser.py" = "pinyin\parser.py"
    "ai_ime\data\base_dict.txt" = "data\base_dict.txt"
}

Write-Host "Copying files..." -ForegroundColor Yellow
foreach ($entry in $copyMap.GetEnumerator()) {
    $srcFile = Join-Path $src $entry.Key
    $dstFile = Join-Path $dst $entry.Value
    $dstDir = Split-Path $dstFile -Parent
    if (-not (Test-Path $srcFile)) {
        Write-Host "  [ERROR] Missing: $($entry.Key)" -ForegroundColor Red
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
foreach ($d in @("$dst\__pycache__", "$dst\pinyin\__pycache__")) {
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
Write-Host "=== Deploy v0.8 Complete ===" -ForegroundColor Green
Write-Host "New: segment-by-segment confirmation mode"
Write-Host "  Type long pinyin -> auto split into segments"
Write-Host "  Space = confirm current segment, move to next"
Write-Host "  1-9 = select alternative for current segment"
Write-Host "  Backspace = undo last confirmed segment"
