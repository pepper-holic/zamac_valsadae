@echo off
rem Builds installer\launcher_dist\ZamakValsadae.exe from launcher.py via PyInstaller.
rem Run this before compiling installer.iss (installer.iss picks up the exe
rem from launcher_dist\). Requires: pip install pyinstaller
cd /d "%~dp0"

python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --icon "%~dp0icon.ico" ^
    --name ZamakValsadae ^
    --distpath launcher_dist ^
    --workpath launcher_build ^
    --specpath launcher_build ^
    launcher.py

if errorlevel 1 (
    echo.
    echo Build failed. See the error above.
    exit /b 1
)

echo.
echo Built launcher_dist\ZamakValsadae.exe
