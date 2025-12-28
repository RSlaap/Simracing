@echo off
set "SSD_ROOT=%~dp0.."

echo ================================================
echo Starting SimRacing Project...
echo ================================================
echo.
echo Debug Info:
echo - Script location: %~dp0
echo - SSD Root: %SSD_ROOT%
echo - Python path: %SSD_ROOT%\venv\Scripts\python.exe
echo - Script path: %SSD_ROOT%\orchestrator.py
echo.

if not exist "%SSD_ROOT%\venv\Scripts\python.exe" (
    echo ERROR: Python executable not found at:
    echo %SSD_ROOT%\venv\Scripts\python.exe
    echo.
    echo Please verify:
    echo 1. The venv folder exists at %SSD_ROOT%\venv
    echo 2. You ran prepare_portable.bat to create the venv
    echo.
    pause
    exit /b 1
)

if not exist "%SSD_ROOT%\orchestrator.py" (
    echo ERROR: Main script not found at:
    echo %SSD_ROOT%\orchestrator.py
    echo.
    echo Please verify your project structure.
    echo.
    pause
    exit /b 1
)

echo All paths verified. Starting project...
echo.

"%SSD_ROOT%\venv\Scripts\python.exe" "%SSD_ROOT%\orchestrator.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Project exited with error code %ERRORLEVEL%
    echo Press any key to close...
    pause >nul
)