@echo off
REM ============================================================================
REM  CHSuite (Tauri) -- Push to GitHub
REM  Stages, commits, and pushes to https://github.com/iamjrmh/CHSuite.
REM  .gitignore already excludes build caches (node_modules, dist,
REM  src-tauri/target, sidecar/.venv, etc.) and Software\ (installers are
REM  published via GitHub Releases, not committed).
REM ============================================================================
SETLOCAL ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

SET "SCRIPT_DIR=%~dp0"
SET "REMOTE_URL=https://github.com/iamjrmh/CHSuite.git"

echo.
echo  =============================================================
echo   CHSuite -- Push to GitHub
echo  =============================================================
echo.

where git >nul 2>&1 || ( echo  [ERROR] git not found on PATH. & goto :error )

REM -- [1/5] Repo check ----------------------------------------------------------
IF NOT EXIST "%SCRIPT_DIR%.git" (
    echo  [1/5] No git repo here yet -- initializing...
    git init || goto :error
    git remote add origin "%REMOTE_URL%" || goto :error
    echo        origin set to %REMOTE_URL%
) ELSE (
    echo  [1/5] Existing git repo found.
    git remote get-url origin >nul 2>&1 || git remote add origin "%REMOTE_URL%"
)
echo.

REM -- [2/5] Stage changes ---------------------------------------------------------
echo  [2/5] Staging changes...
git add -A || goto :error
echo.

REM -- [3/5] Anything to commit? -----------------------------------------------
echo  [3/5] Checking for changes...
git diff --cached --quiet
IF NOT ERRORLEVEL 1 (
    echo        Nothing to commit -- working tree matches the last commit.
    goto :end
)
echo.

REM -- [4/5] Commit ---------------------------------------------------------------
set /p "COMMIT_MSG=[4/5] Commit message (Enter for default): "
IF "%COMMIT_MSG%"=="" set "COMMIT_MSG=Update CHSuite"
git commit -m "%COMMIT_MSG%" || goto :error
echo.

REM -- [5/5] Push -------------------------------------------------------------
echo  [5/5] Pushing to origin...
git push -u origin HEAD
IF ERRORLEVEL 1 (
    echo.
    echo  [WARN] Push was rejected. This repo already has history from the
    echo         original Tkinter CHSuite, which this rewrite's local git
    echo         history doesn't share -- a normal push can't reconcile that.
    echo         This script will NOT force-push automatically. If you want
    echo         this rebuild's code to fully replace what's on GitHub, review
    echo         the remote first, then push manually with the appropriate
    echo         flag once you're sure.
    goto :error
)
echo.

echo  =============================================================
echo   PUSH SUCCESSFUL
echo  =============================================================
goto :end

:error
echo.
echo  =============================================================
echo   PUSH FAILED
echo  =============================================================
ENDLOCAL
EXIT /B 1

:end
ENDLOCAL
EXIT /B 0
