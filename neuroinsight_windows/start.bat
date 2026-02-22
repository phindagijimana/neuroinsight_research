@echo off
REM NeuroInsight Docker - Start Command
powershell.exe -ExecutionPolicy Bypass -File "%~dp0neuroinsight-docker.ps1" start %*
