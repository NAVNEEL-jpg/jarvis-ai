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

:: 0. Start Home Assistant VM (headless) if not already running
echo [0/4] Checking Home Assistant VM...
"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" list runningvms | findstr "Home Assistant" >nul
if errorlevel 1 (
    echo Starting Home Assistant VM in background...
    "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" startvm "Home Assistant" --type headless >nul 2>&1
) else (
    echo Home Assistant VM is already running.
)
echo [OK] Home Assistant active.
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

:: 2. Interface Mode Selector
echo ============================================================
echo   Select JARVIS Interface Mode:
echo ============================================================
echo   [1] Web Dashboard (Recommended)
echo       - Web HUD accessible from laptop, phone, and other devices
echo       - Built-in hands-free "Hey Jarvis" wake word
echo       - Full Control Panel, smart device list, and memory settings
echo.
echo   [2] PyQt5 Desktop App (Arc Reactor HUD)
echo       - Floating desktop widget on this laptop
echo       - Local microphone wake word listener
echo.
echo   [3] Start Both (Requires at least 16GB RAM)
echo ============================================================
set /p CHOICE="Enter choice (1, 2, or 3) [Default is 1]: "

if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="1" (
    echo.
    echo Starting Web Dashboard Server...
    start "JARVIS Web UI" /min cmd /c ^
      "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\ui_server.py"
    timeout /t 2 >nul
    echo Opening Web Dashboard...
    start http://localhost:3000
    goto :system_booted
)

if "%CHOICE%"=="2" (
    echo.
    echo Starting PyQt5 Desktop GUI (Arc Reactor HUD)...
    start "JARVIS GUI" /min cmd /c ^
      "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\jarvis_desktop.py"
    goto :system_booted
)

if "%CHOICE%"=="3" (
    echo.
    echo Starting Web Dashboard Server...
    start "JARVIS Web UI" /min cmd /c ^
      "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\ui_server.py"
    timeout /t 2 >nul
    echo Opening Web Dashboard...
    start http://localhost:3000
    
    echo Starting PyQt5 Desktop GUI (Arc Reactor HUD)...
    start "JARVIS GUI" /min cmd /c ^
      "C:\Users\admin\jarvis-ai\.venv\Scripts\python.exe ui\jarvis_desktop.py"
    goto :system_booted
)

:system_booted
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
