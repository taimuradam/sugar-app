@echo off
setlocal EnableExtensions EnableDelayedExpansion

set PROJECT=sugarapp
cd /d "%~dp0\.."

if not exist data mkdir data
if not exist data\pgdata mkdir data\pgdata
if not exist backups mkdir backups

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
docker compose -p %PROJECT% -f docker-compose.local.yml up -d --build
if errorlevel 1 (
  echo.
  echo ERROR: Docker failed to start the app.
  pause
  exit /b 1
)

echo Waiting for the app to become ready (via /api/health)...
set READY=0
for /l %%i in (1,1,120) do (
  powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
  if !ERRORLEVEL! EQU 0 (
    set READY=1
    goto ready
  )
  timeout /t 1 >NUL
)

:ready
if "%READY%" NEQ "1" (
  echo.
  echo ERROR: App did not become ready in time.
  echo Try running:
  echo   docker compose -p %PROJECT% -f docker-compose.local.yml logs -f
  pause
  exit /b 1
)

start "" "http://localhost:8081"
echo Done.