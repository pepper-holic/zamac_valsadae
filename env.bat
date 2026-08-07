@echo off
REM Prepends this project's portable runtime (runtime/python, runtime/node,
REM runtime/ffmpeg) to PATH for the current session only - nothing is
REM installed system-wide. Run install.bat first to populate runtime/.
set "ZV_ROOT=%~dp0"
set "PATH=%ZV_ROOT%runtime\python;%ZV_ROOT%runtime\python\Scripts;%ZV_ROOT%runtime\node;%ZV_ROOT%runtime\ffmpeg\bin;%PATH%"

REM huggingface_hub's newer "Xet" transfer backend (via the hf-xet package)
REM silently stalls on model.bin-sized downloads in some network environments
REM (corporate proxy/firewall blocking the Xet CAS endpoints) instead of
REM erroring or timing out. Disabling it falls back to plain HTTPS downloads.
set "HF_HUB_DISABLE_XET=1"
