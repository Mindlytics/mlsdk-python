from pydantic import BaseModel
from typing import Optional


# Arguments to Client() constructor
class ClientConfig(BaseModel):
    api_key: str
    server_endpoint: Optional[str] = None
    debug_level: int = 0
