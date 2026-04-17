@echo off
title Voxel Setup
echo.
echo  ========================================
echo    Voxel - Voice Dictation Tool
echo  ========================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Python not found! Installing Python...
    echo  Downloading Python installer...
    curl -L -o "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.13.12/python-3.13.12-amd64.exe"
    echo  Running Python installer (please check "Add to PATH")...
    "%TEMP%\python_installer.exe" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
    del "%TEMP%\python_installer.exe"
    echo  Python installed! Please close and reopen this window, then run again.
    pause
    exit /b
)

echo  [1/2] Installing dependencies...
pip install groq pyaudio pynput pyautogui pyperclip pystray Pillow customtkinter >nul 2>&1
echo  Done!
echo.
echo  [2/2] Launching Voxel...
echo.
echo  Hold Ctrl+Shift+Space to dictate!
echo  ========================================
echo.
python -m src.main
