@echo off
setlocal
set "SRC=%~dp0"
set "DST=%TEMP%\PixelsUndoHost"
if not exist "%DST%" mkdir "%DST%" >nul 2>&1
copy /Y "%SRC%PixelsUndo.exe" "%DST%\PixelsUndo.exe" >nul 2>&1
copy /Y "%SRC%*.dll" "%DST%\" >nul 2>&1
if not exist "%DST%\PixelsUndo.exe" (
  echo Could not prepare the native host in %DST%.
  pause
  exit /b 1
)
set "PIXELSUNDO_APP_DIR=%SRC%"
start "" "%DST%\PixelsUndo.exe"
