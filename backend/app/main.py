from fastapi import FastAPI

from app.models import HealthResponse

app = FastAPI(title="F1 AI Race Engineer Backend", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
