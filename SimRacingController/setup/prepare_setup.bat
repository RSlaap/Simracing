@echo off
echo ================================================
echo    Prepare Portable Environment
echo ================================================
echo.
echo This script prepares everything on YOUR PC (with internet)
echo so it can be copied to the offline SimRacing PC.
echo.

set "SSD_ROOT=%~dp0"
set "SSD_ROOT=%SSD_ROOT:~0,-1%"

echo [1/4] Verifying embedded Python...
if not exist "%SSD_ROOT%\python\python.exe" (
    echo ERROR: Embedded Python not found at %SSD_ROOT%\python\
    pause
    exit /b 1
)
echo OK
echo.

echo [2/4] Verifying requirements.txt...
if not exist "%SSD_ROOT%\requirements.txt" (
    echo ERROR: requirements.txt not found
    pause
    exit /b 1
)
echo OK
echo.

echo [3/4] Creating portable virtual environment...
if exist "%SSD_ROOT%\venv" (
    echo Removing old venv...
    rmdir /s /q "%SSD_ROOT%\venv"
)

echo.
echo Creating venv with your system Python...
echo (This will be portable to other systems)
echo.

python -m venv "%SSD_ROOT%\venv"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create venv
    echo Make sure Python is installed on your system
    pause
    exit /b 1
)
echo OK
echo.

echo [4/4] Installing all packages...
echo This may take several minutes...
echo.

"%SSD_ROOT%\venv\Scripts\pip.exe" install -r "%SSD_ROOT%\requirements.txt"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install packages
    pause
    exit /b 1
)
echo OK
echo.

echo ================================================
echo    Preparation Complete!
echo ================================================
echo.
echo Your SSD now contains:
echo - Embedded Python: %SSD_ROOT%\python\
echo - Virtual environment with all packages: %SSD_ROOT%\venv\
echo - Your project: %SSD_ROOT%\
echo.
echo IMPORTANT: Test it first on this PC by running:
echo   scripts\start.bat
echo.
echo If it works, copy the ENTIRE SSD contents to the SimRacing PC.
echo On the SimRacing PC, just run scripts\start.bat - NO setup needed!
echo.
echo The venv will work on any Windows PC with the same architecture.
echo.
pause