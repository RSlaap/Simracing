@echo off
echo ================================================
echo Starting Template Capture (Using System Python)
echo ================================================
echo.

set "SSD_ROOT=%~dp0.."

REM Find system Python
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    set "PYTHON_EXE=%%i"
    goto :found
)

echo ERROR: System Python not found
pause
exit /b 1

:found
echo Using system Python: %PYTHON_EXE%
echo.

REM Test if system Python has required packages
echo Checking for required packages...
"%PYTHON_EXE%" -c "import tkinter, PIL, pynput" 2>nul

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Missing packages. Installing...
    "%PYTHON_EXE%" -m pip install Pillow pynput
)

echo.
echo Starting template capture tool...
echo.
echo Instructions:
echo - Press 'S' to start capturing a template
echo - Click top-left corner, then bottom-right corner
echo - Press 'Q' to quit when done
echo.

cd /d "%SSD_ROOT%\src"
"%PYTHON_EXE%" templating\template_capture.py

pause
