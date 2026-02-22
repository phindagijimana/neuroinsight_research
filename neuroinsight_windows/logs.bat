@echo off
REM NeuroInsight Docker - Logs Command
powershell.exe -ExecutionPolicy Bypass -File "%~dp0neuroinsight-docker.ps1" logs %*
