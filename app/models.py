from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime
from app.database import Base

class IngestedRecord(Base):
    __tablename__ = "ingested_records"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_name = Column(String, index=True)
    payload = Column(JSON)
    ingested_at = Column(DateTime, default=datetime.utcnow)
