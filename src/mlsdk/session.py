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

    This class is used to create a session for a specific project and user.

    Attributes:
        client (Client): The client config containing the API key and server endpoint.
        project_id (str): The ID of the project.
        session_id (str): The ID of the session.
        user_id (str): The ID of the user.
        attributes (dict): Additional attributes associated with the session.
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
        self.session_id = str(uuid.uuid4())
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
        if self.queue is not None:
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

    async def _send_session_started(self) -> None:
        """Send a message indicating that the session has started.

        This method is a coroutine that sends a message indicating that the session has started.
        """
        message = StartSession(
            timestamp=_utc_timestamp(),
            session_id=self.session_id,
            attributes=self.attributes or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_session_ended(self) -> None:
        """Send a message indicating that the session has ended.

        This method is a coroutine that sends a message indicating that the session has ended.
        """
        message = EndSession(
            timestamp=_utc_timestamp(),
            session_id=self.session_id,
            attributes=self.attributes or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_conversation_started(
        self, properties: Optional[Dict[str, Union[str, bool, int, float]]]
    ) -> None:
        """Send a message indicating that the conversation has started.

        This method is a coroutine that sends a message indicating that the conversation has started.
        """
        if self.conversation_id is None:
            self.conversation_id = str(uuid.uuid4())

        message = StartConversation(
            timestamp=_utc_timestamp(),
            session_id=self.session_id,
            conversation_id=self.conversation_id,
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_conversation_ended(
        self, properties: Optional[Dict[str, Union[str, bool, int, float]]]
    ) -> None:
        """Send a message indicating that the conversation has ended.

        This method is a coroutine that sends a message indicating that the conversation has ended.
        """
        message = EndConversation(
            timestamp=_utc_timestamp(),
            session_id=self.session_id,
            conversation_id=str(self.conversation_id),
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def start_session(self) -> None:
        """Listen for messages from the queue.

        This method is a coroutine that listens for messages from the queue and processes them.
        """
        logger.debug(f"Starting session with ID: {self.session_id}")
        if self.queue is None:
            self.queue = asyncio.Queue()
            self.listen_task = asyncio.create_task(self.__listen__())
        await self._send_session_started()

    async def end_session(self) -> None:
        """Stop the session.

        This method stops the session and cleans up any resources used by the session.
        """
        logger.debug(f"Ending session with ID: {self.session_id}")
        if self.queue is not None:
            if self.conversation_id is not None:
                # send the end conversation message
                await self._send_conversation_ended(properties={})
            # send the end session message
            await self._send_session_ended()
            # send the terminating message
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
        """
        return self.history

    def get_errors(self) -> List[APIResponse]:
        """Return just the errored messages in history.

        Returns:
            List[APIResponse]: The history of API responses.
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
        """Track an event in the session.

        Args:
            timestamp (str, optional): The timestamp of the event. Defaults to the current UTC timestamp.
            event (str): The name of the event to track.
            conversation_id (str, optional): The ID of the conversation associated with the event.
            properties (dict, optional): Additional properties associated with the event.
        """
        if self.queue is None:
            raise RuntimeError(
                "Session is not started. Please start the session before tracking events."
            )
        message = Event(
            timestamp=timestamp or _utc_timestamp(),
            session_id=self.session_id,
            conversation_id=conversation_id or self.conversation_id,
            type="track",
            event=event,
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def start_conversation(
        self,
        *,
        properties: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> str:
        """Start a conversation in the session.

        Args:
            properties (dict, optional): Additional properties associated with the conversation.
        """
        if self.queue is None:
            raise RuntimeError(
                "Session is not started. Please start the session before starting conversations."
            )
        if self.conversation_id is None:
            self.conversation_id = str(uuid.uuid4())
        await self._send_conversation_started(properties=properties)
        return self.conversation_id

    async def end_conversation(
        self,
        *,
        properties: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """End a conversation in the session.

        Args:
            properties (dict, optional): Additional properties associated with the conversation.
        """
        if self.queue is None:
            raise RuntimeError(
                "Session is not started. Please start the session before ending conversations."
            )
        await self._send_conversation_ended(properties=properties)
        self.conversation_id = None
