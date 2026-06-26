@echo off
chcp 65001 >nul 2>&1
setlocal
title Build DanbooruDownload EXE

set "APP_NAME=DanbooruDownload"
set "VENV_PY=.venv\Scripts\python.exe"
set "DIST_DIR=dist\%APP_NAME%"
set "EXE_PATH=%DIST_DIR%\%APP_NAME%.exe"

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

if exist "%VENV_PY%" (
    "%VENV_PY%" --version >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Existing virtual environment is invalid. Recreating...
        rmdir /s /q ".venv"
    )
)

if not exist "%VENV_PY%" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Installing runtime dependencies...
"%VENV_PY%" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Failed to install runtime dependencies.
    pause
    exit /b 1
)

echo [INFO] Installing build dependencies...
"%VENV_PY%" -m pip install -r requirements-build.txt -q
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo [INFO] Running tests...
"%VENV_PY%" -m unittest discover -s tests
if errorlevel 1 (
    echo [ERROR] Tests failed. Packaging stopped.
    pause
    exit /b 1
)

echo [INFO] Checking Python syntax...
"%VENV_PY%" -m compileall danbooru_download config.py danbooru_client.py downloader.py formatter.py gui.py main.py
if errorlevel 1 (
    echo [ERROR] Compile check failed. Packaging stopped.
    pause
    exit /b 1
)

echo [INFO] Cleaning previous build output...
if exist "build" rmdir /s /q "build"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

echo [INFO] Building %APP_NAME%.exe...
"%VENV_PY%" -m PyInstaller DanbooruDownload.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

if not exist "%EXE_PATH%" (
    echo [ERROR] Expected EXE was not created: %EXE_PATH%
    pause
    exit /b 1
)

echo [INFO] Creating user download folder...
if not exist "%DIST_DIR%\Download" mkdir "%DIST_DIR%\Download"

echo [OK] Build complete: %CD%\%EXE_PATH%
echo [OK] Runtime files: %CD%\%DIST_DIR%\win-x64
echo [OK] User folder: Download
if /I "%~1"=="--run" (
    echo [INFO] Starting packaged app...
    start "" "%EXE_PATH%"
)

endlocal
