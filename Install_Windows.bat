@echo off
setlocal

echo ============================================
echo   ProteomicsViewer Installer
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Install the package
echo Installing ProteomicsViewer...
set "PROJDIR=%~dp0."
pip install -e "%PROJDIR%" --quiet
if errorlevel 1 (
    echo.
    echo ERROR: Installation failed. Try running as administrator.
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo.
echo Usage:
echo   protview                    Start the viewer
echo   protview file.txt           Start with a file pre-loaded
echo   protview --port 9000        Use a custom port
echo.
echo Starting ProteomicsViewer now...
echo.
protview
pause
