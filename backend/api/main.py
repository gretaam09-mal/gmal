from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routes import health, invites, profiles, roles, tenants, workspaces

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
app.include_router(roles.router)
app.include_router(tenants.router)
app.include_router(workspaces.router)
app.include_router(invites.router)
app.include_router(profiles.router)
