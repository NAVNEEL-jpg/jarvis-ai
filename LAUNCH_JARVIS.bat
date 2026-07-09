@echo off
title J.A.R.V.I.S Launcher
color 0b

cd /d "C:\Users\admin\jarvis-ai"

echo ============================================================
echo                     J.A.R.V.I.S  SYSTEMS
echo ============================================================
echo  Initializing voice server, web dashboard, and desktop GUI...
echo ============================================================
echo.

:: 1. Start JARVIS Voice Server
echo [1/4] Starting Voice Server...
start "JARVIS Voice Server" /min cmd /c ^
  "C:\Users\admin\jarvis-ai\external\JarvisLuxTTS\.venv-tts\Scripts\python.exe -m uvicorn tts_server:app --app-dir C:\Users\admin\jarvis-ai\external\JarvisLuxTTS --host 127.0.0.1 --port 8765"

:: Wait for voice server health endpoint
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(45); while((Get-Date) -lt $deadline){try{$r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2;if($r.status -eq 'online'){exit 0}}catch{};Start-Sleep -Seconds 1};exit 1"

if errorlevel 1 (
    echo.
    echo [ERROR] JARVIS Voice Server failed to start.
    echo Please make sure Ollama is running and check settings.
    pause
    exit /b 1
)
echo [OK] Voice Server Online.
echo.

:: 2. Start Web UI Server (binds to 0.0.0.0 for Wifi/mobile access)
echo [2/4] Starting Web Dashboard Server...
start "JARVIS Web UI" /min cmd /c ^
  "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\ui_server.py"

:: Give Web UI 1.5 seconds to bind
timeout /t 2 >nul

:: 3. Open Web Dashboard in default browser
echo [3/4] Opening Web Dashboard...
start http://localhost:3000

:: 4. Start PyQt5 Desktop GUI (Arc Reactor HUD)
echo [4/4] Launching Arc Reactor GUI...
start "JARVIS GUI" /min cmd /c ^
  "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\jarvis_desktop.py"

echo [OK] Arc Reactor GUI launched.
echo.
echo ============================================================
echo                     ALL SYSTEMS ONLINE
echo ============================================================
echo.

:: Get and print local network IP address
for /f "tokens=4" %%a in ('route print ^| findstr "\<0.0.0.0\>"') do (
    set LOCAL_IP=%%a
)

if "%LOCAL_IP%"=="" (
    :: Fallback IP detection
    for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "ipv4"') do (
        set LOCAL_IP=%%i
        goto :print_ip
    )
)

:print_ip
:: Remove leading space
set LOCAL_IP=%LOCAL_IP: =%

echo  - Local dashboard url : http://localhost:3000
echo  - Mobile Wifi url     : http://%LOCAL_IP%:3000
echo.
echo  To connect from phones/tablets/other laptops:
echo  1. Connect them to the same Wifi network.
echo  2. Open the Mobile Wifi url above in your browser.
echo.
echo ============================================================
echo  Minimize this window to keep the server running.
echo ============================================================
echo.
pause
