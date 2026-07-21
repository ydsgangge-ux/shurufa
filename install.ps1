# AI 输入法 - 一键安装脚本
# 在管理员 PowerShell 中运行
# 用法：右键 → 以管理员身份运行 PowerShell → .\install.ps1

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$pimeDir = "C:\Program Files (x86)\PIME"
$dst = "$pimeDir\python\input_methods\ai_ime"

# ===== 检查管理员权限 =====
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] 需要管理员权限！请右键 PowerShell 以管理员身份运行" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI 输入法 - 一键安装" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ===== Step 1: 检查 PIME =====
Write-Host "[Step 1/5] 检查 PIME 框架..." -ForegroundColor Yellow

if (-not (Test-Path $pimeDir)) {
    Write-Host "  PIME 未安装，正在下载安装..." -ForegroundColor Yellow

    # 下载 PIME 安装包
    $pimeUrl = "https://github.com/EasyIME/PIME/releases/download/v1.3.0-stable/PIME-1.3.0-stable-x86.exe"
    $pimeInstaller = "$env:TEMP\PIME-installer.exe"

    try {
        Write-Host "  下载 PIME v1.3.0..." -ForegroundColor Gray
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $pimeUrl -OutFile $pimeInstaller -UseBasicParsing
        Write-Host "  启动 PIME 安装程序..." -ForegroundColor Gray
        Start-Process $pimeInstaller -Wait
        Remove-Item $pimeInstaller -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "  [WARN] 自动下载失败: $_" -ForegroundColor Yellow
        Write-Host "  请手动安装 PIME: https://github.com/EasyIME/PIME/releases" -ForegroundColor Yellow
        Write-Host "  安装后重新运行此脚本" -ForegroundColor Yellow
        Read-Host "按回车退出"
        exit 1
    }
}

if (Test-Path $pimeDir) {
    Write-Host "  PIME 已安装: $pimeDir" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] PIME 安装失败，请手动安装后重试" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# ===== Step 2: 安装 Python 依赖 =====
Write-Host ""
Write-Host "[Step 2/5] 安装 Python 依赖..." -ForegroundColor Yellow

# 查找系统 Python（非 PIME 内置的 3.8 32位）
$python = $null
foreach ($py in @("python", "python3", "py")) {
    try {
        $result = & $py -c "import sys; print(sys.executable)" 2>$null
        if ($result -and $result -notmatch "PIME") {
            $python = $py
            break
        }
    } catch {}
}

