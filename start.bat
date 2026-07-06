@echo off
cd /d "%~dp0"

echo ========================================
echo   Critical Thinking AI Assessment
echo ========================================
echo.

set "PY="
python --version >nul 2>&1
if not errorlevel 1 (set "PY=python" & goto :found)
py --version >nul 2>&1
if not errorlevel 1 (set "PY=py" & goto :found)

echo [ERROR] Python not found!
echo.
echo Please install Python 3.10+ from:
echo https://www.python.org/downloads/
echo.
echo IMPORTANT: Check "Add Python to PATH" during installation!
echo.
pause
exit /b 1

:found
echo [OK] Python: %PY%
echo.

echo Checking streamlit...
%PY% -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Installing streamlit, please wait...
    %PY% -m pip install streamlit -q
)
echo [OK] Ready
echo.
echo Starting... Browser will open automatically.
echo.

start "" http://localhost:8501
%PY% -m streamlit run "%~dp0app.py"
