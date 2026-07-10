from fastapi import FastAPI

from api.routes import health

app = FastAPI(title="Provision API", version="0.1.0")

app.include_router(health.router)
