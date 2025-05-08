"""This module defines the data models used in the SDK."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Union

WIRE_TYPE_SESSION_STARTED = "start_session"
WIRE_TYPE_SESSION_ENDED = "end_session"
WIRE_TYPE_USER_IDENTIFY = "identify"
WIRE_TYPE_USER_ALIAS = "alias"
WIRE_TYPE_TRACK = "track"

EVENT_CONVERSATION_STARTED = "Conversation Started"
EVENT_CONVERSATION_ENDED = "Conversation Ended"
EVENT_CONVERSATION_TURN = "Conversation Turn"
EVENT_CONVERSATION_USAGE = "Conversation Usage"
EVENT_CONVERSATION_FUNCTION = "Conversation Function"


# Arguments to Client() constructor
class ClientConfig(BaseModel):
    """Configuration for the Mindlytics Client.

    Attributes:
        api_key (str): The organization API key used for authentication.
        project_id (str): The default project ID used to create sessions.
        server_endpoint (str, optional): The URL of the Mindlytics API. Defaults to the production endpoint.
        debug (bool, optional): Enable debug logging if True.
    """

    api_key: str
    project_id: str
    server_endpoint: Optional[str] = None
    debug: bool = False


# Arguments to Client().create_session() method
class SessionConfig(BaseModel):
    """Configuration for a session in the Mindlytics Client.

    Attributes:
        project_id (str): The ID of the project associated with the session.
        user_id (str, optional): The ID of the user associated with the session.
    """

    project_id: Optional[str] = None
    user_id: Optional[str] = None


class APIResponse(BaseModel):
    """Base class for API responses.

    Attributes:
        errored (bool): Indicates if the API response contains an error.
        status (str): The status of the API response.
        message (str): A message associated with the API response.
    """

    errored: bool
    status: int
    message: str


class BaseEvent(BaseModel):
    """Base class for events.

    Attributes:
        timestamp (str): The timestamp of the event.
        session_id (str): The ID of the session associated with the event.
        conversation_id (str, optional): The ID of the conversation associated with the event.
        type (str): The type of the event.
    """

    timestamp: str
    session_id: str
    conversation_id: Optional[str] = None
    type: str


class Event(BaseEvent):
    """Event class for tracking events in the session.

    Attributes:
        event (str): The name of the event to track.
        properties (dict): Additional properties associated with the event.
    """

    event: str = Field(..., min_length=1, max_length=100)
    properties: Dict[str, Union[str, bool, int, float]]


class StartSession(BaseEvent):
    """Event class for starting a session.

    Attributes:
        type (str): The type of the event. Defaults to 'start_session'.
    """

    type: str = Field(default=WIRE_TYPE_SESSION_STARTED)
    attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None


class EndSession(BaseEvent):
    """Event class for ending a session.

    Attributes:
        type (str): The type of the event. Defaults to 'end_session'.
    """

    type: str = Field(default=WIRE_TYPE_SESSION_ENDED)
    attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None


class StartConversation(BaseEvent):
    """Event class for starting a conversation.

    Attributes:
        type (str): The type of the event. Defaults to 'start_conversation'.
    """

    conversation_id: str
    type: str = Field(default=WIRE_TYPE_TRACK)
    event: str = Field(default=EVENT_CONVERSATION_STARTED)
    properties: Optional[Dict[str, Union[str, bool, int, float]]] = None


class EndConversation(BaseEvent):
    """Event class for ending a conversation.

    Attributes:
        type (str): The type of the event. Defaults to 'end_conversation'.
    """

    conversation_id: str
    type: str = Field(default=WIRE_TYPE_TRACK)
    event: str = Field(default=EVENT_CONVERSATION_ENDED)
    properties: Optional[Dict[str, Union[str, bool, int, float]]] = None
