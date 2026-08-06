@echo off
echo ============================================
echo   Zamak_Valsadae - Installer (portable)
echo ============================================
echo.
echo This downloads a self-contained Python/Node.js/ffmpeg runtime into
echo this folder (no system-wide installs, no admin rights needed) and
echo then installs the app's dependencies.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
    echo.
    echo Install failed. See the error above and run install.bat again.
    pause
    exit /b 1
)

pause
