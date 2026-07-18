@echo off
chcp 65001 >nul 2>&1
title BooruDownload

set "VENV_PY=.venv\Scripts\python.exe"
set "VENV_PYW=.venv\Scripts\pythonw.exe"

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
    rem %ERRORLEVEL% expands before the block runs; "if errorlevel" reads live
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Checking dependencies...
"%VENV_PY%" -c "import httpx, tqdm, yaml, customtkinter, anyio, typing_extensions" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    "%VENV_PY%" -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed successfully.
)

echo [INFO] Starting BooruDownload...
start "" "%VENV_PYW%" gui.py