if ($python) {
    Write-Host "  找到系统 Python: $python" -ForegroundColor Gray

    # 检查 llama-cpp-python
    $hasLlama = & $python -c "import llama_cpp; print('ok')" 2>$null
    if ($hasLlama -eq "ok") {
        Write-Host "  llama-cpp-python 已安装" -ForegroundColor Green
    } else {
        Write-Host "  安装 llama-cpp-python（本地 AI 引擎）..." -ForegroundColor Gray
        & $python -m pip install llama-cpp-python --quiet 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  llama-cpp-python 安装成功" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] llama-cpp-python 安装失败，本地 AI 不可用（可使用云端 API）" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [WARN] 未找到系统 Python，本地 AI 不可用（可使用云端 API）" -ForegroundColor Yellow
    Write-Host "  如需本地 AI，请安装 Python 3.10+: https://www.python.org/downloads/" -ForegroundColor Gray
}

# ===== Step 3: 下载模型 =====
Write-Host ""
Write-Host "[Step 3/5] 检查 AI 模型..." -ForegroundColor Yellow

$modelDir = Join-Path $src "models"
$modelFile = $null
if (Test-Path $modelDir) {
    $modelFile = Get-ChildItem "$modelDir\*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
}

if ($modelFile) {
    Write-Host "  模型已存在: $($modelFile.Name) ($([math]::Round($modelFile.Length/1MB, 0))MB)" -ForegroundColor Green
} else {
    Write-Host "  未找到 .gguf 模型文件" -ForegroundColor Yellow
    Write-Host "  可选操作：" -ForegroundColor Gray
    Write-Host "    A) 运行 download_model.ps1 下载 qwen2.5-0.5b（约 400MB）" -ForegroundColor Gray
    Write-Host "    B) 手动下载 .gguf 模型放到 models/ 目录" -ForegroundColor Gray
    Write-Host "    C) 不用本地 AI，使用云端 API（见下方配置说明）" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  本地 AI 为可选项，不影响基础输入法功能" -ForegroundColor Gray
}

# ===== Step 4: 部署输入法文件 =====
Write-Host ""
Write-Host "[Step 4/5] 部署输入法文件..." -ForegroundColor Yellow

# 清理旧的嵌套目录
$nestedDir = Join-Path $dst "ai_ime"
if (Test-Path $nestedDir) {
    Remove-Item $nestedDir -Recurse -Force
    Write-Host "  清理旧嵌套目录" -ForegroundColor Gray
}

$files = @(
    @("ai_ime\ai_ime_ime.py", "ai_ime_ime.py"),
    @("ai_ime\config.py", "config.py"),
    @("ai_ime\user_memory.py", "user_memory.py"),
    @("ai_ime\__init__.py", "__init__.py"),
    @("ai_ime\ime.json", "ime.json"),
    @("ai_ime\ai\__init__.py", "ai\__init__.py"),
    @("ai_ime\ai\ollama_client.py", "ai\ollama_client.py"),
    @("ai_ime\ai\cloud_client.py", "ai\cloud_client.py"),
    @("ai_ime\ai\local_llm_client.py", "ai\local_llm_client.py"),
    @("ai_ime\ai\predictor.py", "ai\predictor.py"),
    @("ai_ime\ai\lexicon_expander.py", "ai\lexicon_expander.py"),
    @("ai_ime\pinyin\__init__.py", "pinyin\__init__.py"),
    @("ai_ime\pinyin\candidates.py", "pinyin\candidates.py"),
    @("ai_ime\pinyin\dict_loader.py", "pinyin\dict_loader.py"),
    @("ai_ime\pinyin\parser.py", "pinyin\parser.py"),
    @("ai_ime\pinyin\syllables.py", "pinyin\syllables.py"),
    @("ai_ime\data\base_dict.txt", "data\base_dict.txt"),
    @("local_llm_server.py", "local_llm_server.py")
)

$okCount = 0
foreach ($f in $files) {
    $srcFile = Join-Path $src $f[0]
    $dstFile = Join-Path $dst $f[1]
    $dstDir = Split-Path $dstFile -Parent
    if (-not (Test-Path $srcFile)) {
        Write-Host "  [WARN] 缺少: $($f[0])" -ForegroundColor Yellow
        continue
    }
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }
    Copy-Item -Path $srcFile -Destination $dstFile -Force
    $okCount++
}

# 清理 Python 缓存
foreach ($d in @("$dst\__pycache__", "$dst\pinyin\__pycache__", "$dst\ai\__pycache__")) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force }
}

Write-Host "  部署完成: $okCount 个文件" -ForegroundColor Green

# ===== Step 5: 重启 PIME =====
Write-Host ""
Write-Host "[Step 5/5] 重启输入法服务..." -ForegroundColor Yellow

Stop-Process -Name PIMELauncher -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "$pimeDir\PIMELauncher.exe"
Write-Host "  PIMELauncher 已重启" -ForegroundColor Green

# ===== 完成 =====
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "使用方法：" -ForegroundColor Cyan
Write-Host "  1. 打开任意文本编辑器" -ForegroundColor Gray
Write-Host "  2. 切换到「AI输入法」（Win+空格 或 点击语言栏）" -ForegroundColor Gray
Write-Host "  3. 输入拼音即可使用" -ForegroundColor Gray
Write-Host ""
Write-Host "可选配置 - 云端 AI（推荐，效果更好）：" -ForegroundColor Cyan
Write-Host "  1. 创建目录 C:\Users\$env:USERNAME\.ai_ime\" -ForegroundColor Gray
Write-Host "  2. 创建文件 api_config.json，内容：" -ForegroundColor Gray
Write-Host '     {"api_key":"sk-xxx","api_base":"https://api.deepseek.com/v1","model":"deepseek-v4-flash"}' -ForegroundColor Gray
Write-Host "  3. 重启输入法（运行 deploy_v10.ps1）" -ForegroundColor Gray
Write-Host ""
Write-Host "可选配置 - 本地 AI（无需网络，但需要模型）：" -ForegroundColor Cyan
Write-Host "  运行 download_model.ps1 下载模型" -ForegroundColor Gray
Write-Host ""
