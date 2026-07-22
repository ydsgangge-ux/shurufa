# AI IME - Download local model
# Usage: .\download_model.ps1
# Model: Qwen2.5-0.5B-Instruct-GGUF (Q4_0, ~400MB)

$ErrorActionPreference = "Stop"

$ModelName = "qwen2.5-0.5b-instruct-q4_0.gguf"
$DownloadUrl = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_0.gguf"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ModelsDir = Join-Path $ScriptDir "python\input_methods\ai_ime\models"

if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}

$ModelPath = Join-Path $ModelsDir $ModelName

if (Test-Path $ModelPath) {
    $size = [math]::Round((Get-Item $ModelPath).Length / 1MB, 1)
    Write-Host ("Model exists: " + $ModelPath + " (" + $size + " MB)") -ForegroundColor Green
    Write-Host "Delete the file first if you want to re-download." -ForegroundColor Yellow
    exit 0
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI IME - Download Local Model" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ("Model: " + $ModelName)
Write-Host ("Target: " + $ModelPath)
Write-Host ""

$tempPath = $ModelPath + ".download"

# Clean up any leftover temp file from previous failed attempt
if (Test-Path $tempPath) {
    Remove-Item $tempPath -Force -ErrorAction SilentlyContinue
}

Write-Host "Downloading from HuggingFace..." -ForegroundColor Yellow
Write-Host ("URL: " + $DownloadUrl)
Write-Host ""

try {
    # WebClient handles redirects automatically and streams to disk
    $webClient = New-Object System.Net.WebClient
    $webClient.Proxy = [System.Net.WebRequest]::GetSystemWebProxy()
    $webClient.Proxy.Credentials = [System.Net.CredentialCache]::DefaultCredentials

    # Download with progress using event
    $webClient.DownloadFile($DownloadUrl, $tempPath)

    # Verify download
    if (-not (Test-Path $tempPath)) {
        throw "Download file not created"
    }

    $downloadedSize = (Get-Item $tempPath).Length
    if ($downloadedSize -lt 100000) {
        throw "Downloaded file too small ($downloadedSize bytes), likely an error page"
    }

    # Rename to final path
    Move-Item -Force $tempPath $ModelPath

    $finalMB = [math]::Round((Get-Item $ModelPath).Length / 1MB, 1)
    Write-Host ""
    Write-Host ("Download complete: " + $ModelPath) -ForegroundColor Green
    Write-Host ("Size: " + $finalMB + " MB") -ForegroundColor Green
    Write-Host ""
    Write-Host "Local AI prediction is now ready!" -ForegroundColor Cyan

}
catch {
    Write-Host ""
    Write-Host ("Download failed: " + $_.Exception.Message) -ForegroundColor Red

    # Clean up temp file
    if (Test-Path $tempPath) {
        Start-Sleep -Milliseconds 500
        try { Remove-Item $tempPath -Force -ErrorAction Stop } catch {}
    }

    Write-Host ""
    Write-Host "Manual download:" -ForegroundColor Yellow
    Write-Host ("1. Open in browser: " + $DownloadUrl)
    Write-Host ("2. Save as: " + $ModelPath)
    exit 1
}
