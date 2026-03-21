@echo off
setlocal enabledelayedexpansion

:: ── Keep window open if double-clicked ─────────────────────────────────────
if not defined _RELAUNCHED (
    set _RELAUNCHED=1
    cmd /k ""%~f0""
    exit /b
)

title CHSuite Builder
cd /d "%~dp0"

echo.
echo  =============================================================
echo   CHSuite -- Automated Build Script
echo  =============================================================
echo.

:: ── Sanity checks ────────────────────────────────────────────────────────────
if not exist "CHSuite.py" (
    echo  [ERROR] CHSuite.py not found in this folder.
    echo  Make sure build.bat, write_spec.py, and rthook_texture2d.py are
    echo  all in the same folder as CHSuite.py.
    goto :fail
)

if not exist "write_spec.py" (
    echo  [ERROR] write_spec.py not found in this folder.
    goto :fail
)

if not exist "rthook_texture2d.py" (
    echo  [ERROR] rthook_texture2d.py not found in this folder.
    goto :fail
)

:: ── [1/7] Locate Python 3.11 ─────────────────────────────────────────────────
echo  [1/7] Locating Python 3.11...

set "PYTHON="

py -3.11 --version >nul 2>&1
if !errorlevel! == 0 ( set "PYTHON=py -3.11" & goto :found_python )

python3.11 --version >nul 2>&1
if !errorlevel! == 0 ( set "PYTHON=python3.11" & goto :found_python )

for %%P in (
    "C:\Python311\python.exe"
    "C:\Program Files\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) do (
    if exist %%P ( set "PYTHON=%%~P" & goto :found_python )
)

python --version 2>&1 | findstr "3.11" >nul
if !errorlevel! == 0 ( set "PYTHON=python" & goto :found_python )

echo  [ERROR] Python 3.11 not found on this machine.
echo  Download: https://www.python.org/downloads/release/python-3119/
echo  During install: check "Add Python to PATH"
goto :fail

:found_python
echo  Found: %PYTHON%
%PYTHON% --version
echo.

:: ── [2/7] Create virtual environment ─────────────────────────────────────────
echo  [2/7] Setting up virtual environment (.venv)...

if exist ".venv" (
    echo  .venv already exists -- skipping creation.
) else (
    %PYTHON% -m venv .venv
    if !errorlevel! neq 0 ( echo  [ERROR] venv creation failed. & goto :fail )
    echo  .venv created.
)

call ".venv\Scripts\activate.bat"
if !errorlevel! neq 0 ( echo  [ERROR] Could not activate .venv. & goto :fail )
echo  Activated: %VIRTUAL_ENV%
echo.

:: ── [3/7] Install dependencies ────────────────────────────────────────────────
echo  [3/7] Installing dependencies (this may take a minute)...

python -m pip install --upgrade pip setuptools wheel
if !errorlevel! neq 0 ( echo  [ERROR] pip upgrade failed. & goto :fail )

pip install "Pillow==10.4.0"
if !errorlevel! neq 0 ( echo  [ERROR] Pillow install failed. & goto :fail )

pip install "UnityPy==1.25.0"
if !errorlevel! neq 0 ( echo  [ERROR] UnityPy install failed. & goto :fail )

pip install brotli brotlicffi lz4 texture2ddecoder
if !errorlevel! neq 0 ( echo  [ERROR] Native dependency install failed. & goto :fail )

pip install requests
if !errorlevel! neq 0 ( echo  [ERROR] requests install failed. & goto :fail )

pip install pypresence
if !errorlevel! neq 0 ( echo  [ERROR] pypresence install failed. & goto :fail )

pip install "pyinstaller==6.10.0"
if !errorlevel! neq 0 ( echo  [ERROR] PyInstaller install failed. & goto :fail )

echo.
echo  All dependencies installed.
echo.

:: ── [4/7] Verify critical imports ────────────────────────────────────────────
echo  [4/7] Verifying critical imports...

python -c "import UnityPy; print('  UnityPy          OK  v' + UnityPy.__version__)"
if !errorlevel! neq 0 ( echo  [ERROR] UnityPy import failed. & goto :fail )

python -c "import texture2ddecoder; print('  texture2ddecoder OK')"
if !errorlevel! neq 0 ( echo  [ERROR] texture2ddecoder import failed. & goto :fail )

python -c "import lz4.block; print('  lz4.block        OK')"
if !errorlevel! neq 0 ( echo  [ERROR] lz4 import failed. & goto :fail )

python -c "from PIL import Image; print('  Pillow           OK  v' + Image.__version__)"
if !errorlevel! neq 0 ( echo  [ERROR] Pillow import failed. & goto :fail )

