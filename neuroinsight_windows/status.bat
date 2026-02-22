@echo off
REM NeuroInsight Docker - Status Command
powershell.exe -ExecutionPolicy Bypass -File "%~dp0neuroinsight-docker.ps1" status %*
