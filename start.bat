@echo off
title Cloud Monitor - Start

set PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%

echo.
echo  ========================================
echo    Cloud Monitor Dashboard
echo  ========================================
echo.

docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Docker is not running!
    echo  Please open Docker Desktop first.
    echo.
    pause
    exit /b 1
)

echo  [1/3] Starting containers...
cd /d "%~dp0"
docker compose up -d

echo.
echo  [2/3] Waiting for services...
timeout /t 5 /nobreak >nul

echo.
echo  [3/3] Seeding data...
docker compose exec -T web python /seed-scripts/seed_data.py

echo.
echo  ========================================
echo    Started!
echo  ========================================
echo.
echo    Dashboard: http://localhost:5000
echo.
echo    Press any key to open in browser...
pause >nul

start http://localhost:5000
