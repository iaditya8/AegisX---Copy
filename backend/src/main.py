import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.api.v1.routers.alerts import router as alerts_router
from src.api.v1.routers.assets import router as assets_router
from src.api.v1.routers.auth import router as auth_router
from src.api.v1.routers.copilot import router as copilot_router
from src.api.v1.routers.correlations import router as correlations_router
from src.api.v1.routers.findings import router as findings_router
from src.api.v1.routers.governance import router as governance_router
from src.api.v1.routers.health import router as health_router
from src.api.v1.routers.incidents import router as incidents_router
from src.api.v1.routers.cases import router as cases_router
from src.api.v1.routers.detections import router as detections_router
from src.api.v1.routers.threat_intelligence import router as threat_intelligence_router
from src.api.v1.routers.hunts import router as hunts_router
from src.api.v1.routers.monitoring import router as monitoring_router
from src.api.v1.routers.purple_team import router as purple_team_router
from src.api.v1.routers.exposures import router as exposures_router
from src.api.v1.routers.security_posture import router as security_posture_router
from src.api.v1.routers.control_validation import router as control_validation_router
from src.api.v1.routers.security_program import router as security_program_router
from src.api.v1.routers.executive_reporting import router as executive_reporting_router
from src.api.v1.routers.cyber_resilience import router as cyber_resilience_router
from src.api.v1.routers.security_operations_analytics import router as security_operations_analytics_router
from src.api.v1.routers.cyber_risk_quantification import router as cyber_risk_quantification_router
from src.api.v1.routers.plugins import router as plugins_router
from src.api.v1.routers.recommendations import router as recommendations_router
from src.api.v1.routers.remediations import router as remediations_router
from src.api.v1.routers.reports import router as reports_router
from src.api.v1.routers.scan_runs import router as scan_runs_router
from src.api.v1.routers.scopes import router as scopes_router
from src.api.v1.routers.users import router as users_router
from src.api.v1.routers.workflows import router as workflows_router
from src.core.config import settings
from src.core.logging import setup_logging
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Configure logging based on environment (development/production)
setup_logging(settings.ENVIRONMENT)

# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register health check router (includes root-level /healthz and /readyz)
app.include_router(health_router)

# Register versioned API routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(scopes_router, prefix=settings.API_V1_STR)
app.include_router(assets_router, prefix=settings.API_V1_STR)
app.include_router(findings_router, prefix=settings.API_V1_STR)
app.include_router(workflows_router, prefix=settings.API_V1_STR)
app.include_router(scan_runs_router, prefix=settings.API_V1_STR)
app.include_router(plugins_router, prefix=settings.API_V1_STR)
app.include_router(correlations_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(copilot_router, prefix=settings.API_V1_STR)
app.include_router(recommendations_router, prefix=settings.API_V1_STR)
app.include_router(remediations_router, prefix=settings.API_V1_STR)
app.include_router(governance_router, prefix=settings.API_V1_STR)
app.include_router(monitoring_router, prefix=settings.API_V1_STR)
app.include_router(alerts_router, prefix=settings.API_V1_STR)
app.include_router(incidents_router, prefix=settings.API_V1_STR)
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(detections_router, prefix=settings.API_V1_STR)
app.include_router(threat_intelligence_router, prefix=settings.API_V1_STR)
app.include_router(hunts_router, prefix=settings.API_V1_STR)
app.include_router(purple_team_router, prefix=settings.API_V1_STR)
app.include_router(exposures_router, prefix=settings.API_V1_STR)
app.include_router(security_posture_router, prefix=settings.API_V1_STR)
app.include_router(control_validation_router, prefix=settings.API_V1_STR)
app.include_router(security_program_router, prefix=settings.API_V1_STR)
app.include_router(executive_reporting_router, prefix=settings.API_V1_STR)
app.include_router(cyber_resilience_router, prefix=settings.API_V1_STR)
app.include_router(security_operations_analytics_router, prefix=settings.API_V1_STR)
app.include_router(cyber_risk_quantification_router, prefix=settings.API_V1_STR)


# Global Exception Handlers for standardizing error shapes
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.error(f"HTTPException [{trace_id}]: {exc.detail}")

    code = (
        "unauthorized"
        if exc.status_code == 401
        else (
            "forbidden"
            if exc.status_code == 403
            else (
                "not_found"
                if exc.status_code == 404
                else "conflict" if exc.status_code == 409 else "error"
            )
        )
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail,
                "details": {},
                "trace_id": trace_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.error(f"Validation error [{trace_id}]: {exc.errors()}")

    details = {}
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", []))
        details[loc] = error.get("msg", "Validation error")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "invalid_input",
                "message": "Request validation failed",
                "details": details,
                "trace_id": trace_id,
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.error(f"Unhandled exception [{trace_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected server error occurred",
                "details": {},
                "trace_id": trace_id,
            }
        },
    )
