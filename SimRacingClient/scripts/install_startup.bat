@echo off
echo ================================================
echo    Install SimRacing Project to Startup
echo ================================================
echo.

set "SSD_ROOT=%~dp0.."

echo Creating startup shortcut...
set "STARTUP_SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Launch SimRacing Project.lnk"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP_SHORTCUT%'); $s.TargetPath = '%SSD_ROOT%\scripts\launcher.bat'; $s.WorkingDirectory = '%SSD_ROOT%'; $s.Save()"

if exist "%STARTUP_SHORTCUT%" (
    echo.
    echo ================================================
    echo    Success!
    echo ================================================
    echo.
    echo SimRacing Project will now start automatically
    echo when Windows boots.
    echo.
    echo To remove from startup, delete:
    echo %STARTUP_SHORTCUT%
    echo.
) else (
    echo.
    echo ERROR: Could not create startup shortcut
    echo.
    echo Make sure you have permission to write to:
    echo %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
    echo.
)

pause