@echo off
REM ============================================================================
REM  CHSuite (Tauri) -- Automated Windows build
REM  Produces a fully self-contained NSIS installer:
REM    1. builds the Python sidecar into a standalone .exe (PyInstaller)
REM    2. builds the React frontend (tsc + vite)
REM    3. compiles the Tauri shell and bundles everything
REM  The end result needs NO Python and NO Node on the target machine.
REM ============================================================================
SETLOCAL ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

SET "SCRIPT_DIR=%~dp0"
SET "SIDECAR=%SCRIPT_DIR%sidecar"
SET "VENV=%SIDECAR%\.venv"
SET "VPY=%VENV%\Scripts\python.exe"
SET "SIDECAR_EXE=%SIDECAR%\chsuite-sidecar.exe"
SET "SOFTWARE_DIR=%SCRIPT_DIR%Software"
SET "BUNDLE_DIR=%SCRIPT_DIR%src-tauri\target\release\bundle"

echo.
echo  =============================================================
echo   CHSuite (Tauri) -- Build Script
echo  =============================================================
echo.

REM -- [1/10] Version check --------------------------------------------------------
echo  [1/10] Version check...
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "(Get-Content -Raw '%SCRIPT_DIR%package.json' | ConvertFrom-Json).version"`) do set "CUR_VERSION=%%V"
echo        Current version: !CUR_VERSION!
set /p "NEW_VERSION=        New version (X.X.X, Enter to keep !CUR_VERSION!): "
IF "!NEW_VERSION!"=="" (
    set "NEW_VERSION=!CUR_VERSION!"
    echo        Keeping version !CUR_VERSION!.
) ELSE (
    echo !NEW_VERSION!| findstr /r "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul
    IF ERRORLEVEL 1 (
        echo        [WARN] "!NEW_VERSION!" is not X.X.X -- keeping !CUR_VERSION!.
        set "NEW_VERSION=!CUR_VERSION!"
    ) ELSE (
        echo        Bumping version !CUR_VERSION! -^> !NEW_VERSION!...
        powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%bump-version.ps1" -Version "!NEW_VERSION!" || goto :error
    )
)
echo.

REM -- [2/10] Stop any running sidecar instances ---------------------------------
echo  [2/10] Stopping any running chsuite-sidecar.exe instances...
taskkill /F /IM chsuite-sidecar.exe /T >nul 2>&1
echo        done.
echo.

REM -- [3/10] Prerequisites ------------------------------------------------------
echo  [3/10] Checking prerequisites...
where node      >nul 2>&1 || ( echo  [ERROR] Node.js not found on PATH. & goto :error )
where npm       >nul 2>&1 || ( echo  [ERROR] npm not found on PATH.     & goto :error )
where cargo     >nul 2>&1 || ( echo  [ERROR] Rust/cargo not found on PATH. Install from https://rustup.rs & goto :error )
py -3.11 --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo  [ERROR] Python 3.11 not found ^(py -3.11^). Install Python 3.11 64-bit.
    goto :error
)
echo        node:  & node --version
echo        cargo: & cargo --version
echo.

REM -- [4/10] Sidecar virtual environment ---------------------------------------
echo  [4/10] Preparing sidecar virtual environment...
IF NOT EXIST "%VPY%" (
    echo        Creating .venv ...
    py -3.11 -m venv "%VENV%" || ( echo  [ERROR] Could not create .venv & goto :error )
) ELSE (
    echo        .venv already present -- reusing.
)
echo.

REM -- [5/10] Python dependencies + PyInstaller ---------------------------------
echo  [5/10] Installing sidecar dependencies...
"%VPY%" -m pip install --upgrade pip --quiet || goto :error
"%VPY%" -m pip install -r "%SIDECAR%\requirements.txt" --quiet || ( echo  [ERROR] pip install failed & goto :error )
"%VPY%" -m pip install pyinstaller --quiet || ( echo  [ERROR] could not install PyInstaller & goto :error )
echo        dependencies ready.
echo.

REM -- [6/10] Freeze the sidecar into a standalone exe --------------------------
echo  [6/10] Building standalone sidecar (PyInstaller)...
pushd "%SIDECAR%"
"%VPY%" -m PyInstaller --noconfirm --onefile --name chsuite-sidecar ^
    --distpath "%SIDECAR%" --workpath "%SIDECAR%\build_pyi" --specpath "%SIDECAR%\build_pyi" ^
    --paths "%SIDECAR%" ^
    --collect-all UnityPy ^
    --collect-all PIL ^
    --collect-all texture2ddecoder ^
    --collect-all etcpak ^
    --collect-all archspec ^
    --collect-all brotli ^
    --collect-all lz4 ^
    --collect-all fmod_toolkit ^
    --collect-all pyfmodex ^
    --collect-all requests ^
    "%SIDECAR%\chsuite_api.py"
SET "PYI_RC=!ERRORLEVEL!"
popd
IF NOT "!PYI_RC!"=="0" ( echo  [ERROR] PyInstaller failed. & goto :error )
IF NOT EXIST "%SIDECAR_EXE%" ( echo  [ERROR] sidecar exe was not produced. & goto :error )
echo        sidecar.exe ready: %SIDECAR_EXE%
echo.

REM -- [7/10] Frontend dependencies ---------------------------------------------
echo  [7/10] Installing frontend dependencies...
IF NOT EXIST "%SCRIPT_DIR%node_modules" (
    call npm install || ( echo  [ERROR] npm install failed & goto :error )
) ELSE (
    echo        node_modules present -- skipping npm install.
)
echo.

REM -- [8/10] Build the Tauri app -----------------------------------------------
echo  [8/10] Building the Tauri app ^(frontend + Rust + installer^)...
echo        This compiles Rust in release mode and may take several minutes.
call npm run tauri build || ( echo  [ERROR] tauri build failed & goto :error )
echo.

REM -- [9/10] Collect installers + raw exe into Software\ ------------------------
echo  [9/10] Collecting installers and .exe into Software\...
IF NOT EXIST "%SOFTWARE_DIR%" MKDIR "%SOFTWARE_DIR%"

IF EXIST "%BUNDLE_DIR%\nsis" (
    FOR %%F IN ("%BUNDLE_DIR%\nsis\*.exe") DO COPY /Y "%%F" "%SOFTWARE_DIR%\" >NUL
)
IF EXIST "%BUNDLE_DIR%\msi" (
    FOR %%F IN ("%BUNDLE_DIR%\msi\*.msi") DO COPY /Y "%%F" "%SOFTWARE_DIR%\" >NUL
)
IF EXIST "%SCRIPT_DIR%src-tauri\target\release\chsuite.exe" (
    COPY /Y "%SCRIPT_DIR%src-tauri\target\release\chsuite.exe" "%SOFTWARE_DIR%\" >NUL
)
echo        Software\ ready: %SOFTWARE_DIR%
echo.

REM -- [10/10] Clean up intermediate build junk ---------------------------------
echo  [10/10] Cleaning up intermediate build files...
IF EXIST "%SIDECAR%\build_pyi" RMDIR /S /Q "%SIDECAR%\build_pyi"
IF EXIST "%SIDECAR%\__pycache__" RMDIR /S /Q "%SIDECAR%\__pycache__"
IF EXIST "%SIDECAR%\core\__pycache__" RMDIR /S /Q "%SIDECAR%\core\__pycache__"
IF EXIST "%SCRIPT_DIR%dist" RMDIR /S /Q "%SCRIPT_DIR%dist"
REM node_modules, sidecar\.venv, and src-tauri\target are left alone on
REM purpose -- they're dependency/incremental-compile caches, not junk, and
REM wiping them would force a full reinstall/recompile on the next build.
echo        done.

echo.
echo  =============================================================
echo   BUILD SUCCESSFUL
echo  =============================================================
echo.
echo   Installer + exe : %SOFTWARE_DIR%\
echo   Raw build output: src-tauri\target\release\
echo.
echo   The installer is self-contained -- no Python/Node needed to run it.
echo.
goto :end

:error
echo.
echo  =============================================================
echo   BUILD FAILED ^(exit code %ERRORLEVEL%^)
echo  =============================================================
echo  Fix the error above and run build.bat again.
ENDLOCAL
EXIT /B 1

:end
ENDLOCAL
EXIT /B 0
