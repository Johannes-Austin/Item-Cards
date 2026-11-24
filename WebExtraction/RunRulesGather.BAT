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

REM Builds rules.csv (the Rules tab) from the official SRD 5.1 rules text. Add --cached to reuse the download saved in raw_pages.
"%PYTHON_EXE%" "%~dp0RulesGather.py" %*

echo.
echo Python exit code: %errorlevel%
pause
