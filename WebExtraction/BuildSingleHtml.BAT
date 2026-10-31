@echo off
setlocal

cd /d "%~dp0"

REM Uses the local Python environment if it exists, otherwise whatever "python" is installed.
REM The build script only needs the Python standard library.
set "PYTHON_EXE=%~dp0my_env\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

REM Embeds items.csv into template.html (both in this folder) and writes index.html in the main CardHTML folder (one level up).
REM To use a different CSV:  BuildSingleHtml.BAT --csv MyOtherItems.csv
"%PYTHON_EXE%" "%~dp0build_single_html.py" %*

echo.
echo Python exit code: %errorlevel%
pause
