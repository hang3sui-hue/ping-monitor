@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 ping_gui.py
) else (
    python ping_gui.py
)
if errorlevel 1 pause
