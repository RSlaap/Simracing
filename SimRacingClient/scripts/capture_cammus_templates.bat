@echo off
set "SSD_ROOT=%~dp0.."

echo ================================================
echo CAMMUS Template Capture Tool
echo ================================================
echo.
echo This tool will help you capture button templates
echo from the CAMMUS software for automatic configuration.
echo.
echo BEFORE YOU START:
echo  1. Open CAMMUS software
echo  2. Navigate to the screen with buttons you want to capture
echo  3. Make sure CAMMUS window is visible and not minimized
echo.
echo INSTRUCTIONS:
echo  - Press 'S' to start capturing a template
echo  - Click top-left corner of button
echo  - Click bottom-right corner of button
echo  - Repeat for each button you need
echo  - Press 'Q' to quit when done
echo.
echo Templates will be saved to:
echo  src\templating\unclassified_templates\
echo.
echo After capturing, move templates to:
echo  templates\CAMMUS\
echo.
pause
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

echo Starting template capture tool...
echo.

REM Change to templating directory
cd /d "%SSD_ROOT%\src\templating"

if not exist "template_capture.py" (
    echo ERROR: Template capture script not found at:
    echo %SSD_ROOT%\src\templating\template_capture.py
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" template_capture.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Template capture tool exited with error code %ERRORLEVEL%
    echo.
)

echo.
echo ================================================
echo Template capture completed!
echo ================================================
echo.
echo Next steps:
echo  1. Check src\templating\unclassified_templates\ for captured templates
echo  2. Move template images to templates\CAMMUS\
echo  3. Update config.json with template filenames
echo  4. Set "enabled": true in pre_launch_config
echo.
echo See CAMMUS_SETUP.md for detailed instructions.
echo.
pause
