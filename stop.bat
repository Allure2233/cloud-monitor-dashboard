@echo off
title Cloud Monitor - Stop

set PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%

echo.
echo  ========================================
echo    Cloud Monitor Dashboard - Stop
echo  ========================================
echo.

cd /d "%~dp0"
docker compose down

echo.
echo  [OK] All containers stopped.
echo.
pause
