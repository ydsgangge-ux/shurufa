# Deploy v0.9.4 - Fix: seg mode creates phrase for full result
# Run in ADMIN PowerShell

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime"

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "[ERROR] Admin required!" -ForegroundColor Red; exit 1 }

Write-Host "=== Deploy v0.9.4 ===" -ForegroundColor Cyan

$nestedDir = Join-Path $dst "ai_ime"
if (Test-Path $nestedDir) { Remove-Item $nestedDir -Recurse -Force }

$files = @(
    @("ai_ime\ai_ime_ime.py", "ai_ime_ime.py"),
    @("ai_ime\config.py", "config.py"),
    @("ai_ime\user_memory.py", "user_memory.py"),
    @("ai_ime\pinyin\candidates.py", "pinyin\candidates.py"),
    @("ai_ime\pinyin\dict_loader.py", "pinyin\dict_loader.py"),
    @("ai_ime\pinyin\parser.py", "pinyin\parser.py"),
    @("ai_ime\data\base_dict.txt", "data\base_dict.txt")
)

Write-Host "Copying files..." -ForegroundColor Yellow
foreach ($f in $files) {
    $srcFile = Join-Path $src $f[0]
    $dstFile = Join-Path $dst $f[1]
    $dstDir = Split-Path $dstFile -Parent
    if (-not (Test-Path $srcFile)) { Write-Host "  [ERROR] Missing: $($f[0])" -ForegroundColor Red; exit 1 }
    if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
    Copy-Item -Path $srcFile -Destination $dstFile -Force
    Write-Host "  OK $($f[1])"
}

foreach ($d in @("$dst\__pycache__", "$dst\pinyin\__pycache__")) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force; Write-Host "  Cleared pycache" }
}

# Also remove old user_memory.json so freq 9999 takes effect
$oldMem = Join-Path $dst "data\user_memory.json"
if (Test-Path $oldMem) { Remove-Item $oldMem -Force; Write-Host "  Cleared old user_memory.json" }

Write-Host "Restarting PIMELauncher..." -ForegroundColor Yellow
Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "C:\Program Files (x86)\PIME\PIMELauncher.exe"
Write-Host "=== Deploy v0.9.4 Complete ===" -ForegroundColor Green
Write-Host "Fix: segment mode now creates phrase for full result (e.g. duo+xiang=duo xiang)"
