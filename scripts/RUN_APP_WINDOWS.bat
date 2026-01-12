@echo off
setlocal
cd /d "%~dp0\.."

echo Starting Sugar App (local)...
docker compose -f docker-compose.local.yml up -d --build
if errorlevel 1 (
  echo.
  echo ERROR: Docker failed. Install Docker Desktop and make sure it is running.
  pause
  exit /b 1
)

start "" "http://localhost:8080"
echo Done.
