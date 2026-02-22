@echo off
REM NeuroInsight Docker - Stop Command
powershell.exe -ExecutionPolicy Bypass -File "%~dp0neuroinsight-docker.ps1" stop %*
