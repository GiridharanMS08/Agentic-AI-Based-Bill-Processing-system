@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==================================================
echo   Agentic AI Bill Processor - Browser Launcher
echo   MySQL + RapidOCR + Gemini
echo ==================================================

echo.
where python >nul 2>&1
if errorlevel 1 (
  echo Python 3.11+ was not found on PATH.
  goto :fail
)

if not exist venv\Scripts\python.exe (
  echo [1/5] Creating virtual environment...
  python -m venv venv || goto :fail
) else (
  echo [1/5] Virtual environment already exists.
)

set "PY=%CD%\venv\Scripts\python.exe"

echo [2/5] Installing dependencies...
"%PY%" -m pip install --upgrade pip || goto :fail
"%PY%" -m pip install -r requirements.txt || goto :fail

if not exist config\db_config.env (
  copy /Y config\db_config.example.env config\db_config.env >nul
  echo.
  echo Created config\db_config.env.
  echo Edit your MySQL credentials and Gemini API key, then run run.bat again.
  pause
  exit /b 0
)

if not exist input_bills mkdir input_bills
if not exist output mkdir output

echo [3/5] Checking MySQL and creating schema...
"%PY%" setup_db.py || goto :fail

echo [4/5] Starting browser application...
echo.
echo Browser URL: http://127.0.0.1:8000
"%PY%" web_app.py || goto :fail

:fail
echo.
echo Application stopped or startup failed.
pause
exit /b 1
