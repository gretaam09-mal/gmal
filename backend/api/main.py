from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import get_settings
from api.routes import (
    admin_error_register,
    admin_instruments,
    admin_metrics,
    analyses,
    exports,
    health,
    invites,
    me,
    memos,
    profiles,
    roles,
    tenants,
    workspaces,
)
from services.composition.provider import CompositionError
from services.diff_note.provider import DiffNoteError
from services.exports.pdf import PdfRenderingError
from services.extraction.provider import ExtractionError
from services.predicate_assist.provider import PredicateAssistError

app = FastAPI(title="Provision API", version="0.1.0")


async def _external_dependency_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Backstop for errors raised by something this service depends on
    but doesn't control — an AI provider (a route's own try/except, see
    api/routes/admin_instruments.py, memos.py, catches these when the
    call itself fails; this handler is for the case that try/except
    can't reach: the provider raising during FastAPI's dependency
    resolution, e.g. AnthropicExtractionProvider.__init__ raising
    ExtractionNotConfiguredError because PROVISION_ANTHROPIC_API_KEY
    isn't set, before any route body — or try/except — ever runs) or
    headless Chromium for PDF export (PdfRenderingError, raised when the
    browser binary isn't installed in this environment). Without this,
    either surfaces as an opaque 500 instead of a clear, actionable
    message."""
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


for _error_cls in (
    ExtractionError,
    CompositionError,
    PredicateAssistError,
    DiffNoteError,
    PdfRenderingError,
):
    app.add_exception_handler(_error_cls, _external_dependency_error_handler)

app.add_middleware(
    CORSMiddleware,
    # No cookies cross-origin — auth is a bearer token in the Authorization
    # header, so allow_credentials=False is correct (and required to pair
    # with a "*" origin list, which browsers reject alongside credentials).
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(me.router)
app.include_router(roles.router)
app.include_router(tenants.router)
app.include_router(workspaces.router)
app.include_router(invites.router)
app.include_router(profiles.router)
app.include_router(analyses.router)
app.include_router(memos.router)
app.include_router(exports.router)
app.include_router(admin_instruments.router)
app.include_router(admin_metrics.router)
app.include_router(admin_error_register.router)
