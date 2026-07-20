# Cleanup script: remove backup directory that breaks PIME scanning
# The backup dir "ai_ime.v03.bak" contains ime.json, which PIME tries to load
# as a separate input method named "ai_ime.v03", causing ModuleNotFoundError.
#
# Run in ADMIN PowerShell:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<path-to-this-script>"

$ErrorActionPreference = "Stop"

$backupDir = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime.v03.bak"

Write-Host "=== Cleanup ai_ime.v03.bak ===" -ForegroundColor Cyan

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Admin privileges required!" -ForegroundColor Red
    exit 1
}

if (Test-Path $backupDir) {
    Write-Host "Removing: $backupDir"
    Remove-Item $backupDir -Recurse -Force
    Write-Host "Removed successfully." -ForegroundColor Green
} else {
    Write-Host "Backup dir not found, nothing to remove: $backupDir"
}

# Restart PIMELauncher to clear cache
Write-Host ""
Write-Host "Restarting PIMELauncher..." -ForegroundColor Yellow
Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "C:\Program Files (x86)\PIME\PIMELauncher.exe"
Write-Host "PIMELauncher restarted." -ForegroundColor Green

Write-Host ""
Write-Host "=== Cleanup Complete ===" -ForegroundColor Green
Write-Host "Now try typing in Notepad again."
