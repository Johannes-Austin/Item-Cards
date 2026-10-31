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

REM Scrapes the spell list and every spell page into spells.csv. Add --cached to reuse the pages saved in raw_pages.
"%PYTHON_EXE%" "%~dp0SpellGather.py" %*

echo.
echo Python exit code: %errorlevel%
pause
