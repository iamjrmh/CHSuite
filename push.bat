@echo off
REM ============================================================================
REM  CHSuite (Tauri) -- Push to GitHub
REM  Stages, commits (if needed), and always pushes to https://github.com/iamjrmh/CHSuite (main).
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

REM -- [1/4] Repo check ----------------------------------------------------------
IF NOT EXIST "%SCRIPT_DIR%.git" (
    echo  [1/4] No git repo here yet -- initializing...
    git init || goto :error
    git remote add origin "%REMOTE_URL%" || goto :error
    echo        origin set to %REMOTE_URL%
) ELSE (
    echo  [1/4] Existing git repo found.
    git remote get-url origin >nul 2>&1 || git remote add origin "%REMOTE_URL%"
)
REM Force the local branch to be named "main" regardless of git's default
REM (older/unconfigured git inits as "master") so this always pushes to main.
git branch -M main || goto :error
echo.

REM -- [2/4] Stage changes ---------------------------------------------------------
echo  [2/4] Staging changes...
git add -A || goto :error
echo.

REM -- [3/4] Commit if there's anything staged -------------------------------------
echo  [3/4] Checking for changes to commit...
git diff --cached --quiet
IF ERRORLEVEL 1 (
    set /p "COMMIT_MSG=       Commit message (Enter for default): "
    IF "!COMMIT_MSG!"=="" set "COMMIT_MSG=Update CHSuite"
    git commit -m "!COMMIT_MSG!" || goto :error
) ELSE (
    echo        Nothing new to stage -- skipping commit, still checking for
    echo        unpushed commits below.
)
echo.

REM -- [4/4] Push -------------------------------------------------------------
REM Always runs, even with nothing new to commit -- there may already be
REM local commits that were never successfully pushed to origin/main.
REM Force-pushes: origin/main already has unrelated commits this local repo
REM doesn't share, and this rebuild's history is meant to fully replace it.
echo  [4/4] Force-pushing to origin/main...
git push -u origin main --force
IF ERRORLEVEL 1 (
    echo.
    echo  [WARN] Push failed -- check your GitHub auth/credentials and
    echo         network connection.
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
