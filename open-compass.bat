@echo off
setlocal
chcp 65001 >nul
if defined COMPASS_HOME (set "CH=%COMPASS_HOME%") else (set "CH=%USERPROFILE%\.compass")
if not exist "%CH%\bin\compass.cmd" (
  echo Compass is not installed yet. Run install.bat first.
  pause
  exit /b 1
)
"%CH%\bin\compass.cmd" open
if errorlevel 1 pause
