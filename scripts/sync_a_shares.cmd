@echo off
rem Run from this repository, regardless of Task Scheduler's working directory.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m src.market_data sync
) else (
    python -m src.market_data sync
)
exit /b %errorlevel%
