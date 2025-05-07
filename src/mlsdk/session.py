"""Session module for Mindlytics SDK!"""

import asyncio
import logging
import uuid
from .types import SessionConfig, ClientConfig
from typing import Optional

logger = logging.getLogger(__name__)  # Use module name


class Session:
    """Session class for managing a session with the Mindlytics service.

    This class is used to create a session for a specific project and user.

    Attributes:
        client (Client): The client config containing the API key and server endpoint.
        project_id (str): The ID of the project.
        session_id (str): The ID of the session.
        user_id (str): The ID of the user.
    """

    def __init__(self, *, client: ClientConfig, config: SessionConfig) -> None:
        """Initialize the Session with the given parameters.

        Args:
            client (Client): The client instance used to communicate with the Mindlytics service.
            config (SessionConfig): The configuration for the session.
        """
        self.client = client
        self.project_id = config.project_id
        self.session_id = config.session_id
        self.user_id = config.user_id
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())
        self.queue: Optional[asyncio.Queue] = None
        self.listen_task: Optional[asyncio.Task] = None
        if client.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

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
            self.queue.task_done()
        logger.debug(
            f"Finished processing messages in session with ID: {self.session_id}"
        )
        # await self.queue.join()
        logger.debug(
            f"Queue is empty, exiting listen loop for session with ID: {self.session_id}"
        )
        self.queue = None

    async def start_session(self) -> None:
        """Listen for messages from the queue.

        This method is a coroutine that listens for messages from the queue and processes them.
        """
        logger.debug(f"Starting session with ID: {self.session_id}")
        if self.queue is None:
            self.queue = asyncio.Queue()
            self.listen_task = asyncio.create_task(self.__listen__())

    async def end_session(self) -> None:
        """Stop the session.

        This method stops the session and cleans up any resources used by the session.
        """
        logger.debug(f"Ending session with ID: {self.session_id}")
        if self.queue is not None:
            await self.queue.put(None)
        if self.listen_task is not None:
            await self.listen_task
        self.listen_task = None

    async def enqueue(self, message: dict) -> None:
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
