@echo off
setlocal

cd /d "%~dp0\.."

mkdir data 2>NUL
mkdir data\pgdata 2>NUL
mkdir backups 2>NUL

where docker >NUL 2>NUL
if %ERRORLEVEL% NEQ 0 (
  echo Docker CLI not found. Please install Docker Desktop.
  echo Then restart this computer and try again.
  pause
  exit /b 1
)

docker info >NUL 2>NUL
if %ERRORLEVEL% NEQ 0 (
  echo Docker Desktop is installed but the Docker engine is not running.
  echo Please open Docker Desktop and wait until it says "Engine running".
  pause
  exit /b 1
)

echo Starting Sugar App (local)...
docker compose -f docker-compose.local.yml up -d --build
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo ERROR: Docker failed to start the app.
  echo Try: close Docker Desktop, reopen it, wait for "Engine running", then run again.
  pause
  exit /b 1
)

start "" "http://localhost:8080"
echo Done.