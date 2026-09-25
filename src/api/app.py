"""
Main FastAPI Application Factory for Sovereign On-Premise Agentic AI Workbench.
Configures CORS, middlewares, exception handlers, security, and API route endpoints.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from src.api.middleware.exception_handler import register_exception_handlers
from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.middleware.timing import TimingMiddleware
from src.security import SecurityHeadersMiddleware
from src.deployment import ReadinessChecker

from src.api.routes.agent import router as agent_router
from src.api.routes.agent_tasks import router as agent_tasks_router
from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.documents import router as documents_router
from src.api.routes.health import router as health_router
from src.api.routes.metrics import router as metrics_router
from src.api.routes.models import router as models_router
from src.api.routes.ocr import router as ocr_router
from src.api.routes.operator import router as operator_router
from src.api.routes.rag import router as rag_router
from src.api.routes.router import router as router_info_router
from src.api.routes.security import router as security_router
from src.api.routes.telemetry import router as telemetry_router
from src.api.routes.ui import router as ui_router
from src.api.routes.workbench import router as workbench_router
from src.api.responses.standard_response import StandardResponse, success_response
from src.schemas.deployment import ReadinessResponse
from src.agents.recovery import RecoveryManager
from src.persistence.database import get_db_manager


def create_app() -> FastAPI:
    """
    Construct and configure production-ready FastAPI application instance.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Sovereign On-Premise Agentic AI Workbench REST API featuring Intelligent Local Model Router.",
        version=settings.WORKBENCH_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @app.on_event("startup")
    async def on_startup():
        """FastAPI startup lifecycle hook: initializes database, processes recovery, and validates offline posture."""
        if getattr(settings, "OFFLINE_VALIDATION_ENABLED", True):
            from src.security.startup_validator import StartupValidator
            validator = StartupValidator()
            validator.run_startup_validation()

        if settings.AGENT_PERSISTENCE_ENABLED:
            db_mgr = get_db_manager()
            db_mgr.initialize_database()
            if settings.AGENT_RECOVERY_ENABLED:
                rec_mgr = RecoveryManager()
                rec_mgr.process_startup_recovery()

        # Knowledge Base Startup Check & Auto-Ingestion
        try:
            from src.rag.ingest_mrpl import MRPLKnowledgeBaseIngester
            ingester = MRPLKnowledgeBaseIngester()
            ingester.ingest(force=False)
        except Exception as kb_err:
            import logging
            logging.getLogger("MRPL.Startup").warning(f"KB startup check notice: {kb_err}")

    # Configure CORS Middleware (Restrictive for production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Custom Middlewares
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Register Exception Handlers
    register_exception_handlers(app)

    # Register API Route Endpoints
    app.include_router(ui_router)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(operator_router)
    app.include_router(security_router)
    app.include_router(metrics_router)
    app.include_router(models_router)
    app.include_router(router_info_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(rag_router)
    app.include_router(ocr_router)
    app.include_router(workbench_router)
    app.include_router(agent_router)
    app.include_router(agent_tasks_router)
    app.include_router(telemetry_router)

    # Mount Local Static Assets Directory
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    # Production Deployment Readiness & Liveness Endpoints
    @app.get("/live", response_model=StandardResponse[dict], tags=["System Health"])
    async def liveness_probe():
        """Liveness probe: verifies API process is alive."""
        return success_response(
            data={"status": "alive", "workbench_version": settings.WORKBENCH_VERSION},
            message="Process is alive",
        )

    @app.get("/ready", response_model=StandardResponse[ReadinessResponse], tags=["System Health"])
    async def readiness_probe():
        """Readiness probe: verifies system capability to accept production traffic."""
        checker = ReadinessChecker()
        assessment = checker.readiness_check()
        resp = ReadinessResponse(**assessment)
        return success_response(
            data=resp,
            message=f"System readiness status: {assessment['status']}",
        )

    return app


# Application Singleton Instance
app = create_app()
