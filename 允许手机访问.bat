@echo off
setlocal
cd /d "%~dp0"
echo Requesting administrator permission to allow phone access on this Wi-Fi...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%~dp0tools\allow_lan_firewall.ps1'"
if errorlevel 1 (
  echo.
  echo Could not open the permission prompt. Right-click this file and choose "Run as administrator".
  pause
)
