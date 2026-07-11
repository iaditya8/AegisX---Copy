@echo off
echo === CRIT-07 Pre-Deployment Database Backup ===
if not exist backups mkdir backups

docker exec -t aegisx_db pg_dump -U postgres -d aegisx -Fc > backups\aegisx_pre_crit07_backup.dump 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Backup successfully created at: backups\aegisx_pre_crit07_backup.dump
    goto end
)

echo Docker container not found or failed. Attempting local pg_dump...
pg_dump -h localhost -U postgres -d aegisx -Fc -f backups\aegisx_pre_crit07_backup.dump
if %ERRORLEVEL% EQU 0 (
    echo Backup successfully created at: backups\aegisx_pre_crit07_backup.dump
) else (
    echo Error: pg_dump failed or is not installed.
    exit /b 1
)

:end
