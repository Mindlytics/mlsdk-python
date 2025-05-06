from pydantic import BaseModel
from typing import Optional


# Arguments to Client() constructor
class ClientConfig(BaseModel):
    api_key: str
    server_endpoint: Optional[str] = None
    debug: bool = False


# Arguments to Client().create_session() method
class SessionConfig(BaseModel):
    session_id: Optional[str] = None
    project_id: str
    user_id: Optional[str] = None
