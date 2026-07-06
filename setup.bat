@echo off
chcp 65001 >nul
title Critical Thinking AI Assessment - Setup

echo ============================================
echo   Critical Thinking AI Assessment - Setup
echo ============================================
echo.

:: ============================================
:: Step 1: Check Python
:: ============================================
echo [1/4] Checking Python...

set "PY=""
python --version >nul 2>&1
if not errorlevel 1 (set "PY=python" & goto :py_found)
py --version >nul 2>&1
if not errorlevel 1 (set "PY=py" & goto :py_found)

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (set "PY=%%~P" & goto :py_found)
)

echo.
echo   [X] Python NOT found!
echo.
echo   Please install Python 3.10 or higher:
echo   https://www.python.org/downloads/
echo.
echo   IMPORTANT: You MUST check "Add Python to PATH"!
echo   Then run this script again.
echo.
pause
exit /b 1

:py_found
%PY% --version >nul 2>&1
for /f "tokens=*" %%i in ('%PY% --version 2^>^&1') do set PYVER=%%i
echo   [OK] %PYVER%
echo.

:: ============================================
:: Step 2: Check pip
:: ============================================
echo [2/4] Checking pip...
%PY% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo   [X] pip not found, trying to install...
    %PY% -m ensurepip --upgrade >nul 2>&1
    if errorlevel 1 (
        echo   [X] Failed to install pip
        echo   Please install pip manually
        pause
        exit /b 1
    )
)
echo   [OK] pip is ready
echo.

:: ============================================
:: Step 3: Install dependencies
:: ============================================
echo [3/4] Checking dependencies...

%PY% -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo   streamlit not found, installing...
    %PY% -m pip install streamlit -q
    if errorlevel 1 (
        echo   [X] Failed to install streamlit
        echo   Please check your network connection
        pause
        exit /b 1
    )
    echo   [OK] streamlit installed
) else (
    echo   [OK] streamlit already installed
)
echo.

:: ============================================
:: Step 4: Verify project files & create dirs
:: ============================================
echo [4/4] Checking project files...

if not exist "%~dp0cases" mkdir "%~dp0cases"
if not exist "%~dp0rubrics" mkdir "%~dp0rubrics"
if not exist "%~dp0data" mkdir "%~dp0data"

set "OK=0"
if exist "%~dp0app.py" (echo   [OK] app.py & set /a OK+=1) else (echo   [X] app.py MISSING)
if exist "%~dp0cases\*.json" (echo   [OK] cases/ & set /a OK+=1) else (echo   [X] cases/ MISSING)
if exist "%~dp0rubrics\rubric.json" (echo   [OK] rubrics/ & set /a OK+=1) else (echo   [X] rubrics/ MISSING)

if %OK% LSS 3 (
    echo.
    echo   [X] Some project files are missing!
    echo   Please re-download the project.
    pause
    exit /b 1
)
echo.

:: ============================================
:: Setup Complete
:: ============================================
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   All requirements are satisfied.
echo.
echo   Press any key to start the application...
echo.
pause >nul

:: Start the app
start "" http://localhost:8501
%PY% -m streamlit run "%~dp0app.py"
