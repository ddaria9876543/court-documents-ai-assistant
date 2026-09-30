from fastapi import FastAPI

from app.api.documents import router as documents_router


app = FastAPI(
    title="Court Documents Assistant",
    description="Backend for court and enforcement document processing",
    version="1.0.0"
)


app.include_router(documents_router)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Court Documents Assistant API"
    }