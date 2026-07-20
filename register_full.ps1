# -*- coding: ascii -*-
# Register AI IME to TSF (requires admin)
# Fix: .reg UTF-8 import lost Description string value
# Note: All Chinese chars use Unicode escape; paths use $PSScriptRoot to avoid PS5 GBK decoding issues

$ErrorActionPreference = "Continue"
# Use $PSScriptRoot so we don't hardcode Chinese paths in source
$root = $PSScriptRoot
$logPath = Join-Path $root "register_full_log.txt"
$startTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"=== AI IME TSF Register Start $startTime ===" | Out-File -FilePath $logPath -Encoding utf8

# Chinese string "AI输入法" via Unicode escape (no literal Chinese in source)
$desc = "AI" + [char]0x8F93 + [char]0x5165 + [char]0x6CD5
$pimeClsid = "{35F67E9D-A54D-4177-9697-8B0AB71A9E04}"
$aiImeGuid = "{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"

# --- 1. Fix 64-bit LanguageProfile ---
"--- 1. Fix 64-bit LanguageProfile ---" | Out-File -FilePath $logPath -Encoding utf8 -Append
$key64 = "HKLM:\SOFTWARE\Microsoft\CTF\TIP\$pimeClsid\LanguageProfile\0x00000804\$aiImeGuid"
if (-not (Test-Path $key64)) {
    New-Item -Path $key64 -Force | Out-Null
    "  Created key: $key64" | Out-File -FilePath $logPath -Encoding utf8 -Append
}
Set-ItemProperty -Path $key64 -Name "Description" -Value $desc -Type String
Set-ItemProperty -Path $key64 -Name "IconFile" -Value "" -Type String
Set-ItemProperty -Path $key64 -Name "IconIndex" -Value 0 -Type DWord
$check64 = Get-ItemProperty -Path $key64
"  Verify: Description='$($check64.Description)' IconFile='$($check64.IconFile)' IconIndex=$($check64.IconIndex)" | Out-File -FilePath $logPath -Encoding utf8 -Append

# --- 2. Fix 32-bit LanguageProfile ---
"--- 2. Fix 32-bit LanguageProfile ---" | Out-File -FilePath $logPath -Encoding utf8 -Append
$key32 = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\$pimeClsid\LanguageProfile\0x00000804\$aiImeGuid"
if (-not (Test-Path $key32)) {
    New-Item -Path $key32 -Force | Out-Null
    "  Created key: $key32" | Out-File -FilePath $logPath -Encoding utf8 -Append
}
Set-ItemProperty -Path $key32 -Name "Description" -Value $desc -Type String
Set-ItemProperty -Path $key32 -Name "IconFile" -Value "" -Type String
Set-ItemProperty -Path $key32 -Name "IconIndex" -Value 0 -Type DWord
$check32 = Get-ItemProperty -Path $key32
"  Verify: Description='$($check32.Description)' IconFile='$($check32.IconFile)' IconIndex=$($check32.IconIndex)" | Out-File -FilePath $logPath -Encoding utf8 -Append

# --- 3. Check PIMETextService DLL COM registration ---
"--- 3. Check PIMETextService DLL COM reg ---" | Out-File -FilePath $logPath -Encoding utf8 -Append
$clsidKey = "HKLM:\SOFTWARE\Classes\CLSID\$pimeClsid"
if (Test-Path $clsidKey) {
    $inproc = Get-ItemProperty -Path "$clsidKey\InprocServer32" -ErrorAction SilentlyContinue
    "  CLSID registered, InprocServer32='$($inproc.'(default)')'" | Out-File -FilePath $logPath -Encoding utf8 -Append
} else {
    "  WARNING: CLSID $pimeClsid not registered under HKLM\SOFTWARE\Classes\CLSID" | Out-File -FilePath $logPath -Encoding utf8 -Append
}

# --- 4. Summary ---
"--- 4. Summary ---" | Out-File -FilePath $logPath -Encoding utf8 -Append
"  PIME TextService CLSID: $pimeClsid" | Out-File -FilePath $logPath -Encoding utf8 -Append
"  AI IME Profile GUID: $aiImeGuid" | Out-File -FilePath $logPath -Encoding utf8 -Append
"  Language ID: 0x00000804 (zh-CN)" | Out-File -FilePath $logPath -Encoding utf8 -Append
"  Description: $desc" | Out-File -FilePath $logPath -Encoding utf8 -Append
$endTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"=== Register Done $endTime ===" | Out-File -FilePath $logPath -Encoding utf8 -Append

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Register OK. Log: $logPath" -ForegroundColor Green
Write-Host "Description = $desc" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
