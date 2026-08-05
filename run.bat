@echo off
echo Starting Zamak_Valsadae server...
cd backend
if not exist .venv (
    echo Not installed yet. Please run install.bat first.
    pause
    exit /b 1
)

start "Zamak_Valsadae Server" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Waiting for the server to start...
timeout /t 4 /nobreak >nul
start "" http://localhost:8000

echo.
echo The server is running in a separate window. Close that window to stop it.
pause
