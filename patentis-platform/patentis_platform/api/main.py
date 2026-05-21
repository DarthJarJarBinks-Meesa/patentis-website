from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from patentis_platform.api.routes import (
    agents,
    analyst,
    auth_routes,
    calibration,
    enterprise,
    enterprise_training,
    health,
    landscape,
    ingestion_routes,
    prior_art_routes,
    projects,
    search,
    training,
)

app = FastAPI(
    title="Patentis Platform",
    description="Innovation intelligence — whitespace discovery for R&D teams",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth_routes.router, prefix="/api")
app.include_router(landscape.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(calibration.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(enterprise.router, prefix="/api")
app.include_router(enterprise_training.router, prefix="/api")
app.include_router(analyst.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(ingestion_routes.router, prefix="/api")
app.include_router(prior_art_routes.router, prefix="/api")
app.include_router(training.router, prefix="/api")
