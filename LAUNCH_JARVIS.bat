@echo off
title J.A.R.V.I.S Launcher
color 0b

cd /d "C:\Users\admin\jarvis-ai"

echo ============================================================
echo                     J.A.R.V.I.S  SYSTEMS
echo ============================================================
echo  Initializing voice server, web dashboard, and controller...
echo ============================================================
echo.

:: 1. Start JARVIS Voice Server
echo [1/3] Starting Voice Server...
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
echo [2/3] Starting Web Dashboard Server...
start "JARVIS Web UI" /min cmd /c ^
  "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\ui_server.py"

:: 3. Start System Tray Controller & Desktop GUI
echo [3/3] Launching Controller & System Tray...
start "JARVIS Controller" /min cmd /c ^
  "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe assistant\jarvis_controller.py"

echo [OK] Controller & System Tray running.
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
