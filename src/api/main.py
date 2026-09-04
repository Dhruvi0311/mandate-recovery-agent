import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.schemas import HealthResponse, ErrorResponse
from src.api.routes.mandates import router as mandates_router
from src.api.routes.recovery import router as recovery_router
from src.api.routes.agent import router as agent_router
from src.api.routes.execution import router as execution_router
from src.api.routes.batch_report import router as batch_report_router
from src.api.routes.audit import router as audit_router

logger = logging.getLogger("mandate_recovery_api")

app = FastAPI(
    title="Mandate Recovery Agent API",
    description=(
        "FastAPI orchestration layer for UPI AutoPay mandate recovery. "
        "Coordinates feature pipelines, ML predictions, deterministic policy decisions, "
        "LangGraph customer conversations, and isolated payment simulation."
    ),
    version="1.0.0"
)

# Enable CORS for local development (e.g. React frontend on vite 5173 / cra 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers for clean frontend-friendly responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "ClientError" if exc.status_code < 500 else "ServerError", "detail": exc.detail}
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled API error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError", "detail": "An unexpected server error occurred."}
    )

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """Confirms service is running and healthy."""
    return HealthResponse(status="healthy", service="mandate-recovery-agent", version="1.0.0")

# Register routes
app.include_router(mandates_router)
app.include_router(recovery_router)
app.include_router(agent_router)
app.include_router(execution_router)
app.include_router(batch_report_router)
app.include_router(audit_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
