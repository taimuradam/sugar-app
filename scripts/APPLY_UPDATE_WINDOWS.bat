@echo off
setlocal EnableExtensions EnableDelayedExpansion

set PROJECT=sugarapp
cd /d "%~dp0\.."

if not exist data mkdir data
if not exist data\pgdata mkdir data\pgdata
if not exist backups mkdir backups

set ZIP=%~1
if "%ZIP%"=="" set ZIP=%CD%\update.zip

if not exist "%ZIP%" (
  echo.
  echo ERROR: update zip not found.
  echo Put your update zip here:
  echo   %CD%\update.zip
  echo Or run:
  echo   scripts\APPLY_UPDATE_WINDOWS.bat C:\path\to\update.zip
  echo.
  pause
  exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set TS=%%i
echo Creating safety backup backups\backup_%TS%.sql ...
docker compose -p %PROJECT% -f docker-compose.local.yml exec -T db pg_dump -U app -d finance > "backups\backup_%TS%.sql"
if errorlevel 1 (
  echo.
  echo ERROR: Backup failed. Is the app running?
  pause
  exit /b 1
)

echo Stopping app...
docker compose -p %PROJECT% -f docker-compose.local.yml down

set TMP=%TEMP%\sugarapp_update_%RANDOM%%RANDOM%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$zip='%ZIP%'; $tmp='%TMP%';" ^
  "New-Item -ItemType Directory -Force $tmp | Out-Null;" ^
  "Expand-Archive -Force $zip $tmp;" ^
  "$items=Get-ChildItem $tmp;" ^
  "if($items.Count -eq 1 -and $items[0].PSIsContainer){ $src=$items[0].FullName } else { $src=$tmp }" ^
  "robocopy $src '%CD%' /E /XD backups data .git .venv __MACOSX /NFL /NDL /NJH /NJS /NP; " ^
  "if($LASTEXITCODE -ge 8){ exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo.
  echo ERROR: Applying update failed.
  echo Your backup is here: backups\backup_%TS%.sql
  pause
  exit /b 1
)

echo Rebuilding and starting updated app...
docker compose -p %PROJECT% -f docker-compose.local.yml up -d --build
if errorlevel 1 (
  echo.
  echo ERROR: Docker failed after applying update.
  pause
  exit /b 1
)

echo Running database migrations...
docker compose -p %PROJECT% -f docker-compose.local.yml exec -T backend alembic upgrade head

start "" "http://localhost:8080"
echo Update complete.