@echo off
set "SSD_ROOT=%~dp0.."

echo ================================================
echo Starting Template Capture Tool...
echo ================================================
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
    echo Please run prepare_setup.bat to set up the environment
    echo.
    pause
    exit /b 1
)

echo - Using embedded Python: %PYTHON_EXE%

echo - Python path: %PYTHON_EXE%
echo - Script path: %SSD_ROOT%\src\templating\template_capture.py
echo.

if not exist "%SSD_ROOT%\src\templating\template_capture.py" (
    echo ERROR: Template capture script not found at:
    echo %SSD_ROOT%\src\templating\template_capture.py
    echo.
    echo Please verify your project structure.
    echo.
    pause
    exit /b 1
)

echo All paths verified. Starting template capture...
echo.
echo Instructions:
echo - Press 'S' to start capturing a template
echo - Click top-left corner, then bottom-right corner
echo - Press 'Q' to quit when done
echo.

REM Change to src directory so Python can find local modules
cd /d "%SSD_ROOT%\src"
"%PYTHON_EXE%" templating\template_capture.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Template capture exited with error code %ERRORLEVEL%
    echo Press any key to close...
    pause
)
