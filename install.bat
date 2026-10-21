@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo   Compass installer
echo   -----------------
echo.

if defined COMPASS_HOME (set "CH=%COMPASS_HOME%") else (set "CH=%USERPROFILE%\.compass")

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
  if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" (
    set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
  )
)
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  echo Python was not found.
  echo Install Python 3.9+ or run this folder inside WorkBuddy.
  pause
  exit /b 1
)

%PY% install.py
if errorlevel 1 (
  echo.
  echo Install failed. Read the message above.
  pause
  exit /b 1
)

echo.
echo Choose a short name for your dashboard page.
echo Example: xiaoyu   (lowercase letters and numbers only)
set /p HANDLE=Name:
if "%HANDLE%"=="" set "HANDLE=me"

"%CH%\bin\compass.cmd" init --handle %HANDLE%
if errorlevel 1 (
  echo.
  echo That name may be taken or invalid. Try another one.
  set /p HANDLE=Name:
  "%CH%\bin\compass.cmd" init --handle %HANDLE%
)

echo.
echo Opening your dashboard...
"%CH%\bin\compass.cmd" open

echo.
echo Done.
echo 1. Restart WorkBuddy once (fully quit, then open again).
echo 2. Then just say: I don't know what I want to do.
echo.
echo To reopen the dashboard later, double-click: open-compass.bat
echo.
pause
