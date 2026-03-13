@echo off
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install-nir-windows.ps1"
if %ERRORLEVEL% neq 0 (
  echo Installer verification failed. Please check output above.
  exit /b %ERRORLEVEL%
)
