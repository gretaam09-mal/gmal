from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app = FastAPI(title="Provision API", version="0.1.0")

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
