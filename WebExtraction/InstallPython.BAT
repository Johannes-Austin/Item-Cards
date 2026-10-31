@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

REM ============================================================
REM CONFIGURATION
REM ============================================================

set VENV_NAME=my_env
set "PYTHON_CMD="
set "PYTHON_INSTALLER=python-3.12.1-amd64.exe"
set "VENV_PYTHON=%~dp0%VENV_NAME%\Scripts\python.exe"

REM Local package cache folders
set OFFLINE_PACKAGES=offline_packages
set AUTO_PACKAGES=automatic_packages

REM ============================================================
REM PACKAGE LIST (easy to edit)
REM ============================================================

set PACKAGES=^
beautifulsoup4 ^
requests

REM ============================================================
REM CREATE VENV IF IT DOES NOT EXIST
REM ============================================================

if not exist "%VENV_PYTHON%" (
    echo Creating virtual environment...
    call :ResolvePython
    if not defined PYTHON_CMD (
        call :InstallBundledPython
        call :ResolvePython
    )
    if not defined PYTHON_CMD (
        goto :python_missing
    )
    !PYTHON_CMD! -m venv "%VENV_NAME%"
    if errorlevel 1 (
        goto :venv_failed
    )
)

REM ============================================================
REM VERIFY VENV
REM ============================================================

if not exist "%VENV_PYTHON%" (
    goto :venv_failed
)

echo.
echo Upgrading pip...
"%VENV_PYTHON%" -m pip install --upgrade pip

REM ============================================================
REM CREATE PACKAGE FOLDERS IF MISSING
REM ============================================================

if not exist %OFFLINE_PACKAGES% (
    mkdir %OFFLINE_PACKAGES%
)

if not exist %AUTO_PACKAGES% (
    mkdir %AUTO_PACKAGES%
)

REM ============================================================
REM INSTALL PACKAGES
REM ============================================================

for %%P in (%PACKAGES%) do (

    echo.
    echo ========================================================
    echo Processing package: %%P
    echo ========================================================

    REM --------------------------------------------------------
    REM Check if package already installed
    REM --------------------------------------------------------

    "%VENV_PYTHON%" -m pip show %%P >nul 2>&1

    if !errorlevel! == 0 (
        echo Package already installed: %%P
    ) else (

        echo Package not installed: %%P

        REM ----------------------------------------------------
        REM Attempt OFFLINE install first
        REM ----------------------------------------------------

        echo Attempting offline install...

        "%VENV_PYTHON%" -m pip install ^
            --no-index ^
            --find-links=%OFFLINE_PACKAGES% ^
            --find-links=%AUTO_PACKAGES% ^
            %%P

        REM ----------------------------------------------------
        REM If offline failed, download online
        REM ----------------------------------------------------

        if !errorlevel! neq 0 (

            echo Offline install failed.
            echo Downloading package online...

            "%VENV_PYTHON%" -m pip download %%P -d %AUTO_PACKAGES%

            if !errorlevel! neq 0 (
                echo FAILED TO DOWNLOAD %%P
            ) else (

                echo Installing downloaded package...

                "%VENV_PYTHON%" -m pip install ^
                    --no-index ^
                    --find-links=%AUTO_PACKAGES% ^
                    %%P

                if !errorlevel! neq 0 (
                    echo FAILED TO INSTALL %%P
                ) else (
                    echo SUCCESSFULLY INSTALLED %%P
                )
            )
        ) else (
            echo SUCCESSFULLY INSTALLED %%P FROM OFFLINE CACHE
        )
    )
)

echo.
echo ============================================================
echo Environment setup complete.
echo ============================================================

pause
exit /b 0

:ResolvePython
set "PYTHON_CMD="

py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
    exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    "%LocalAppData%\Programs\Python\Python312\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD="%LocalAppData%\Programs\Python\Python312\python.exe"
        exit /b 0
    )
)

if exist "%ProgramFiles%\Python312\python.exe" (
    "%ProgramFiles%\Python312\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD="%ProgramFiles%\Python312\python.exe"
        exit /b 0
    )
)

py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.11"
    exit /b 0
)

py -3.10 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.10"
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)

python3 -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    exit /b 0
)

exit /b 0

:InstallBundledPython
if not exist "%~dp0%PYTHON_INSTALLER%" (
    exit /b 0
)

echo.
echo No suitable Python runtime was found.
echo Attempting to install bundled Python: %PYTHON_INSTALLER%
echo.
start /wait "" "%~dp0%PYTHON_INSTALLER%" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_venv=1
if errorlevel 1 (
    echo.
    echo Bundled Python installer exited with error %errorlevel%.
)
exit /b 0

:python_missing
echo.
echo ============================================================
echo No suitable Python runtime was found.
echo ============================================================
echo.
echo InstallPython.BAT tried to find Python and also tried the bundled installer
echo if %PYTHON_INSTALLER% was present. A usable Python runtime still was not found.
echo.
echo Fix:
echo   1. Run %PYTHON_INSTALLER% as Administrator.
echo   2. Finish the Python install or repair.
echo   3. Run InstallPython.BAT again.
echo.
echo If Python is already installed, make sure it is added to PATH, that the
echo Python Launcher can find it, and that Python's venv feature is installed.
pause
exit /b 1

:venv_failed
echo.
echo ============================================================
echo Virtual environment creation failed.
echo ============================================================
echo.
echo The Python runtime was found, but %VENV_NAME% could not be created.
echo If this PC already has a broken %VENV_NAME% folder, delete it and rerun
echo InstallPython.BAT.
echo If Python itself is missing, run python-3.12.1-amd64.exe as Administrator
echo and then rerun InstallPython.BAT.
pause
exit /b 1
