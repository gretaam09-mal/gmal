from fastapi import FastAPI

from api.routes import health, invites, roles, tenants, workspaces

app = FastAPI(title="Provision API", version="0.1.0")

app.include_router(health.router)
app.include_router(roles.router)
app.include_router(tenants.router)
app.include_router(workspaces.router)
app.include_router(invites.router)
