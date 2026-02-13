@echo off
chcp 65001 >nul 2>&1
title DanbooruDownload v1.0

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Checking dependencies...
.venv\Scripts\python.exe -c "import httpx, tqdm, yaml, customtkinter" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing dependencies...
    .venv\Scripts\pip.exe install -r requirements.txt -q
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed successfully.
)

echo [INFO] Starting DanbooruDownload...
start "" .venv\Scripts\pythonw.exe gui.py
