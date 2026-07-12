# AegisX Runtime Evidence Pack
## Live Execution Logs, API Payloads, and Database Verification Outputs

This pack contains the raw evidence collected during the production readiness audit of the AegisX platform on July 11, 2026.

---

## 1. Container & Infrastructure Status

### 1.1 Docker Compose Process Verification
```powershell
PS C:\Users\Aditya\Desktop\AegisX - Copy> docker compose ps
NAME            IMAGE             COMMAND                  SERVICE   CREATED       STATUS                 PORTS
aegisx_api      aegisx-copy-api   "uvicorn src.main:ap…"   api       7 hours ago   Up 4 minutes           0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
aegisx_db       postgres:15-alpine "docker-entrypoint.s…"   db        7 hours ago   Up 4 minutes (healthy)  0.0.0.0:5432->5432/tcp
aegisx_redis    redis:7-alpine    "docker-entrypoint.s…"   redis     7 hours ago   Up 4 minutes (healthy)  0.0.0.0:6379->6379/tcp
aegisx_worker   aegisx-copy-api   "celery -A src.infras…"  worker    7 hours ago   Up 4 minutes           
```

### 1.2 Alembic Migration Verification
Database head version retrieved directly from the `alembic_version` table:
```
version_num  
--------------
 a9b8c7d6e5f4
(1 row)
```

---

## 2. API Contract Payloads

### 2.1 Authentication & Tokens
* **Request (Invalid Credentials):**
  * `POST http://localhost:8000/api/v1/auth/token`
  * Body: `{"username": "admin", "password": "wrong_password"}`
* **Response (401 Unauthorized):**
  ```json
  {
    "error": {
      "code": "unauthorized",
      "message": "Incorrect username or password",
      "details": {},
      "trace_id": "166661d7-5a36-4d82-b71a-72c9dbf80c8a"
    }
  }
  ```

* **Request (Valid Login):**
  * `POST http://localhost:8000/api/v1/auth/token`
  * Body: `{"username": "admin_user", "password": "admin_password"}`
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 1800,
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "meta": {},
    "trace_id": null
  }
  ```

---

## 3. Scope & Asset Creation Payloads

### 3.1 Scope Creation (Operator Role)
* **Request:**
  * `POST http://localhost:8000/api/v1/scopes`
  * Headers: `Authorization: Bearer <JWT_TOKEN>`
  * Body:
    ```json
    {
      "name": "Audit Target Scope",
      "definition": {
        "targets": ["audit.target.local"]
      }
    }
    ```
* **Response (201 Created):**
  ```json
  {
    "success": true,
    "data": {
      "id": "77ed31fb-540a-410c-a644-2a20ff1bf9a7",
      "name": "Audit Target Scope",
      "definition": {
        "targets": ["audit.target.local"]
      }
    }
  }
  ```

### 3.2 Asset Details Retrieval
* **Request:**
  * `GET http://localhost:8000/api/v1/assets/dcfa9cf7-7c04-425c-aa69-6f381259dcb3`
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "dcfa9cf7-7c04-425c-aa69-6f381259dcb3",
      "scope_id": "77ed31fb-540a-410c-a644-2a20ff1bf9a7",
      "host": "audit.target.local",
      "ip": "192.168.5.10",
      "asset_type": "domain",
      "metadata_json": {},
      "first_seen": "2026-07-11T21:11:16.476937Z",
      "last_seen": "2026-07-11T21:11:16.476937Z",
      "fingerprint": "61272203-562f-4e43-ba91-9ec9d73738b9",
      "deleted_at": null,
      "deleted_by": null
    },
    "meta": {},
    "trace_id": null
  }
  ```

---

## 4. Triage & Incident Ingest Payloads

### 4.1 Finding Acknowledgment
* **Request:**
  * `POST http://localhost:8000/api/v1/findings/cc003325-4fa1-4073-b537-b91856b2dd27/ack`
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "cc003325-4fa1-4073-b537-b91856b2dd27",
      "status": "acknowledged",
      "updated_at": "2026-07-11T21:11:20.872169Z"
    }
  }
  ```

### 4.2 Incident Creation
* **Request:**
  * `POST http://localhost:8000/api/v1/incidents`
  * Body:
    ```json
    {
      "title": "Critical Data Leakage Incident",
      "description": "Unauthorized data transfer to external server.",
      "severity": "critical",
      "alert_ids": ["76b1890e-dc1b-486f-bcd8-3259c354f8ce"],
      "asset_ids": ["dcfa9cf7-7c04-425c-aa69-6f381259dcb3"],
      "finding_ids": ["cc003325-4fa1-4073-b537-b91856b2dd27"]
    }
    ```
* **Response (201 Created):**
  ```json
  {
    "incident_id": "e43d079e-f26a-43c7-845b-60ec6ca2166e",
    "incident_fingerprint": "4163a88e-dec3-4ff4-9905-67877de1c756",
    "title": "Critical Data Leakage Incident",
    "description": "Unauthorized data transfer to external server.",
    "severity": "CRITICAL",
    "status": "OPEN",
    "owner": null,
    "created_at": "2026-07-11T21:11:21.434585Z",
    "updated_at": "2026-07-11T21:11:21.434589Z",
    "alert_ids": ["76b1890e-dc1b-486f-bcd8-3259c354f8ce"],
    "asset_ids": ["dcfa9cf7-7c04-425c-aa69-6f381259dcb3"],
    "finding_ids": ["cc003325-4fa1-4073-b537-b91856b2dd27"],
    "recommendation_ids": [],
    "remediation_ids": []
  }
  ```

---

## 5. Database Verification Evidence

### 5.1 Asset Column verification after update
```
host            |      ip      
----------------------------+--------------
 audit.target-updated.local | 192.168.5.11
(1 row)
```

### 5.2 Celery Worker execution logging (workflow events count in DB)
```
count 
-------
    45
(1 row)
```
