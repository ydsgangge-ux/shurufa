# 下载 AI 模型
# 用法：.\download_model.ps1
# 默认下载 qwen2.5-0.5b-instruct-q4_k_m（约 400MB）

$ErrorActionPreference = "Stop"
$modelDir = Join-Path $PSScriptRoot "models"

if (-not (Test-Path $modelDir)) {
    New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
}

# 检查是否已有模型
$existing = Get-ChildItem "$modelDir\*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Write-Host "已有模型: $($existing.Name) ($([math]::Round($existing.Length/1MB, 0))MB)" -ForegroundColor Green
    $answer = Read-Host "是否重新下载？(y/N)"
    if ($answer -ne "y" -and $answer -ne "Y") { exit 0 }
}

# 模型信息
$modelName = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
$modelUrl = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
$modelPath = Join-Path $modelDir $modelName

Write-Host ""
Write-Host "下载模型: $modelName" -ForegroundColor Cyan
Write-Host "来源: HuggingFace (Qwen2.5-0.5B-Instruct Q4_K_M)" -ForegroundColor Gray
Write-Host "大小: 约 400MB" -ForegroundColor Gray
Write-Host "目标: $modelPath" -ForegroundColor Gray
Write-Host ""

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host "开始下载..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath -UseBasicParsing
    Write-Host "下载完成！模型已保存到: $modelPath" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 下载失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "手动下载方法：" -ForegroundColor Yellow
    Write-Host "  1. 访问 https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF" -ForegroundColor Gray
    Write-Host "  2. 下载 qwen2.5-0.5b-instruct-q4_k_m.gguf" -ForegroundColor Gray
    Write-Host "  3. 放到 $modelDir 目录" -ForegroundColor Gray
    Write-Host ""
    Write-Host "也可以使用其他 .gguf 模型（如 qwen3:0.6b），放到 models/ 目录即可" -ForegroundColor Gray
    if (Test-Path $modelPath) { Remove-Item $modelPath -Force -ErrorAction SilentlyContinue }
    exit 1
}
