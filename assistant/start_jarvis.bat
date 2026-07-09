@echo off
title JARVIS Launcher

cd /d C:\Users\admin\jarvis-ai

echo ============================================
echo Starting JARVIS Voice Server...
echo ============================================

start "JARVIS Voice Server" /min cmd /k ^
"C:\Users\admin\jarvis-ai\external\JarvisLuxTTS\.venv-tts\Scripts\python.exe -m uvicorn tts_server:app --app-dir C:\Users\admin\jarvis-ai\external\JarvisLuxTTS --host 127.0.0.1 --port 8765"

echo Waiting for JARVIS Voice Server...

powershell -NoProfile -Command ^
"$deadline=(Get-Date).AddMinutes(3); while((Get-Date) -lt $deadline){try{$r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2;if($r.status -eq 'online'){exit 0}}catch{};Start-Sleep -Seconds 2};exit 1"

if errorlevel 1 (
    echo.
    echo ERROR: JARVIS Voice Server failed to start.
    echo Check the Voice Server window for errors.
    pause
    exit /b 1
)

echo Voice Server Online.
echo Starting Main Assistant...

start "JARVIS Assistant" cmd /k ^
"C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe C:\Users\admin\jarvis-ai\assistant\main.py"

exit