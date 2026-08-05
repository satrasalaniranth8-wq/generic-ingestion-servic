from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app.strategies.auth import NoAuthStrategy, BearerAuthStrategy
from app.strategies.pagination import OffsetLimitPagination, PageNumberPagination
from app.strategies.storage import DatabaseStorage
from app.ingestion import IngestionEngine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Generic Data Ingestion Service", version="1.0.0")

class IngestionRequest(BaseModel):
    source_name: str
    url: str
    auth_type: str = "none"
    token: str | None = None
    pagination_type: str = "offset"
    limit: int = 20
    data_key: str | None = None

@app.post("/ingest")
def trigger_ingestion(payload: IngestionRequest, db: Session = Depends(get_db)):
    try:
        auth = BearerAuthStrategy(payload.token) if payload.auth_type == "bearer" and payload.token else NoAuthStrategy()
        pagination = PageNumberPagination(data_key=payload.data_key) if payload.pagination_type == "page" else OffsetLimitPagination(limit=payload.limit, data_key=payload.data_key)
        storage = DatabaseStorage(db)
        engine_runner = IngestionEngine(auth=auth, pagination=pagination, storage=storage)
        count = engine_runner.run(payload.source_name, payload.url)
        return {"status": "success", "source": payload.source_name, "records_ingested": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
      
