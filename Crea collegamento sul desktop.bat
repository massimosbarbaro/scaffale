@echo off
chcp 65001 >nul
title Scaffale - collegamento
cd /d "%~dp0"
echo.
echo   Creo il collegamento «Scaffale» sul desktop...
echo.
powershell -NoProfile -Command ^
  "$b=(Get-Location).Path;" ^
  "$w=New-Object -ComObject WScript.Shell;" ^
  "$s=$w.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Scaffale.lnk'));" ^
  "$s.TargetPath=(Join-Path $b 'Avvia Scaffale.bat');" ^
  "$s.WorkingDirectory=$b;" ^
  "$s.IconLocation=((Join-Path $b 'scaffale.ico')+',0');" ^
  "$s.Description='Scaffale - cerca dentro il tuo archivio';" ^
  "$s.WindowStyle=1; $s.Save();" ^
  "Write-Host '  Fatto: trovi Scaffale sul desktop.'"
echo.
pause
