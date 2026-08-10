@echo off
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

rem The bundled portable Python ships a python312._pth file, which puts the
rem interpreter in "isolated path" mode - it ignores PYTHONPATH and does NOT
rem add the current directory to sys.path (even for `python -m`), unlike a
rem normal Python install. Without this .pth file in site-packages, `app.*`
rem imports (and `python -m app.desktop` itself) fail with
rem "ModuleNotFoundError: No module named 'app'". Regenerated every run so it
rem stays correct even if this folder is moved.
echo %ROOT_DIR%backend> "%ROOT_DIR%runtime\python\Lib\site-packages\zamac_valsadae.pth"

(
    echo @echo off
    echo call "%ROOT_DIR%env.bat"
    echo cd /d "%ROOT_DIR%backend"
    echo start "" /B pythonw -m app.desktop
) > "%ROOT_DIR%runtime\_run_app.bat"

call "%ROOT_DIR%runtime\_run_app.bat"
