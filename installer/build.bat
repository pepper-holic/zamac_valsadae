@echo off
rem Builds the full installer end-to-end:
rem   1. launcher.py -> launcher_dist\ZamakValsadae.exe (via PyInstaller)
rem   2. installer.iss -> dist\Zamak_Valsadae_Setup.exe (via Inno Setup ISCC)
rem
rem Requirements: pip install pyinstaller, and Inno Setup 6
rem (https://jrsoftware.org/isinfo.php) installed at its default path.
cd /d "%~dp0"

echo [1/2] Building launcher exe...
call "%~dp0build_launcher.bat"
if errorlevel 1 exit /b 1

echo.
echo [2/2] Compiling installer with Inno Setup...

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo.
    echo Inno Setup 6 not found at the default install path.
    echo Install it from https://jrsoftware.org/isinfo.php, or compile manually:
    echo   ISCC.exe installer.iss
    exit /b 1
)

"%ISCC%" installer.iss
if errorlevel 1 exit /b 1

echo.
echo Done. Output: dist\Zamak_Valsadae_Setup.exe
