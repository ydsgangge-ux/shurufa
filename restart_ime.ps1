$regPath = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\AI IME_is1"
$installDir = $null

if (Test-Path $regPath) {
    $installDir = (Get-ItemProperty -Path $regPath -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation
}

if (-not $installDir) {
    $pf = [Environment]::GetFolderPath("ProgramFilesX86")
    $paths = @(
        "$pf\AI_IME",
        "$pf\PIME"
    )
    foreach ($p in $paths) {
        if (Test-Path "$p\PIMELauncher.exe") {
            $installDir = $p
            break
        }
    }
}

if (-not $installDir) {
    Write-Host "[ERROR] PIME installation not found."
    Read-Host "Press Enter to exit"
    exit 1
}

$launcher = "$installDir\PIMELauncher.exe"
if (-not (Test-Path $launcher)) {
    Write-Host "[ERROR] PIMELauncher.exe not found: $launcher"
    Read-Host "Press Enter to exit"
    exit 1
}

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[WARNING] Not running as Administrator!"
    Write-Host "  Restarting with elevated privileges..."
    $script = $MyInvocation.MyCommand.Path
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$script`""
    exit 0
}

Write-Host "========================================"
Write-Host "  AI IME Restart Tool"
Write-Host "========================================"
Write-Host ""
Write-Host "[1/4] Stopping PIMELauncher and Python server..."
Write-Host "  (Killing process tree...)"

# 1. 杀掉 PIMELauncher 及其所有子进程
taskkill /F /T /IM PIMELauncher.exe 2>$null

# 2. 兜底：杀掉 AI_IME 目录下的残留 python 进程
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" 2>$null |
    Where-Object { $_.ExecutablePath -like "*AI_IME*" -or $_.CommandLine -like "*AI_IME*" } |
    ForEach-Object {
        Write-Host "  Killing leftover python PID: $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Write-Host ""
Write-Host "[2/4] Waiting for processes to fully exit..."
Write-Host "  (Need 5 seconds to release ports and resources)"

# 等待5秒确保进程完全退出、端口释放
Start-Sleep -Seconds 5

# 确认进程已退出
$stillRunning = Get-Process -Name PIMELauncher -ErrorAction SilentlyContinue
if ($stillRunning) {
    Write-Host "  [WARNING] PIMELauncher still running, force killing again..."
    taskkill /F /T /IM PIMELauncher.exe 2>$null
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "[3/4] Starting PIMELauncher..."
Start-Process $launcher

Write-Host ""
Write-Host "[4/4] Waiting for Python server to initialize..."
Write-Host "  (Loading 360k+ dictionary entries, please wait...)"

# 等待Python server完全启动（最多等15秒）
$ready = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-Process -Name PIMELauncher -ErrorAction SilentlyContinue
    if ($proc -and -not $proc.HasExited) {
        $ready = $true
        Write-Host "  PIMELauncher is running ($i s)"
        # 再等2秒让Python server完全就绪
        Start-Sleep -Seconds 2
        break
    }
    Write-Host "  Waiting... ($i s)"
}

Write-Host ""
if ($ready) {
    Write-Host "========================================"
    Write-Host "  SUCCESS! Input method restarted."
    Write-Host "  Lexicon reloaded. You can type now."
    Write-Host "========================================"
} else {
    Write-Host "========================================"
    Write-Host "  [WARNING] PIMELauncher may not have started."
    Write-Host "  Please start it manually: $launcher"
    Write-Host "========================================"
}

Start-Sleep -Seconds 3
