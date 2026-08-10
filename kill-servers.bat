@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo ============================================
echo   Zamak_Valsadae - 강제 서버 종료
echo ============================================
echo.
echo 이 스크립트는 로컬에서 자주 사용하는 서버 포트에 바인딩된 프로세스를 찾아 강제 종료합니다.
echo 필요하면 관리자 권한으로 실행하세요.
echo.

set PORTS=8000 5173 3000 3001

echo Target ports: %PORTS%
for %%P in (%PORTS%) do (
    echo.
    echo Checking port %%P ...
    for /f "tokens=5" %%Q in ('netstat -ano ^| findstr /R /C:":%%P " ^| findstr /I TCP') do (
        echo Found process listening on port %%P: PID=%%Q
        taskkill /PID %%Q /F >nul 2>&1
        if errorlevel 1 (
            echo   실패: PID %%Q를 종료하지 못했습니다.
        ) else (
            echo   성공: PID %%Q를 종료했습니다.
        )
    )
)

echo.
echo.
echo 추가로 uvicorn 또는 Vite/Node 서버 프로세스가 남아있을 수 있습니다.
echo 아래 프로세스 이름도 확인해서 필요시 종료합니다.
echo.
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE | findstr /I uvicorn >nul
if not errorlevel 1 (
  echo Found python.exe process with uvicorn in command line. Attempting to terminate all matching python.exe processes...
  taskkill /IM python.exe /F >nul 2>&1
)
tasklist /FI "IMAGENAME eq pythonw.exe" >nul 2>&1
if not errorlevel 1 (
  echo Found pythonw.exe process ^(desktop app window^). Terminating pythonw.exe...
  taskkill /IM pythonw.exe /F >nul 2>&1
)
tasklist /FI "IMAGENAME eq node.exe" /FO TABLE | findstr /I vite >nul
if not errorlevel 1 (
  echo Found node.exe process with Vite in command line. Terminating node.exe...
  taskkill /IM node.exe /F >nul 2>&1
)
echo.
echo 강제 종료 작업을 완료했습니다.
echo 만약 포트가 여전히 점유되어 있다면, 포트 번호를 확인한 뒤 이 스크립트에 추가해주세요.
echo.
echo Done.
pause
