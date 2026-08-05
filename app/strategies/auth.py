from abc import ABC, abstractmethod
from typing import Dict

class AuthStrategy(ABC):
    @abstractmethod
    def get_auth_headers(self) -> Dict[str, str]: pass
    @abstractmethod
    def get_auth_params(self) -> Dict[str, str]: pass

class NoAuthStrategy(AuthStrategy):
    def get_auth_headers(self): return {}
    def get_auth_params(self): return {}

class BearerAuthStrategy(AuthStrategy):
    def __init__(self, token: str): self.token = token
    def get_auth_headers(self): return {"Authorization": f"Bearer {self.token}"}
    def get_auth_params(self): return {}
      
