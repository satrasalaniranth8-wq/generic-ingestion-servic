from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import requests

class PaginationStrategy(ABC):
    @abstractmethod
    def fetch_pages(self, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> List[Dict[str, Any]]: pass

class OffsetLimitPagination(PaginationStrategy):
    def __init__(self, limit: int = 20, offset_param: str = "offset", limit_param: str = "limit", data_key: Optional[str] = None):
        self.limit, self.offset_param, self.limit_param, self.data_key = limit, offset_param, limit_param, data_key

    def fetch_pages(self, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        all_records, offset = [], 0
        while True:
            current_params = {**params, self.offset_param: offset, self.limit_param: self.limit}
            response = requests.get(url, headers=headers, params=current_params)
            response.raise_for_status()
            data = response.json()
            items = data.get(self.data_key, data) if self.data_key else data
            if isinstance(items, dict): items = [items]
            if not items: break
            all_records.extend(items)
            if len(items) < self.limit: break
            offset += self.limit
        return all_records

class PageNumberPagination(PaginationStrategy):
    def __init__(self, page_param: str = "page", data_key: Optional[str] = None):
        self.page_param, self.data_key = page_param, data_key

    def fetch_pages(self, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        all_records, page = [], 1
        while True:
            current_params = {**params, self.page_param: page}
            response = requests.get(url, headers=headers, params=current_params)
            response.raise_for_status()
            data = response.json()
            items = data.get(self.data_key, data) if self.data_key else data
            if isinstance(items, dict): items = [items]
            if not items: break
            all_records.extend(items)
            page += 1
        return all_records
      
