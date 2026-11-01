@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0my_env\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Virtual environment not found: %PYTHON_EXE%
    echo Run InstallPython.BAT to rebuild the local environment.
    pause
    exit /b 1
)

REM Downloads the Open5e magic items and spells we don't have yet into open5eItems.csv and open5eSpells.csv. Add --cached to reuse the download saved in raw_pages.
"%PYTHON_EXE%" "%~dp0Open5eGather.py" %*

echo.
echo Python exit code: %errorlevel%
pause
