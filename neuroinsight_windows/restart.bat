@echo off
REM NeuroInsight Docker - Restart Command
powershell.exe -ExecutionPolicy Bypass -File "%~dp0neuroinsight-docker.ps1" restart %*
