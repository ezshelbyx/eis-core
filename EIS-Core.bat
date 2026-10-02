@echo off
rem ------------------------------------------------------------
rem  E.I.S. Core launcher (double-click or run from the project
rem  folder). Requires Python 3.10+ on PATH.
rem ------------------------------------------------------------
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found in PATH.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

python __main__.py %*
if errorlevel 1 pause
endlocal
