@echo off
REM Prepends this project's portable runtime (runtime/python, runtime/node,
REM runtime/ffmpeg) to PATH for the current session only - nothing is
REM installed system-wide. Run install.bat first to populate runtime/.
set "ZV_ROOT=%~dp0"
set "PATH=%ZV_ROOT%runtime\python;%ZV_ROOT%runtime\python\Scripts;%ZV_ROOT%runtime\node;%ZV_ROOT%runtime\ffmpeg\bin;%PATH%"
