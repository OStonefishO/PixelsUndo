@echo off
setlocal
cd /d "%~dp0"
title PixelsUndo

set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"

if not exist "%PY%" goto setup

"%PY%" -c "import PIL, numpy, cv2, segno" >nul 2>nul
if errorlevel 1 goto deps
goto run

:setup
echo.
echo   First run: creating the Python environment...
echo.
where py >nul 2>nul
if errorlevel 1 (
    echo   Python was not found. Please install Python 3.8 - 3.11,
    echo   tick "Add Python to PATH", then double-click this file again.
    echo.
    pause
    exit /b 1
)
py -3 -m venv "%VENV%"
if errorlevel 1 (
    echo   Could not create the Python environment. Please check your Python install.
    pause
    exit /b 1
)

:deps
echo.
echo   Installing image components (first run: about 1-3 minutes)...
echo.
"%PY%" -m pip install --no-cache-dir --disable-pip-version-check --only-binary=:all: -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo   Installation failed. Check your network, or try the default index:
    echo   "%PY%" -m pip install --no-cache-dir -r requirements.txt
    echo.
    pause
    exit /b 1
)

:run
if exist "%PYW%" (
    start "" "%PYW%" launcher.py
) else (
    start "" "%PY%" launcher.py
)
exit /b 0
