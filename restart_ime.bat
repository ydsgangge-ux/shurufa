@echo off
title AI IME Restart
cd /d "%~dp0"

:: Check admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c %~dp0restart_ime.bat' -Verb RunAs"
    exit /b
)

powershell -ExecutionPolicy Bypass -File "%~dp0restart_ime.ps1"
pause
