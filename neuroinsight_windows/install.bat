@echo off
REM NeuroInsight Docker - Install Command
powershell.exe -ExecutionPolicy Bypass -File "%~dp0neuroinsight-docker.ps1" install %*
