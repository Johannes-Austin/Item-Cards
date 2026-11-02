@echo off
setlocal

cd /d "%~dp0"

REM Uses the local Python environment if it exists, otherwise whatever "python" is installed.
REM The build script needs the Python standard library, plus the "cryptography" package for the personal items.
set "PYTHON_EXE=%~dp0my_env\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

REM Embeds the CSVs into template.html (both in this folder) and writes index.html in the main CardHTML folder (one level up).
REM If griffonsSaddlebag.csv exists, it asks for the passphrase that locks those items (Enter keeps the ones already built).
REM To use a different CSV:  BuildSingleHtml.BAT --csv MyOtherItems.csv
"%PYTHON_EXE%" "%~dp0build_single_html.py" %*

echo.
echo Python exit code: %errorlevel%
pause
