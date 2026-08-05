from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import IngestedRecord

class StorageBackend(ABC):
    @abstractmethod
    def save(self, source_name: str, records: List[Dict[str, Any]]) -> int: pass

class DatabaseStorage(StorageBackend):
    def __init__(self, db: Session): self.db = db
    def save(self, source_name: str, records: List[Dict[str, Any]]) -> int:
        count = 0
        for record in records:
            self.db.add(IngestedRecord(source_name=source_name, payload=record))
            count += 1
        self.db.commit()
        return count
      
