@echo off
setlocal EnableExtensions EnableDelayedExpansion

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

echo Waiting for backend to be ready...
set "READY=0"

for /L %%i in (1,1,60) do (
  docker compose -f docker-compose.local.yml exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs', timeout=2); print('ok')" >NUL 2>NUL
  if !ERRORLEVEL! EQU 0 (
    set "READY=1"
    goto :backend_ready
  )
  timeout /t 1 >NUL
)

:backend_ready
if "%READY%" NEQ "1" (
  echo.
  echo ERROR: Backend did not become ready in time.
  echo Try running:
  echo   docker compose -f docker-compose.local.yml logs -f backend
  echo.
  pause
  exit /b 1
)

start "" "http://localhost:8080"
echo Done.