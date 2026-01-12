@echo off
setlocal
cd /d "%~dp0\.."
if not exist backups mkdir backups

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set TS=%%i

echo Creating backup backups\backup_%TS%.sql ...
docker compose -f docker-compose.local.yml exec -T db pg_dump -U app finance > "backups\backup_%TS%.sql"
if errorlevel 1 (
  echo.
  echo ERROR: Backup failed. Is the app running?
  pause
  exit /b 1
)
echo Backup complete: backups\backup_%TS%.sql
