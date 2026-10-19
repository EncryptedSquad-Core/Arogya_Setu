@echo off
title Arogya Setu Full-Stack Auto-Localhost (Backend :8000 + Frontend :5173)
cd /d "%~dp0"

echo ============================================================
echo   Starting Arogya Setu Full-Stack Application...
echo   - Initializing SQLite Database (backend/arogya_setu.db)
echo   - Starting Backend REST API on http://127.0.0.1:8000
echo   - Starting Frontend UI on http://127.0.0.1:5173
echo ============================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    pause
    exit /b 1
)

python "%~dp0auto_localhost.py"
pause