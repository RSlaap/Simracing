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
echo  2. Navigate to the first screen with buttons you want to capture
echo  3. Make sure CAMMUS window is visible and not minimized
echo.
echo WORKFLOW:
echo  1. Position your mouse over a button in CAMMUS
echo  2. Press 'C' to capture (single-click) or 'V' (double-click)
echo  3. Click the button in CAMMUS to navigate to the next screen
echo  4. Repeat steps 1-3 for each button
echo  5. Press 'Q' when done
echo.
echo NOTE: Your mouse clicks are NOT blocked - you can click
echo normally in CAMMUS while using this tool.
echo.
echo Templates will be saved to:
echo  src\templating\unclassified_templates\
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
    echo Please run scripts\installation\prepare_setup.bat to set up the environment
    echo.
    pause
    exit /b 1
)

echo Starting template capture tool...
echo.

REM Change to templating directory
cd /d "%SSD_ROOT%\src\templating"

if not exist "click_template_capture.py" (
    echo ERROR: Template capture script not found at:
    echo %SSD_ROOT%\src\templating\click_template_capture.py
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" click_template_capture.py

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
echo  2. Move template PNG images to templates\CAMMUS\
echo  3. Move click_steps.json to templates\CAMMUS\
echo  4. Update cammus_config.json with correct settings
echo.
echo See documentation\CAMMUS_SETUP.md for detailed instructions.
echo.
pause
