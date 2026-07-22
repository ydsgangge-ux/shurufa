# 从已安装的 PIME 提取核心运行时文件到 pime_runtime/ 目录
# 用法：.\extract_pime_runtime.ps1
# 前提：本机已安装 PIME 1.3.0

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$pimeInstall = "C:\Program Files (x86)\PIME"
$outDir = Join-Path $src "pime_runtime"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  提取 PIME 核心运行时" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 PIME 是否已安装
if (-not (Test-Path $pimeInstall)) {
    Write-Host "[ERROR] PIME 未安装在 $pimeInstall" -ForegroundColor Red
    Write-Host "请先安装 PIME: https://github.com/EasyIME/PIME/releases" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}

# 清空输出目录
if (Test-Path $outDir) {
    Remove-Item $outDir -Recurse -Force
}
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

Write-Host "提取 PIME 核心运行时文件..." -ForegroundColor Yellow
Write-Host "  源: $pimeInstall" -ForegroundColor Gray
Write-Host "  目标: $outDir" -ForegroundColor Gray
Write-Host ""

# ===== 1. PIMELauncher.exe =====
Copy-Item "$pimeInstall\PIMELauncher.exe" "$outDir\PIMELauncher.exe" -Force
Write-Host "  [OK] PIMELauncher.exe" -ForegroundColor Green

# ===== 2. TSF 驱动 DLL (x86 + x64) =====
New-Item -ItemType Directory -Path "$outDir\x86" -Force | Out-Null
New-Item -ItemType Directory -Path "$outDir\x64" -Force | Out-Null
Copy-Item "$pimeInstall\x86\PIMETextService.dll" "$outDir\x86\PIMETextService.dll" -Force
Copy-Item "$pimeInstall\x64\PIMETextService.dll" "$outDir\x64\PIMETextService.dll" -Force
Write-Host "  [OK] x86/PIMETextService.dll" -ForegroundColor Green
Write-Host "  [OK] x64/PIMETextService.dll" -ForegroundColor Green

# ===== 3. backends.json + version.txt =====
Copy-Item "$pimeInstall\backends.json" "$outDir\backends.json" -Force
Copy-Item "$pimeInstall\version.txt" "$outDir\version.txt" -Force
Write-Host "  [OK] backends.json" -ForegroundColor Green
Write-Host "  [OK] version.txt" -ForegroundColor Green

# ===== 4. Python 运行时 (python/python3/) =====
$pySrc = "$pimeInstall\python\python3"
$pyDst = "$outDir\python\python3"
New-Item -ItemType Directory -Path $pyDst -Force | Out-Null

# 核心 Python 文件
$pyFiles = @(
    "python.exe", "pythonw.exe", "python3.dll", "python38.dll", "python38.zip",
    "vcruntime140.dll", "PIME.pth", "LICENSE.txt",
    "libcrypto-1_1.dll", "libffi-7.dll", "libssl-1_1.dll", "sqlite3.dll",
    "pyexpat.pyd", "select.pyd", "unicodedata.pyd", "winsound.pyd",
    "_asyncio.pyd", "_bz2.pyd", "_ctypes.pyd", "_decimal.pyd",
    "_elementtree.pyd", "_hashlib.pyd", "_lzma.pyd", "_msi.pyd",
    "_multiprocessing.pyd", "_overlapped.pyd", "_queue.pyd",
    "_socket.pyd", "_sqlite3.pyd", "_ssl.pyd"
)

foreach ($f in $pyFiles) {
    $srcFile = Join-Path $pySrc $f
    if (Test-Path $srcFile) {
        Copy-Item $srcFile (Join-Path $pyDst $f) -Force
    } else {
        Write-Host "  [WARN] Missing: $f" -ForegroundColor Yellow
    }
}

# tornado 库（PIME server 依赖）
if (Test-Path "$pySrc\tornado") {
    Copy-Item "$pySrc\tornado" "$pyDst\tornado" -Recurse -Force
}
# pip 等标准库包（python38.zip 内含大部分，但部分需额外目录）
foreach ($pkgDir in @("pip", "setuptools", "distutils", "wheel", "importlib", "encodings", "collections", "asyncio", "concurrent", "urllib", "http", "email", "html", "xml", "logging", "unittest", "lib2to3", "json", "zoneinfo", "pydoc_data", "wsgiref")) {
    $pkgPath = Join-Path $pySrc $pkgDir
    if (Test-Path $pkgPath) {
        Copy-Item $pkgPath (Join-Path $pyDst $pkgDir) -Recurse -Force
    }
}

Write-Host "  [OK] python/python3/ (运行时)" -ForegroundColor Green

# ===== 5. PIME Python 服务端核心文件 =====
$pyServerDst = "$outDir\python"
New-Item -ItemType Directory -Path $pyServerDst -Force | Out-Null

Copy-Item "$pimeInstall\python\server.py" "$pyServerDst\server.py" -Force
Copy-Item "$pimeInstall\python\serviceManager.py" "$pyServerDst\serviceManager.py" -Force
Copy-Item "$pimeInstall\python\textService.py" "$pyServerDst\textService.py" -Force
Copy-Item "$pimeInstall\python\keycodes.py" "$pyServerDst\keycodes.py" -Force
Write-Host "  [OK] python/server.py + serviceManager.py + textService.py + keycodes.py" -ForegroundColor Green

# ===== 6. input_methods 目录（空的，后面由安装脚本放 ai_ime） =====
New-Item -ItemType Directory -Path "$outDir\python\input_methods" -Force | Out-Null
# 放入 __init__.py
if (Test-Path "$pimeInstall\python\input_methods\__init__.py") {
    Copy-Item "$pimeInstall\python\input_methods\__init__.py" "$outDir\python\input_methods\__init__.py" -Force
} else {
    # PIME 可能没有这个文件，创建一个空的
    "" | Out-File "$outDir\python\input_methods\__init__.py" -Encoding ascii
}
Write-Host "  [OK] python/input_methods/ (空，仅含 __init__.py)" -ForegroundColor Green

# ===== 7. 不包含 PIME 自带输入法（chewing 等） =====
Write-Host "  [SKIP] PIME 自带输入法（chewing 等）- 不提取" -ForegroundColor Gray

# ===== 8. 不包含 libchewing、opencc =====
Write-Host "  [SKIP] libchewing, opencc - AI 输入法不需要" -ForegroundColor Gray

# ===== 统计大小 =====
$totalSize = (Get-ChildItem $outDir -Recurse | Measure-Object -Property Length -Sum).Sum
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  提取完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  目录: $outDir" -ForegroundColor Cyan
Write-Host "  大小: $([math]::Round($totalSize/1MB, 1)) MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "  下一步: 运行 .\build_installer.ps1 构建安装包" -ForegroundColor Gray
