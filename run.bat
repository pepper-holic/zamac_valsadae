@echo off
echo Starting Zamak_Valsadae server...
set "ROOT_DIR=%~dp0"

if not exist "%ROOT_DIR%runtime\python\python.exe" (
    echo First launch detected - installing the portable runtime and dependencies.
    echo This downloads Python/Node.js/ffmpeg and installs packages ^(a few GB, one-time^).
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%install.ps1"
    if errorlevel 1 (
        echo.
        echo Install failed. See the error above, then run install.bat to retry.
        pause
        exit /b 1
    )
)

(
    echo @echo off
    echo call "%ROOT_DIR%env.bat"
    echo cd /d "%ROOT_DIR%backend"
    echo python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) > "%ROOT_DIR%runtime\_run_server.bat"

start "Zamak_Valsadae Server" cmd /k "%ROOT_DIR%runtime\_run_server.bat"

echo Waiting for the server to start...
timeout /t 4 /nobreak >nul
start "" http://localhost:8000

echo.
echo The server is running in a separate window. Close that window to stop it.
pause
