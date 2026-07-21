# 构建安装包 - 一键打包 EXE
# 用法：.\build_installer.ps1
# 需要：Inno Setup 6（自动下载安装）

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI 输入法 - 构建安装包" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ===== 检查 Inno Setup =====
$innoPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $innoPath)) {
    Write-Host "[1/4] 安装 Inno Setup 6..." -ForegroundColor Yellow
    $innoInstaller = "$env:TEMP\inno-setup.exe"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://files.jrsoftware.org/is/6/innosetup-6.3.3.exe" -OutFile $innoInstaller -UseBasicParsing
        Start-Process $innoInstaller -ArgumentList "/SILENT", "/ALLUSERS" -Wait
        Remove-Item $innoInstaller -Force -ErrorAction SilentlyContinue
        Write-Host "  Inno Setup 安装完成" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Inno Setup 安装失败: $_" -ForegroundColor Red
        Write-Host "  请手动安装: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
        Read-Host "按回车退出"
        exit 1
    }
} else {
    Write-Host "[1/4] Inno Setup 已安装" -ForegroundColor Green
}

# ===== 检查模型文件 =====
Write-Host ""
Write-Host "[2/4] 检查模型文件..." -ForegroundColor Yellow

$modelDir = Join-Path $src "models"
$hasModel = $false
if (Test-Path $modelDir) {
    $modelFile = Get-ChildItem "$modelDir\*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($modelFile) {
        $hasModel = $true
        Write-Host "  模型: $($modelFile.Name) ($([math]::Round($modelFile.Length/1MB, 0))MB)" -ForegroundColor Green
    }
}

if (-not $hasModel) {
    Write-Host "  [WARN] 未找到模型文件" -ForegroundColor Yellow
    Write-Host "  安装包将不包含本地 AI 模型（用户可用云端 API 替代）" -ForegroundColor Gray
    $answer = Read-Host "  是否继续？(Y/n)"
    if ($answer -eq "n" -or $answer -eq "N") { exit 0 }
}

# ===== 检查输入法文件 =====
Write-Host ""
Write-Host "[3/4] 检查输入法文件..." -ForegroundColor Yellow

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
    Write-Host "  [ERROR] 缺少文件:" -ForegroundColor Red
    foreach ($f in $missing) { Write-Host "    $f" -ForegroundColor Red }
    Read-Host "按回车退出"
    exit 1
}
Write-Host "  所有文件就绪 ($($requiredFiles.Count) 个)" -ForegroundColor Green

# ===== 编译安装包 =====
Write-Host ""
Write-Host "[4/4] 编译安装包..." -ForegroundColor Yellow

$outputDir = Join-Path $src "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# 更新 setup.iss 中的版本号（可选）
$issFile = Join-Path $src "setup.iss"

& $innoPath $issFile /O"$outputDir" 2>&1 | ForEach-Object {
    if ($_ -match "Successful|Error|Warning") {
        Write-Host "  $_" -ForegroundColor $(if ($_ -match "Error") { "Red" } elseif ($_ -match "Warning") { "Yellow" } else { "Green" })
    }
}

# 检查结果
$setupFile = Get-ChildItem "$outputDir\AI*_Setup_*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($setupFile) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  构建成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  安装包: $($setupFile.FullName)" -ForegroundColor Cyan
    Write-Host "  大小: $([math]::Round($setupFile.Length/1MB, 1))MB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  上传到 GitHub Releases:" -ForegroundColor Gray
    Write-Host "  1. 创建 GitHub Release（如 v1.0.0）" -ForegroundColor Gray
    Write-Host "  2. 上传 $($setupFile.Name)" -ForegroundColor Gray
    Write-Host "  3. 用户下载后双击安装即可" -ForegroundColor Gray
} else {
    Write-Host "  [ERROR] 构建失败，请检查 setup.iss" -ForegroundColor Red
}
