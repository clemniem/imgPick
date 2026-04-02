@echo off
echo imgPick Setup wird gestartet...
powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo Setup fehlgeschlagen. Siehe Fehlermeldung oben.
)
pause
