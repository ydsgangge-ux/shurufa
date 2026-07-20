# Deploy v0.5 to PIME
# Backup goes to PROJECT directory (NOT input_methods/) to avoid ModuleNotFoundError
# Run in ADMIN PowerShell:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<path-to-this-script>"

$ErrorActionPreference = "Stop"

# Use $PSScriptRoot for automatic path resolution
$src = $PSScriptRoot
$dst = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime"

# Backup directory in PROJECT (not in input_methods/)
$backupDir = Join-Path $src "backups\ai_ime.v04"

Write-Host "=== Deploy v0.5 to PIME ===" -ForegroundColor Cyan
Write-Host "Source: $src"
Write-Host "Target: $dst"
Write-Host ""

# 1. Check admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Admin privileges required!" -ForegroundColor Red
    Write-Host "Right-click Start menu -> 'Windows PowerShell (Admin)' and rerun."
    exit 1
}
Write-Host "[1/5] Admin check: OK" -ForegroundColor Green

# 2. Check source files
Write-Host "[2/5] Checking source files..." -ForegroundColor Yellow
$files = @(
    "ai_ime\ai_ime_ime.py",
    "ai_ime\config.py",
    "ai_ime\user_memory.py",
    "ai_ime\pinyin\candidates.py",
    "ai_ime\pinyin\dict_loader.py",
    "ai_ime\pinyin\parser.py",
    "ai_ime\data\base_dict.txt"
)
foreach ($f in $files) {
    $p = Join-Path $src $f
    if (-not (Test-Path $p)) {
        Write-Host "  [ERROR] Missing: $p" -ForegroundColor Red
        exit 1
    }
    $size = (Get-Item $p).Length
    Write-Host "  OK $f ($size bytes)"
}

# 3. Backup current version to PROJECT directory
Write-Host "[3/5] Backup current version to: $backupDir" -ForegroundColor Yellow
if (Test-Path $backupDir) {
    Write-Host "  Backup exists, removing old..."
    Remove-Item $backupDir -Recurse -Force
}
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -Path $dst -Destination $backupDir -Recurse -Force
Write-Host "  Backup complete." -ForegroundColor Green

# 4. Copy v0.5 files
Write-Host "[4/5] Copying v0.5 files..." -ForegroundColor Yellow
foreach ($f in $files) {
    $srcFile = Join-Path $src $f
    $dstFile = Join-Path $dst $f
    $dstDir = Split-Path $dstFile -Parent
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }
    Copy-Item -Path $srcFile -Destination $dstFile -Force
    Write-Host "  OK $f"
}

# 5. Clear __pycache__ and restart PIMELauncher
Write-Host "[5/5] Clearing __pycache__ and restarting PIMELauncher..." -ForegroundColor Yellow
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

Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "C:\Program Files (x86)\PIME\PIMELauncher.exe"
Write-Host "  PIMELauncher restarted." -ForegroundColor Green

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Backup: $backupDir"
Write-Host "Try typing in Notepad now."
Write-Host ""
Write-Host "Test cases:"
Write-Host "  changyong -> chang yong (full pinyin)"
Write-Host "  changy    -> chang y (mixed)"
Write-Host "  cyong     -> c yong (mixed)"
Write-Host "  ,         -> fullwidth comma"
Write-Host "  Select a word, type again -> should rank higher"
