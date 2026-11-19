@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python -B serve.py --open
) else (
    py -3 -B serve.py --open
)
if errorlevel 1 pause
