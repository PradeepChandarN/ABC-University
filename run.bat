@echo off
setlocal enabledelayedexpansion

title ABC University Academic Management System
echo ======================================================================
echo          ABC UNIVERSITY ACADEMIC MANAGEMENT SYSTEM
echo             Powered by Python, FastAPI and DuckDB
echo ======================================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not found in system PATH.
    echo Please install Python 3.10+ from https://www.python.org/ and check
    echo "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Install dependencies if not already installed
echo [1/4] Checking and installing dependencies...
python -m pip install -r "%~dp0backend\requirements.txt" --quiet
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Pip install had issues. Attempting to proceed...
)

:: 3. Initialize DuckDB Database
echo [2/4] Verifying / Initializing DuckDB Database...
python "%~dp0backend\init_db.py"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to initialize database.
    pause
    exit /b 1
)
echo.

:: 4. Detect Local IP Address for other laptops
set "LOCAL_IP=localhost"
for /f "tokens=4" %%a in ('route print 0.0.0.0 ^| findstr 0.0.0.0 ^| findstr /v "0.0.0.0.*0.0.0.0"') do (
    set "LOCAL_IP=%%a"
)

echo [3/4] Access Information:
echo   - On this laptop:     http://localhost:8000
echo   - For other laptops:  http://!LOCAL_IP!:8000  (on the same Wi-Fi)
echo.

:: 5. Open local browser
echo [4/4] Opening browser...
start "" "http://localhost:8000"

echo.
echo ======================================================================
echo Server is running on all interfaces (0.0.0.0:8000).
echo Keep this window open. Press CTRL+C to stop the application.
echo ======================================================================
echo.

cd /d "%~dp0backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause

