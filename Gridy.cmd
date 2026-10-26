@echo off
setlocal
set "GRIDY_APP=%~dp0dist\1.0.3-20261011-155416-995019\GardenToolsGridy\GardenToolsGridy.exe"
if exist "%GRIDY_APP%" (
    start "" /D "%~dp0" "%GRIDY_APP%"
) else (
    echo Gridy build not found. See README.md for build instructions.
    pause
)
