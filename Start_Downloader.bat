@echo off
title MediaGrabber Pro - Universal Video Downloader
cd /d "%~dp0"

echo =======================================================
echo    Starting MediaGrabber Pro Video Downloader...
echo =======================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

echo [INFO] Launching server...
echo [INFO] Dashboard will automatically open in your default browser.
echo.

python app.py

pause
