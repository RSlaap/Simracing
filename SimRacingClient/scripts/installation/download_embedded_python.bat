@echo off
echo ================================================
echo    Download Embedded Python for Portability
echo ================================================
echo.
echo This script downloads Python 3.11.9 embedded distribution
echo and sets it up for portable deployment.
echo.

SET "SSD_ROOT=%~dp0..\..\\"
SET "PYTHON_VERSION=3.11.9"
SET "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"
SET "PYTHON_DIR=%SSD_ROOT%python"
SET "TEMP_ZIP=%TEMP%\python-embed.zip"

echo [1/5] Checking if embedded Python already exists...
if exist "%PYTHON_DIR%\python.exe" (
    echo WARNING: Embedded Python already exists at %PYTHON_DIR%
    echo.
    choice /C YN /M "Do you want to re-download and overwrite it"
    if errorlevel 2 goto :skip_download
    echo Removing old installation...
    rmdir /s /q "%PYTHON_DIR%"
)
echo.

echo [2/5] Downloading Python %PYTHON_VERSION% embedded distribution...
echo URL: %PYTHON_URL%
echo Target: %TEMP_ZIP%
echo.

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%TEMP_ZIP%'}"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to download Python
    pause
    exit /b 1
)
echo OK
echo.

echo [3/5] Extracting Python to %PYTHON_DIR%...
powershell -Command "& {Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force}"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to extract Python
    pause
    exit /b 1
)
echo OK
echo.

echo [4/5] Configuring embedded Python for pip and venv...
echo.

REM Uncomment site-packages in python311._pth to enable pip
powershell -Command "& {$file = '%PYTHON_DIR%\python311._pth'; if (Test-Path $file) { (Get-Content $file) -replace '#import site', 'import site' | Set-Content $file }}"

echo Downloading get-pip.py...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py'}"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to download get-pip.py
    pause
    exit /b 1
)

echo Installing pip...
"%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install pip
    pause
    exit /b 1
)
echo OK
echo.

echo [5/5] Installing virtualenv for portable venv creation...
"%PYTHON_DIR%\python.exe" -m pip install virtualenv

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install virtualenv
    pause
    exit /b 1
)
echo OK
echo.

echo Cleaning up...
del "%TEMP_ZIP%" 2>nul
del "%PYTHON_DIR%\get-pip.py" 2>nul

:skip_download

echo ================================================
echo    Embedded Python Setup Complete!
echo ================================================
echo.
echo Embedded Python installed at: %PYTHON_DIR%
echo.
echo NEXT STEPS:
echo 1. Run scripts\installation\prepare_setup.bat to create the portable venv
echo 2. Test with scripts\launcher.bat
echo 3. Copy entire project folder to target PC
echo.
pause
