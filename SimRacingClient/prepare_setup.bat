@echo off
echo ================================================
echo    Download Packages for Offline Installation
echo ================================================
echo.

set "SSD_ROOT=%~dp0"
set "SSD_ROOT=%SSD_ROOT:~0,-1%"

echo [1/2] Verifying requirements.txt...
if not exist "%SSD_ROOT%\requirements.txt" (
    echo ERROR: requirements.txt not found at %SSD_ROOT%\project\requirements.txt
    pause
    exit /b 1
)
echo OK - requirements.txt found
echo.

echo [2/2] Downloading packages...
if not exist "%SSD_ROOT%\pip_cache" mkdir "%SSD_ROOT%\pip_cache"

echo This will download all Python packages for offline installation.
echo This may take several minutes depending on package size...
echo.

pip download -r "%SSD_ROOT%\requirements.txt" -d "%SSD_ROOT%\pip_cache"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to download packages
    echo.
    echo Make sure:
    echo - You have pip installed (try: python -m pip --version)
    echo - You have internet connection
    echo - requirements.txt has valid package names
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================
echo    Download Complete!
echo ================================================
echo.
echo Packages saved to: %SSD_ROOT%\pip_cache\
echo.
echo Your SSD is now ready for offline installation.
echo Copy everything to the target system and run setup.bat
echo.
pause