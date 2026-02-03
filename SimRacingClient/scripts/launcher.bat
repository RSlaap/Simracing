@echo off
:: BatchGotAdmin - Request admin privileges
:: This script will request UAC elevation and then run the main launcher

:: Check for admin privileges
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

:: If error flag is set, we don't have admin
if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

:: ========================================
:: Main launcher code starts here
:: ========================================

set "SSD_ROOT=%~dp0.."

echo ================================================
echo Starting SimRacing Project
echo ================================================
echo.
echo Running with elevated privileges for CAMMUS control.
echo.
echo Debug Info:
echo - Script location: %~dp0
echo - SSD Root: %SSD_ROOT%
echo.

REM Use embedded Python directly
set "PYTHON_EXE=%SSD_ROOT%\python\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERROR: Embedded Python not found!
    echo.
    echo Expected location: %PYTHON_EXE%
    echo.
    echo Please run scripts\installation\prepare_setup.bat to set up the environment
    echo.
    pause
    exit /b 1
)

echo - Using embedded Python: %PYTHON_EXE%

echo - Python path: %PYTHON_EXE%
echo - Script path: %SSD_ROOT%\src\simracing_client.py
echo.

if not exist "%SSD_ROOT%\src\simracing_client.py" (
    echo ERROR: Main script not found at:
    echo %SSD_ROOT%\src\simracing_client.py
    echo.
    echo Please verify your project structure.
    echo.
    pause
    exit /b 1
)

echo All paths verified. Starting project...
echo.

REM Set PYTHONPATH to src directory so Python can find local modules
set "PYTHONPATH=%SSD_ROOT%\src"

REM Change to src directory and run
cd /d "%SSD_ROOT%\src"
"%PYTHON_EXE%" simracing_client.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Project exited with error code %ERRORLEVEL%
    echo Press any key to close...
    pause
)
