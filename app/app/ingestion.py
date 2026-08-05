from tenacity import retry, stop_after_attempt, wait_exponential
from app.strategies.auth import AuthStrategy
from app.strategies.pagination import PaginationStrategy
from app.strategies.storage import StorageBackend
from typing import Dict, Any

class IngestionEngine:
    def __init__(self, auth: AuthStrategy, pagination: PaginationStrategy, storage: StorageBackend):
        self.auth = auth
        self.pagination = pagination
        self.storage = storage

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_with_retries(self, url: str, headers: Dict[str, str], params: Dict[str, Any]):
        return self.pagination.fetch_pages(url, headers, params)

    def run(self, source_name: str, url: str) -> int:
        headers = self.auth.get_auth_headers()
        params = self.auth.get_auth_params()
        records = self._fetch_with_retries(url, headers, params)
        return self.storage.save(source_name, records)
      
