# Deploy v1.2 - AI Triple Engine (Local LLM + Cloud API + Ollama)
# Run in ADMIN PowerShell

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = "C:\Program Files (x86)\PIME\python\input_methods\ai_ime"

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "[ERROR] Admin required!" -ForegroundColor Red; exit 1 }

Write-Host "=== Deploy v1.2 - AI Triple Engine ===" -ForegroundColor Cyan

$nestedDir = Join-Path $dst "ai_ime"
if (Test-Path $nestedDir) { Remove-Item $nestedDir -Recurse -Force }

$files = @(
    @("ai_ime\ai_ime_ime.py", "ai_ime_ime.py"),
    @("ai_ime\config.py", "config.py"),
    @("ai_ime\user_memory.py", "user_memory.py"),
    @("ai_ime\__init__.py", "__init__.py"),
    @("ai_ime\ai\__init__.py", "ai\__init__.py"),
    @("ai_ime\ai\ollama_client.py", "ai\ollama_client.py"),
    @("ai_ime\ai\cloud_client.py", "ai\cloud_client.py"),
    @("ai_ime\ai\local_llm_client.py", "ai\local_llm_client.py"),
    @("ai_ime\ai\predictor.py", "ai\predictor.py"),
    @("ai_ime\ai\lexicon_expander.py", "ai\lexicon_expander.py"),
    @("ai_ime\pinyin\candidates.py", "pinyin\candidates.py"),
    @("ai_ime\pinyin\dict_loader.py", "pinyin\dict_loader.py"),
    @("ai_ime\pinyin\parser.py", "pinyin\parser.py"),
    @("ai_ime\pinyin\syllables.py", "pinyin\syllables.py"),
    @("ai_ime\data\base_dict.txt", "data\base_dict.txt"),
    @("local_llm_server.py", "local_llm_server.py")
)

Write-Host "Copying files..." -ForegroundColor Yellow
foreach ($f in $files) {
    $srcFile = Join-Path $src $f[0]
    $dstFile = Join-Path $dst $f[1]
    $dstDir = Split-Path $dstFile -Parent
    if (-not (Test-Path $srcFile)) { Write-Host "  [WARN] Missing: $($f[0])" -ForegroundColor Yellow; continue }
    if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
    Copy-Item -Path $srcFile -Destination $dstFile -Force
    Write-Host "  OK $($f[1])"
}

foreach ($d in @("$dst\__pycache__", "$dst\pinyin\__pycache__", "$dst\ai\__pycache__")) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force; Write-Host "  Cleared pycache" }
}

Write-Host "Restarting PIMELauncher..." -ForegroundColor Yellow
Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "C:\Program Files (x86)\PIME\PIMELauncher.exe"
Write-Host "=== Deploy v1.2 Complete ===" -ForegroundColor Green
Write-Host "AI Engines: Local LLM (qwen2.5-0.5b) + Cloud API (DeepSeek) + Ollama"
Write-Host "Cloud API: edit C:\Users\$env:USERNAME\.ai_ime\api_config.json"