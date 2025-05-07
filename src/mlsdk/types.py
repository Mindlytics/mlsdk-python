"""This module defines the data models used in the SDK."""

from pydantic import BaseModel
from typing import Optional


# Arguments to Client() constructor
class ClientConfig(BaseModel):
    """Configuration for the Mindlytics Client.

    Attributes:
        api_key (str): The organization API key used for authentication.
        server_endpoint (str, optional): The URL of the Mindlytics API. Defaults to the production endpoint.
        debug (bool, optional): Enable debug logging if True.
    """

    api_key: str
    server_endpoint: Optional[str] = None
    debug: bool = False


# Arguments to Client().create_session() method
class SessionConfig(BaseModel):
    """Configuration for a session in the Mindlytics Client.

    Attributes:
        session_id (str, optional): The ID of the session. If not provided, a new session ID will be generated.
        project_id (str): The ID of the project associated with the session.
        user_id (str, optional): The ID of the user associated with the session.
    """

    session_id: Optional[str] = None
    project_id: str
    user_id: Optional[str] = None
