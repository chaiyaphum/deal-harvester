from fastapi import FastAPI

from card_retrieval.api.routes import router

api = FastAPI(
    title="Card Data Retrieval API",
    description="REST API for Thai bank credit card promotion data",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

api.include_router(router)
