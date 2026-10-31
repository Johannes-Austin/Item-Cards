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

REM Re-parse the pages already saved in raw_pages (no downloading). Pages not saved yet are downloaded.
"%PYTHON_EXE%" "%~dp0DataGather.py" --cached

echo.
echo Python exit code: %errorlevel%
pause
