@echo off
setlocal
cd /d "%~dp0\.."

echo Updating Sugar App (local)...
docker compose -f docker-compose.local.yml up -d --build
if errorlevel 1 (
  echo.
  echo ERROR: Docker failed. Make sure Docker Desktop is running.
  pause
  exit /b 1
)

echo Running database migrations...
docker compose -f docker-compose.local.yml exec backend alembic upgrade head
if errorlevel 1 (
  echo.
  echo ERROR: Migration failed.
  echo Data is still safe under .\data\pgdata
  pause
  exit /b 1
)

start "" "http://localhost:8080"
echo Done.