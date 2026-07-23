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
    Write-Host "PIME installation not found."
    Read-Host "Press Enter to exit"
    exit 1
}

$launcher = "$installDir\PIMELauncher.exe"
if (-not (Test-Path $launcher)) {
    Write-Host "PIMELauncher.exe not found: $launcher"
    Read-Host "Press Enter to exit"
    exit 1
}

Stop-Process -Name "PIMELauncher" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process $launcher
Write-Host "Done."
Start-Sleep -Seconds 2