python -c "import requests; print('  requests         OK  v' + requests.__version__)"
if !errorlevel! neq 0 ( echo  [ERROR] requests import failed. & goto :fail )

python -c "import pypresence; print('  pypresence       OK  v' + pypresence.__version__)"
if !errorlevel! neq 0 ( echo  [ERROR] pypresence import failed. & goto :fail )

echo.

:: ── [5/7] Write spec file ─────────────────────────────────────────────────────
echo  [5/7] Writing CHSuite.spec...

python write_spec.py
if !errorlevel! neq 0 ( echo  [ERROR] write_spec.py failed. & goto :fail )

if not exist "CHSuite.spec" (
    echo  [ERROR] CHSuite.spec was not created.
    goto :fail
)
echo.

:: ── [6/7] Clean old build artifacts ──────────────────────────────────────────
echo  [6/7] Cleaning previous build and dist folders...

if exist "build" ( rmdir /s /q "build" && echo  Removed: build\ )
if exist "dist"  ( rmdir /s /q "dist"  && echo  Removed: dist\  )
echo.

:: ── [7/7] Run PyInstaller ─────────────────────────────────────────────────────
echo  [7/7] Running PyInstaller (takes 1-3 minutes, output below)...
echo  ---------------------------------------------------------
echo.

pyinstaller CHSuite.spec
if !errorlevel! neq 0 (
    echo.
    echo  ---------------------------------------------------------
    echo  [ERROR] PyInstaller failed. Read the output above.
    echo.
    echo  Common causes:
    echo    - "ModuleNotFoundError" : a hidden import is missing
    echo    - "collect_all" error   : a package failed to install
    echo    - Antivirus blocked a write into dist\
    echo.
    goto :fail
)

:: ── Hide _internal folder ─────────────────────────────────────────────────────
echo  Hiding _internal folder...
if exist "dist\CHSuite\_internal" (
    attrib +h "dist\CHSuite\_internal"
    echo  dist\CHSuite\_internal is now hidden.
) else (
    echo  [WARNING] dist\CHSuite\_internal not found -- skipping attrib.
)
echo.

:: ── Copy and hide Images folder ───────────────────────────────────────────────
echo  Copying Images folder to dist\CHSuite...
if exist "Images\" (
    xcopy /E /I /Y "Images" "dist\CHSuite\Images" >nul
    attrib +h "dist\CHSuite\Images"
    echo  Images folder copied and hidden.
) else (
    echo  [WARNING] Images folder not found in %~dp0 -- skipping copy.
    echo  Place your greyscale note template in an Images\ folder next to CHSuite.py.
)
echo.

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo  =============================================================
echo   BUILD SUCCESSFUL
echo  =============================================================
echo.
echo   Executable : dist\CHSuite\CHSuite.exe
echo   Full bundle: dist\CHSuite\
echo.
echo   ZIP the entire dist\CHSuite\ folder to distribute.
echo   Do NOT ship the .exe alone -- it needs _internal\ beside it.
echo.
echo   Test now: run dist\CHSuite\CHSuite.exe from this window.
echo   If it crashes silently, the error will print here.
echo.

:: NSIS installer build (optional)
echo  [Optional] Looking for NSIS to build installer...

set "MAKENSIS="
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
if exist "C:\Program Files\NSIS\makensis.exe" set "MAKENSIS=C:\Program Files\NSIS\makensis.exe"

if not defined MAKENSIS (
    echo  NSIS not found -- skipping installer.
    echo  Install from https://nsis.sourceforge.io/Download then rerun to get CHSuite_Setup.exe
    goto :done_nsis
)

if not exist "CHSuite_Installer.nsi" (
    echo  CHSuite_Installer.nsi not found -- skipping installer.
    goto :done_nsis
)

echo  Compiling NSIS installer...
"%MAKENSIS%" CHSuite_Installer.nsi
if !errorlevel! neq 0 (
    echo  [WARNING] NSIS compile failed. .exe build is still good.
    goto :done_nsis
)
echo  Installer built: CHSuite_Setup.exe

:done_nsis
echo.
echo  =============================================================
echo   BUILD SUCCESSFUL
echo  =============================================================
echo.
echo   Executable : dist\CHSuite\CHSuite.exe
echo   Installer  : CHSuite_Setup.exe  (if NSIS was installed)
echo.
echo   Without installer: ZIP the entire dist\CHSuite\ folder.
echo   With installer:    ship CHSuite_Setup.exe standalone.
echo.
echo   Test: run dist\CHSuite\CHSuite.exe from this window.
echo.
goto :eof

:fail
echo.
echo  Build did not complete. Fix the error above and run build.bat again.
echo.
