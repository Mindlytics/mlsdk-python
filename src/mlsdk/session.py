"""Session module for Mindlytics SDK!"""

import asyncio
import logging
import uuid
from .types import (
    SessionConfig,
    ClientConfig,
    APIResponse,
    Event,
    StartSession,
    EndSession,
    StartConversation,
    EndConversation,
    UserIdentify,
    UserAlias,
    ConversationTurn,
    ConversationUsage,
    TokenBasedCost,
    Cost,
    TurnPropertiesModel,
)

from typing import Optional, List, Dict, Union
from .httpclient import HTTPClient
from datetime import datetime, timezone

logger = logging.getLogger(__name__)  # Use module name


def _utc_timestamp():
    """Get the current UTC timestamp in ISO format.

    Returns:
        str: The current UTC timestamp in ISO format.
    """
    return datetime.now(timezone.utc).isoformat()


class Session:
    """Session class for managing a session with the Mindlytics service.

    This class is used to manage sessions with the Mindlytics service. It provides methods
    to start and end sessions, track events, and manage conversations.

    It can be used in three different "styles".  For the most control over the session you can
    explicity call methods to start and end the session, and start and end conversations within the
    session, and send events.  Or, you can just send events and a session and/or a conversation will
    be created automatically behind the sceenes.  Finally, you can use the session as a context manager
    to automatically start and end the session when entering and exiting the context.

    This class is not intended to be instanciated directly.  Instead, you should use the `Client` class to create
    an instance of this class.

    Sending events using this sdk is asynchronous.  This means that when you call the methods on this
    object, they will return immediately.  The actual sending of the events will happen in the background.
    This is done to avoid blocking the main thread of your application.  You can use the `get_history` method
    to get the history of events that have been sent, and the `has_errors` method to check if there were any errors
    during the sending of the events.  You can also use the `get_errors` method to get a list of the errored events.
    """

    def __init__(
        self,
        *,
        client: ClientConfig,
        config: SessionConfig,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """Initialize the Session with the given parameters.

        Args:
            client (Client): The client instance used to communicate with the Mindlytics service.
            config (SessionConfig): The configuration for the session.
            attributes (dict, optional): Additional attributes associated with the session.
        """
        self.client = client
        self.session_id: str | None = None
        self.project_id = config.project_id
        self.conversation_id: str | None = None
        self.attributes = attributes
        self.user_id = config.user_id
        self.queue: Optional[asyncio.Queue] = None
        self.listen_task: Optional[asyncio.Task] = None
        self.http_client = HTTPClient(config=client, sessionConfig=config)
        if client.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)
        self.history: List[APIResponse] = []
        self.errors = 0

    async def __aenter__(self) -> "Session":
        """Enter the runtime context related to this object.

        Returns:
            Session: The session instance.
        """
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the runtime context related to this object.

        Args:
            exc_type: The exception type.
            exc_val: The exception value.
            exc_tb: The traceback object.
        """
        await self.end_session()

    async def __listen__(self) -> None:
        """Listen for messages from the queue.

        This method is a coroutine that listens for messages from the queue and processes them.
        """
        logger.debug(f"Listening for messages in session with ID: {self.session_id}")
        if self.queue is None:
            self.queue = asyncio.Queue()
        while True:
            message = await self.queue.get()
            if message is None:
                break
            # Process the message here
            logger.debug(f"Processing message: {str(message)}")
            if message.get("test") is None:
                response = await self.http_client.send_request(
                    method="POST",
                    url="/bc/v1/events/event",
                    data=message,
                )
                self.history.append(response)
                if response.errored:
                    self.errors += 1
            self.queue.task_done()
        logger.debug(
            f"Finished processing messages in session with ID: {self.session_id}"
        )
        # await self.queue.join()
        logger.debug(
            f"Queue is empty, exiting listen loop for session with ID: {self.session_id}"
        )
        self.queue = None

    async def _enqueue(self, message: dict) -> None:
        """Enqueue a message to the session.

        Args:
            message (dict): The message to enqueue.
        """
        if self.queue is not None:
            self.queue.put_nowait(message)
        else:
            raise RuntimeError(
                "Session is not started. Please start the session before enqueueing messages."
            )

    async def _send_session_started(self, timestamp: str | None) -> None:
        """Send a message indicating that the session has started.

        This method is a coroutine that sends a message indicating that the session has started.
        """
        attributes = self.attributes or {}
        if self.user_id is not None:
            if attributes.get("user_id") is None:
                attributes["user_id"] = self.user_id
        message = StartSession(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            attributes=attributes,
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_session_ended(
        self,
        *,
        timestamp: str | None,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """Send a message indicating that the session has ended.

        This method is a coroutine that sends a message indicating that the session has ended.

        Args:
            timestamp (str | None): The timestamp of the session end. Defaults to the current UTC timestamp.
            attributes (dict, optional): Additional attributes associated with the session.
        """
        message = EndSession(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            attributes=attributes or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_conversation_started(
        self,
        timestamp: str | None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """Send a message indicating that the conversation has started.

        This method is a coroutine that sends a message indicating that the conversation has started.
        """
        if self.conversation_id is None:
            self.conversation_id = str(uuid.uuid4())

        message = StartConversation(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=self.conversation_id,
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_conversation_ended(
        self,
        timestamp: str | None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """Send a message indicating that the conversation has ended.

        This method is a coroutine that sends a message indicating that the conversation has ended.
        """
        message = EndConversation(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=str(self.conversation_id),
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def start_session(
        self,
        *,
        timestamp: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> str:
        """Start the session.

        This method can be called directly to start the session.  It might also be called automatically when sending
        events if the session is not already started, or when using the session as a context manager.

        Args:
            timestamp (str, optional): The timestamp of the session start. Defaults to the current UTC timestamp.
            session_id (str, optional): The ID of the session. If not provided, a new session ID will be generated.
            project_id (str, optional): The ID of the project. If not provided, the default project ID (from Client)
                                        will be used.
            user_id (str, optional): The ID of the user, if known.
            attributes (dict, optional): Additional attributes associated with the session.

        Returns:
            str: The ID of the session.
        """
        if session_id is not None:
            self.session_id = session_id
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())
        if project_id is not None:
            self.project_id = project_id
        if user_id is not None:
            self.user_id = user_id
        if attributes is not None:
            self.attributes = attributes
        logger.debug(f"Starting session with ID: {self.session_id}")
        if self.queue is None:
            self.queue = asyncio.Queue()
            self.listen_task = asyncio.create_task(self.__listen__())
        await self._send_session_started(timestamp=timestamp)

        return self.session_id

    async def end_session(
        self,
        *,
        timestamp: Optional[str] = None,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """End the session.

        This method ends the session and cleans up any resources used by the session.
        It can be called directly or automatically when using the session as a context manager.

        Args:
            timestamp (str, optional): The timestamp of the session end. Defaults to the current UTC timestamp.
            attributes (dict, optional): Additional attributes associated with the session.
        """
        if self.session_id is not None:
            logger.debug(f"Ending session with ID: {self.session_id}")
            if self.conversation_id is not None:
                # send the end conversation message
                await self._send_conversation_ended(timestamp=timestamp, properties={})
            # send the end session message
            await self._send_session_ended(timestamp=timestamp, attributes=attributes)
            # send the terminating message
            if self.queue is not None:
                await self.queue.put(None)
        if self.listen_task is not None:
            await self.listen_task
        self.listen_task = None

    def has_errors(self) -> bool:
        """Check if there are any errors in the session.

        Returns:
            bool: True if there are errors, False otherwise.
        """
        return self.errors > 0

    def get_history(self) -> List[APIResponse]:
        """Get the history of API responses.

        Returns:
            List[APIResponse]: The history of API responses.

        Example:
            >>> await session.track_event(event="test_event_1")
            >>> await session.track_event(event="test_event_2")
            >>> await session.end_session()
            >>> history = session.get_history()
            >>> for response in history:
            ...     print(response)
            APIResponse(errored=False, status=200, message="Success")
            APIResponse(errored=False, status=200, message="Success")
        """
        return self.history

    def get_errors(self) -> List[APIResponse]:
        """Return just the errored messages in history.

        Returns:
            List[APIResponse]: The history of API responses.

        Example:
            >>> await session.track_event(event="test_event_1")
            >>> await session.track_event(event="test_event_2")
            >>> await session.end_session()
            >>> if session.has_errors():
            >>>     errors = session.get_errors()
            >>>     for response in errors:
            ...         print(response)
            APIResponse(errored=True, status=400, message="Error: 400 - Invalid wire type: undefined")
            APIResponse(errored=True, status=403, message="Error: 403 - Unauthorized: No organization
            found for given apikey: test_api_key")
        """
        return [response for response in self.history if response.errored]

    async def track_event(
        self,
        *,
        timestamp: Optional[str] = None,
        event: str,
        conversation_id: Optional[str] = None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """Track an arbitrary event in the session.

        If the timestamp is supplied, it must be in ISO format.  If the timestamp is not supplied, the current
        UTC timestamp will be used.  If the session is not started, it will be started automatically.  If the
        conversation_id is supplied, it will be used to associate the event with the conversation.  If the
        conversation_id is not supplied, and a conversation has been started, the event will be associated with
        the current conversation, otherwise it will only be associated with the session.

        Args:
            timestamp (str, optional): The timestamp of the event. Defaults to the current UTC timestamp.
            event (str): The name of the event to track.
            conversation_id (str, optional): The ID of the conversation associated with the event.
            properties (dict, optional): Additional properties associated with the event.
        """
        if self.session_id is None:
            await self.start_session()
        message = Event(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=conversation_id or self.conversation_id,
            type="track",
            event=event,
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def user_identify(
        self,
        *,
        timestamp: Optional[str] = None,
        id: str,
        traits: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """Identify a user with the given user ID and traits.

        This method sends an identify event to the Mindlytics API, associating the user ID with the specified traits.
        If the session is not started, it will be started automatically.

        Args:
            timestamp (str, optional): The timestamp of the identify event. Defaults to the current UTC timestamp.
            id (str, optional): The ID of the user to identify.
            traits (dict, optional): Additional traits associated with the user.
        """
        if self.session_id is None:
            await self.start_session()
        message = UserIdentify(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            id=id,
            traits=traits or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def user_alias(
        self,
        *,
        timestamp: Optional[str] = None,
        id: str,
        previous_id: str,
    ) -> None:
        """Alias a user with the given user ID and previous ID.

        This method sends an alias event to the Mindlytics API, associating the user ID with the specified previous ID.
        If the session is not started, it will be started automatically.

        Args:
            timestamp (str, optional): The timestamp of the alias event. Defaults to the current UTC timestamp.
            id (str, optional): The ID of the user to alias.
            previous_id (str, optional): The previous ID to associate with the user.
        """
        if self.session_id is None:
            await self.start_session()
        message = UserAlias(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            id=id,
            previous_id=previous_id,
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def start_conversation(
        self,
        *,
        timestamp: Optional[str] = None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> str:
        """Start a conversation in the session.

        If the session is not started, it will be started automatically.  If the conversation_id is not supplied, a new
        conversation_id will be generated.  This method might be called automatically when sending
        conversation-related events.

        Args:
            timestamp (str, optional): The timestamp of the conversation. Defaults to the current UTC timestamp.
            properties (dict, optional): Additional properties associated with the conversation.
        """
        if self.session_id is None:
            await self.start_session(timestamp=timestamp)
        if self.conversation_id is None:
            self.conversation_id = str(uuid.uuid4())
        await self._send_conversation_started(
            timestamp=timestamp, properties=properties
        )
        return self.conversation_id

    async def end_conversation(
        self,
        *,
        timestamp: Optional[str] = None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """End a conversation in the session.

        This method can be called directly to end the conversation.  It might also be called automatically when the
        session is ended or when using the session as a context manager.

        Args:
            timestamp (str, optional): The timestamp of the conversation. Defaults to the current UTC timestamp.
            properties (dict, optional): Additional properties associated with the conversation.
        """
        if self.session_id is not None and self.conversation_id is not None:
            await self._send_conversation_ended(
                timestamp=timestamp, properties=properties
            )
        self.conversation_id = None

    async def track_conversation_turn(
        self,
        *,
        timestamp: Optional[str] = None,
        conversation_id: Optional[str] = None,
        user: str,
        assistant: str,
        assistant_id: Optional[str] = None,
        cost: Optional[Union[TokenBasedCost, Cost]] = None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """Track a turn in the conversation.

        This method can be called to track a turn in the conversation.  If the session is not started, it will be
        started automatically.  If the conversation_id is not supplied, it will be used to associate the event with
        the current conversation.  If there is no current conversation, a new conversation will be started.

        Args:
            timestamp (str, optional): The timestamp of the conversation turn. Defaults to the current UTC timestamp.
            conversation_id (str, optional): The ID of the conversation associated with the event.
            user (str): The user input in the conversation.
            assistant (str): The assistant output in the conversation.
            assistant_id (str, optional): The ID of the assistant.
            cost (TokenBasedCost or Cost, optional): The cost associated with the conversation turn.
            properties (dict, optional): Additional properties associated with the conversation turn.
        """
        if self.session_id is None:
            await self.start_session(timestamp=timestamp)

        if conversation_id is None and self.conversation_id is None:
            self.conversation_id = await self.start_conversation(
                timestamp=timestamp, properties=properties
            )
        elif conversation_id is not None and self.conversation_id is not None:
            if conversation_id != self.conversation_id:
                raise ValueError(
                    "Conversation ID does not match the current conversation ID."
                )
        elif conversation_id is not None:
            self.conversation_id = conversation_id
            await self.start_conversation(timestamp=timestamp, properties=properties)

        p = TurnPropertiesModel(
            user=user,
            assistant=assistant,
            assistant_id=assistant_id,
            cost=cost,
            **(properties or {}),
        )
        message = ConversationTurn(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=str(self.conversation_id),
            properties=p,
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def track_conversation_usage(
        self,
        *,
        timestamp: Optional[str] = None,
        conversation_id: Optional[str] = None,
        cost: Union[TokenBasedCost, Cost],
    ) -> None:
        """Track the usage of the conversation.

        This method can be called to track the usage of the conversation.  If the session is not started, it will be
        started automatically.  If the conversation_id is not supplied, it will be used to associate the event with
        the current conversation.  If there is no current conversation, a new conversation will be started.

        Args:
            timestamp (str, optional): The timestamp of the conversation usage. Defaults to the current UTC timestamp.
            conversation_id (str, optional): The ID of the conversation associated with the event.
            cost (TokenBasedCost or Cost, optional): The cost associated with the conversation usage.
        """
        if self.session_id is None:
            await self.start_session(timestamp=timestamp)

        if conversation_id is None and self.conversation_id is None:
            self.conversation_id = await self.start_conversation(
                timestamp=timestamp, properties={}
            )
        elif conversation_id is not None and self.conversation_id is not None:
            if conversation_id != self.conversation_id:
                raise ValueError(
                    "Conversation ID does not match the current conversation ID."
                )
        elif conversation_id is not None:
            self.conversation_id = conversation_id
            await self.start_conversation(timestamp=timestamp, properties={})

        message = ConversationUsage(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=str(self.conversation_id),
            properties=cost,
        )
        await self._enqueue(message.model_dump(exclude_none=True))
