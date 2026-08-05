@echo off
setlocal enabledelayedexpansion
echo ============================================
echo   Zamak_Valsadae - Installer
echo ============================================
echo.

REM --- Python check ---
where python >nul 2>nul
if errorlevel 1 (
    echo [1/5] Python not found. Trying to install via winget...
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo.
        echo Automatic install failed. Please install Python 3.11+ from https://python.org
        echo then close this window and run install.bat again.
        pause
        exit /b 1
    )
    echo Python installed. Please close this window and run install.bat again.
    pause
    exit /b 0
) else (
    echo [1/5] Python OK.
)

REM --- Node.js check ---
where npm >nul 2>nul
if errorlevel 1 (
    echo [2/5] Node.js not found. Trying to install via winget...
    winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo.
        echo Automatic install failed. Please install Node.js LTS from https://nodejs.org
        echo then close this window and run install.bat again.
        pause
        exit /b 1
    )
    echo Node.js installed. Please close this window and run install.bat again.
    pause
    exit /b 0
) else (
    echo [2/5] Node.js OK.
)

REM --- ffmpeg check ---
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [3/5] ffmpeg not found. Trying to install via winget...
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    echo ffmpeg was installed but only applies to NEW terminal windows.
    echo Please close this window and run install.bat again to confirm PATH is updated.
    pause
) else (
    echo [3/5] ffmpeg OK.
)

REM --- Backend deps (heavy: torch, whisper, ctranslate2 - several GB, can take a while) ---
echo [4/5] Installing backend Python packages (several GB, first run can take a while)...
cd backend
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Backend package install failed. Check the error message above.
    pause
    exit /b 1
)
cd ..

REM --- Frontend build ---
echo [5/5] Building the frontend...
cd frontend
call npm install
if errorlevel 1 (
    echo npm install failed. Check the error message above.
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo Frontend build failed. Check the error message above.
    pause
    exit /b 1
)
cd ..

echo.
echo ============================================
echo   Install complete! Run run.bat to start.
echo ============================================
pause
