@echo off
setlocal enabledelayedexpansion

echo ================================================
echo   Building Monitor Deployer EXE
echo ================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is available
echo [1/5] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
python --version

REM Install PyInstaller if needed
echo.
echo [2/5] Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

REM Clean previous builds
echo.
echo [3/5] Cleaning previous builds...
if exist dist rmdir /s /q dist 2>nul
if exist build rmdir /s /q build 2>nul
if exist ..\MonitorSetup.exe del /q ..\MonitorSetup.exe 2>nul

REM Build using PyInstaller
echo.
echo [4/5] Building EXE (this may take a few minutes)...
python -m PyInstaller ^
    --onefile ^
    --console ^
    --name MonitorSetup ^
    --uac-admin ^
    --add-data "..\agent;agent" ^
    --add-data "..\extensions\chromium;extensions/chromium" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.simpledialog ^
    --hidden-import winreg ^
    --clean ^
    deploy.py

if errorlevel 1 (
    echo.
    echo ================================================
    echo   BUILD FAILED!
    echo ================================================
    echo.
    echo Check the output above for errors.
    pause
    exit /b 1
)

REM Verify and copy to project root
echo.
echo [5/5] Finalizing...
if not exist dist\MonitorSetup.exe (
    echo ERROR: EXE not found after build!
    pause
    exit /b 1
)

copy dist\MonitorSetup.exe ..\MonitorSetup.exe
if errorlevel 1 (
    echo Warning: Could not copy to project root
)

echo.
echo ================================================
echo   Build Complete!
echo ================================================
echo.
echo   Output files:
echo     - deployer\dist\MonitorSetup.exe
echo     - MonitorSetup.exe (project root)
echo.
echo   Size: 
for %%A in (dist\MonitorSetup.exe) do echo     %%~zA bytes
echo.
echo   To deploy:
echo     1. Copy MonitorSetup.exe to target device
echo     2. Run as Administrator
echo     3. Enter the Dashboard IP when prompted
echo.
pause
