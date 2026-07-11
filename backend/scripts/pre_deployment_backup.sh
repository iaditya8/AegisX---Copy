#!/bin/bash
# Pre-deployment database backup script for CRIT-07
set -e

BACKUP_DIR="./backups"
BACKUP_FILE="${BACKUP_DIR}/aegisx_pre_crit07_backup.dump"

echo "=== CRIT-07 Pre-Deployment Database Backup ==="
mkdir -p "${BACKUP_DIR}"

if command -v docker &> /dev/null && docker ps | grep -q aegisx_db; then
    echo "Creating backup from Docker container 'aegisx_db'..."
    docker exec -t aegisx_db pg_dump -U postgres -d aegisx -Fc > "${BACKUP_FILE}"
else
    echo "Docker container 'aegisx_db' not found. Attempting local pg_dump..."
    if command -v pg_dump &> /dev/null; then
        pg_dump -h localhost -U postgres -d aegisx -Fc -f "${BACKUP_FILE}"
    else
        echo "Error: pg_dump not found in system PATH. Cannot create backup."
        exit 1
    fi
fi

echo "Backup successfully created at: ${BACKUP_FILE}"
ls -lh "${BACKUP_FILE}"
