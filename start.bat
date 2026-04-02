@echo off
cd /d "%~dp0"
echo imgPick GUI wird gestartet...
echo.
uv run python gui.py
echo.
if errorlevel 1 echo Fehler beim Starten der GUI. Siehe Meldung oben.
echo.
pause
