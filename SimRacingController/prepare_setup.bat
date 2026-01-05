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

echo [1/5] Verifying embedded Python...
if not exist "%SSD_ROOT%\python\python.exe" (
    echo ERROR: Embedded Python not found at %SSD_ROOT%\python\
    pause
    exit /b 1
)
echo OK
echo.

echo [2/5] Verifying requirements.txt...
if not exist "%SSD_ROOT%\requirements.txt" (
    echo ERROR: requirements.txt not found
    pause
    exit /b 1
)
echo OK
echo.

echo [3/5] Upgrading pip...
echo.

"%SSD_ROOT%\python\python.exe" -m pip install --upgrade pip

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to upgrade pip
    echo Make sure the embedded Python has pip available
    pause
    exit /b 1
)
echo OK
echo.

echo [4/5] Installing all packages directly into embedded Python...
echo This may take several minutes...
echo.

"%SSD_ROOT%\python\python.exe" -m pip install -r "%SSD_ROOT%\requirements.txt"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install packages
    pause
    exit /b 1
)
echo OK
echo.

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
echo Your project now contains:
echo - Embedded Python with all packages: %SSD_ROOT%\python\
echo - Your project: %SSD_ROOT%\
echo.
echo IMPORTANT: Test it first on this PC by running:
echo   scripts\launcher.bat
echo.
echo If it works, copy the ENTIRE project folder to the SimRacing PC.
echo On the SimRacing PC, just run scripts\launcher.bat - NO setup needed!
echo.
echo The embedded Python will work on any Windows PC with the same architecture.
echo.
pause