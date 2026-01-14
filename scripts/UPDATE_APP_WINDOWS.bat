@echo off
setlocal EnableExtensions EnableDelayedExpansion

set PROJECT=sugarapp
cd /d "%~dp0\.."

where docker >NUL 2>NUL
if %ERRORLEVEL% NEQ 0 (
  echo Docker CLI not found. Please install Docker Desktop.
  pause
  exit /b 1
)

docker info >NUL 2>NUL
if %ERRORLEVEL% NEQ 0 (
  echo Docker engine is not running. Open Docker Desktop and try again.
  pause
  exit /b 1
)

echo Updating Sugar App (local)...
docker compose -p %PROJECT% -f docker-compose.local.yml pull >NUL 2>NUL

docker compose -p %PROJECT% -f docker-compose.local.yml up -d --build
if errorlevel 1 (
  echo.
  echo ERROR: Docker failed during update.
  pause
  exit /b 1
)

echo Running database migrations...
docker compose -p %PROJECT% -f docker-compose.local.yml exec -T backend alembic upgrade head
if errorlevel 1 (
  echo.
  echo ERROR: Migration failed.
  echo Your data is still safe in the Docker volume.
  pause
  exit /b 1
)

start "" "http://localhost:8080"
echo Done.