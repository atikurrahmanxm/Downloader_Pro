@echo off
title Push Downloader_Pro to GitHub
cd /d "%~dp0"

echo =======================================================
echo    Pushing Downloader_Pro to GitHub...
echo    Target: https://github.com/atikurrahmanxm/Downloader_Pro
echo =======================================================
echo.

git add .
git commit -m "Update Downloader Pro" >nul 2>nul

echo [INFO] Pushing commits to GitHub...
echo [NOTE] If a browser login prompt appears, please click 'Sign in' / 'Authorize'.
echo.

git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo =======================================================
    echo   [SUCCESS] Code successfully uploaded to GitHub!
    echo   URL: https://github.com/atikurrahmanxm/Downloader_Pro
    echo =======================================================
) else (
    echo.
    echo [ERROR] Push failed. If this is a new repository with existing files,
    echo run: git pull --rebase origin main, then push again.
)

echo.
pause
