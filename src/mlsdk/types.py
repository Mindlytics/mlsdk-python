"""This module defines the data models used in the SDK."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Union, Any

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
        id (str, optional): The ID of the user associated with the session.
    """

    project_id: Optional[str] = None
    id: Optional[str] = None
    device_id: Optional[str] = None

    @model_validator(mode="after")
    def check_id_or_device_id(self):
        """Validate that either id or device_id (or both) is provided."""
        if self.id is None and self.device_id is None:
            raise ValueError("Either 'id' or 'device_id' must be provided")
        return self


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
    id: Optional[str] = Field(None, min_length=1, max_length=100)
    device_id: Optional[str] = Field(None, min_length=1, max_length=100)
    attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None

    @model_validator(mode="after")
    def check_id_or_device_id(self):
        """Validate that either id or device_id (or both) is provided."""
        if self.id is None and self.device_id is None:
            raise ValueError("Either 'id' or 'device_id' must be provided")
        return self


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


class UserIdentify(BaseEvent):
    """Event class for identifying a user.

    Attributes:
        type (str): The type of the event. Defaults to 'identify'.
    """

    type: str = Field(default=WIRE_TYPE_USER_IDENTIFY)
    traits: Optional[Dict[str, Union[str, bool, int, float]]] = None
    id: Optional[str] = Field(None, min_length=1, max_length=100)
    device_id: Optional[str] = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_id_or_device_id(self):
        """Validate that either id or device_id (or both) is provided."""
        if self.id is None and self.device_id is None:
            raise ValueError("Either 'id' or 'device_id' must be provided")
        return self

    model_config = {
        "json_schema_extra": {
            "description": "The event that identifies a user - requires either id or device_id (or both)"
        }
    }


class UserAlias(BaseEvent):
    """Event class for aliasing a user.

    Attributes:
        type (str): The type of the event. Defaults to 'alias'.
    """

    type: str = Field(default=WIRE_TYPE_USER_ALIAS)
    id: str = Field(..., min_length=1, max_length=100)
    previous_id: str = Field(..., min_length=1, max_length=100)


class TokenBasedCost(BaseModel):
    """Common models have costs that are provided by a service on the web.

    If you are using one of these models, you can provide the model name and the
    number of tokens in the prompt and completion, and the cost will be calculated for you.
    """

    model: str = Field(..., min_length=1, max_length=100)
    prompt_tokens: int
    completion_tokens: int


class Cost(BaseModel):
    """If you know the cost of a conversation turn, you can provide it directly.

    This will be accumulated in the conversation analysis.
    """

    cost: float


class TurnPropertiesModel(BaseModel):
    """Properties associated with a turn in a conversation."""

    user: str = Field(..., min_length=1, max_length=100)
    assistant: str = Field(..., min_length=1, max_length=100)
    assistant_id: Optional[str | None] = None
    usage: Optional[Union[TokenBasedCost, Cost]] = None

    # This enables additional properties of various types
    model_config = {"extra": "allow"}  # Allows additional fields beyond defined ones

    # Custom validator to ensure additional fields are string, number, or boolean
    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation to ensure additional fields are of the correct type."""
        for field_name, value in self.__dict__.items():
            if field_name not in ("user", "assistant", "assistant_id", "usage"):
                if not isinstance(value, (str, int, float, bool)):
                    raise ValueError(
                        f"Field '{field_name}' must be a string, number, or boolean, got {type(value).__name__}"
                    )


class ConversationTurn(BaseEvent):
    """Event class for a turn in a conversation.

    Attributes:
        type (str): The type of the event. Defaults to 'turn'.
        properties (TurnPropertiesModel): The properties associated with the turn.
    """

    type: str = Field(default=WIRE_TYPE_TRACK)
    event: str = Field(default=EVENT_CONVERSATION_TURN)
    properties: TurnPropertiesModel
    conversation_id: str


class ConversationUsage(BaseEvent):
    """Event class for usage in a conversation.

    Attributes:
        type (str): The type of the event. Defaults to 'usage'.
        properties (TurnPropertiesModel): The properties associated with the usage.
    """

    type: str = Field(default=WIRE_TYPE_TRACK)
    event: str = Field(default=EVENT_CONVERSATION_USAGE)
    properties: Union[TokenBasedCost, Cost]
    conversation_id: str
