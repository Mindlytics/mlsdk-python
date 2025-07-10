"""Session module for Mindlytics SDK!"""

import asyncio
import logging
from .types import (
    SessionConfig,
    ClientConfig,
    APIResponse,
    Event,
    EndSession,
    EndConversation,
    UserIdentify,
    UserAlias,
    ConversationTurn,
    ConversationUsage,
    TokenBasedCost,
    Cost,
    TurnPropertiesModel,
    MLEvent,
    FunctionPropertiesModel,
    FunctionCall,
)
from .queue import AsyncQueueWorker

from typing import Optional, List, Dict, Union, Callable, Awaitable
from .httpclient import HTTPClient
from datetime import datetime, timezone
from .ws import WS

logger = logging.getLogger(__name__)  # Use module name


def _utc_timestamp():
    """Get the current UTC timestamp in ISO format.

    Returns:
        str: The current UTC timestamp in ISO format.
    """
    return datetime.now(timezone.utc).isoformat()


class Session:
    """Session class for managing a session with the Mindlytics service.

    This class is used to manage sessions with the Mindlytics service.

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
        on_event: Optional[Callable[[MLEvent], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ) -> None:
        """Initialize the Session with the given parameters.

        Args:
            client (Client): The client instance used to communicate with the Mindlytics service.
            config (SessionConfig): The configuration for the session.
            attributes (dict, optional): Additional attributes associated with the session.
            on_event (callable, optional): A callback function to handle events.
            on_error (callable, optional): A callback function to handle errors.
        """
        self.client = client
        self.session_id = config.session_id
        self.project_id = config.project_id
        self.conversation_id = config.conversation_id
        self.id = config.id
        self.device_id = config.device_id

        if self.id is None and self.device_id is None:
            raise ValueError(
                "Either 'id' or 'device_id' must be provided in the session configuration."
            )

        self.http_client = HTTPClient(
            server_endpoint=client.server_endpoint,
            api_key=client.api_key,
            project_id=self.project_id,
            debug=client.debug,
        )
        if client.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)
        self.history: List[APIResponse] = []
        self.errors = 0
        self.on_error = on_error
        self.on_event = on_event
        self.ws = None  # type: Optional[WS]
        self.listener = None  # type: Optional[asyncio.Task[None]]
        self.seen_session_end = False

        def _queue_callback(message):
            return self._process_queue_message(message)

        self._queue_worker = AsyncQueueWorker(
            _queue_callback
        )  # type: AsyncQueueWorker | None

    async def _process_queue_message(self, message):
        logger.debug(f"Processing message: {str(message)}")
        if message.get("test") is None:
            response = await self.http_client.send_request(
                method="POST",
                url="/bc/v1/events/queue",
                data=message,
            )
            if response.get("errored", False):
                self.history.append(APIResponse.model_validate(response))
                self.errors += 1
                if self.on_error is not None:
                    await self.on_error(Exception(response.get("message")))

    async def _enqueue(self, message: dict) -> None:
        if self.on_event is not None or self.on_error is not None:
            if self.listener is None:
                await self.start_listening(
                    session_id=self.session_id,
                    on_event=self.on_event,
                    on_error=self.on_error,
                )
        if self._queue_worker is None:
            raise RuntimeError(
                "Queue worker has been flushed and is no longer available."
            )
        self._queue_worker.enqueue(message)

    async def flush(self) -> None:
        """Flush the queue worker to ensure all messages are sent.

        After calling this method, you can no longer send any messages.  The queue resources will be cleaned up.
        """
        if self._queue_worker is not None:
            await self._queue_worker.flush(final=True)
            self._queue_worker = None
        if self.on_event is not None or self.on_error is not None:
            await self.stop_listening()

    async def flush_and_continue(self) -> None:
        """Flush the queue worker to ensure all messages are sent.

        After calling this method, you can continue to send messages.  The queue resources will not be cleaned up.
        """
        if self._queue_worker is not None:
            await self._queue_worker.flush(final=False)

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
            user_id=self.id,
            device_id=self.device_id,
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            attributes=attributes or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def _send_conversation_ended(
        self,
        *,
        conversation_id: str,
        timestamp: str | None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]],
    ) -> None:
        """Send a message indicating that the conversation has ended.

        This method is a coroutine that sends a message indicating that the conversation has ended.
        """
        message = EndConversation(
            user_id=self.id,
            device_id=self.device_id,
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=conversation_id,
            properties=properties or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def end_session(
        self,
        *,
        timestamp: Optional[str] = None,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """End the session.

        This method ends the session and cleans up any resources used by the session.

        Args:
            timestamp (str, optional): The timestamp of the session end. Defaults to the current UTC timestamp.
            attributes (dict, optional): Additional attributes associated with the session.
        """
        # send the end session message
        await self._send_session_ended(timestamp=timestamp, attributes=attributes)

    def has_errors(self) -> bool:
        """Check if there are any errors in the session.

        Returns:
            bool: True if there are errors, False otherwise.
        """
        return self.errors > 0

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
        message = Event(
            user_id=self.id,
            device_id=self.device_id,
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
        id: Optional[str] = None,
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
        message = UserIdentify(
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            id=id,
            user_id=self.id,
            device_id=self.device_id,
            traits=traits or {},
        )
        await self._enqueue(message.model_dump(exclude_none=True))
        self.id = id  # Update the session ID to the identified user ID

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
        message = UserAlias(
            user_id=self.id,
            device_id=self.device_id,
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            id=id,
            previous_id=previous_id,
        )
        await self._enqueue(message.model_dump(exclude_none=True))
        self.id = id  # Update the session ID to the aliased user ID

    async def end_conversation(
        self,
        *,
        conversation_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        properties: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """End a conversation in the session.

        This method can be called directly to end a conversation.

        Args:
            conversation_id (str, optional): The ID of the conversation to end. If not provided, the current
            conversation will be used.
            timestamp (str, optional): The timestamp of the conversation. Defaults to the current UTC timestamp.
            properties (dict, optional): Additional properties associated with the conversation.
        """
        await self._send_conversation_ended(
            timestamp=timestamp,
            properties=properties,
            conversation_id=str(conversation_id or self.conversation_id),
        )

    async def track_conversation_turn(
        self,
        *,
        timestamp: Optional[str] = None,
        conversation_id: Optional[str] = None,
        user: str,
        assistant: str,
        assistant_id: Optional[str] = None,
        usage: Optional[Union[TokenBasedCost, Cost]] = None,
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
            usage (TokenBasedCost or Cost, optional): The cost associated with the conversation turn.
            properties (dict, optional): Additional properties associated with the conversation turn.
        """
        p = TurnPropertiesModel(
            user=user,
            assistant=assistant,
            assistant_id=assistant_id,
        )
        if properties:
            for k, v in properties.items():
                setattr(p, k, v)

        if usage:
            if isinstance(usage, TokenBasedCost):
                p.model = usage.model
                p.prompt_tokens = usage.prompt_tokens
                p.completion_tokens = usage.completion_tokens
            elif isinstance(usage, Cost):
                p.cost = usage.cost

        message = ConversationTurn(
            user_id=self.id,
            device_id=self.device_id,
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=str(conversation_id or self.conversation_id),
            properties=p,
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def track_conversation_usage(
        self,
        *,
        timestamp: Optional[str] = None,
        conversation_id: Optional[str] = None,
        usage: Union[TokenBasedCost, Cost],
    ) -> None:
        """Track the usage of the conversation.

        This method can be called to track the usage of the conversation.  If the session is not started, it will be
        started automatically.  If the conversation_id is not supplied, it will be used to associate the event with
        the current conversation.  If there is no current conversation, a new conversation will be started.

        Args:
            timestamp (str, optional): The timestamp of the conversation usage. Defaults to the current UTC timestamp.
            conversation_id (str, optional): The ID of the conversation associated with the event.
            usage (TokenBasedCost or Cost, optional): The cost associated with the conversation usage.
        """
        message = ConversationUsage(
            user_id=self.id,
            device_id=self.device_id,
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=str(conversation_id or self.conversation_id),
            properties=usage,
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def track_function_call(
        self,
        *,
        timestamp: Optional[str] = None,
        conversation_id: Optional[str] = None,
        name: str,
        args: Optional[str] = None,
        result: Optional[str] = None,
        runtime: Optional[int] = 0,
        properties: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """Track a function call in the conversation.

        This method can be called to track a function call in the conversation.  If the session is not started, it will
        be started automatically.  If the conversation_id is not supplied, it will be used to associate the event with
        the current conversation.  If there is no current conversation, a new conversation will be started.

        Args:
            timestamp (str, optional): The timestamp of the function call. Defaults to the current UTC timestamp.
            conversation_id (str, optional): The ID of the conversation associated with the event.
            name (str): The name of the function being called.
            args (str, optional): The arguments passed to the function call.
            result (str, optional): The result of the function call.
            runtime (int, optional): The runtime of the function call in milliseconds. Defaults to 0.
            properties (dict, optional): Additional properties associated with the function call.
        """
        p = FunctionPropertiesModel(
            name=name,
            args=args,
            result=result,
            runtime=runtime,
        )

        if properties:
            for k, v in properties.items():
                setattr(p, k, v)

        message = FunctionCall(
            user_id=self.id,
            device_id=self.device_id,
            timestamp=timestamp or _utc_timestamp(),
            session_id=str(self.session_id),
            conversation_id=str(conversation_id or self.conversation_id),
            properties=p,
        )
        await self._enqueue(message.model_dump(exclude_none=True))

    async def start_listening(
        self,
        *,
        session_id: str,
        on_event: Optional[Callable[[MLEvent], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ) -> None:
        """Start listening for events from the Mindlytics API.

        This method sets up a WebSocket connection to the Mindlytics API and listens for events.  When an event is
        received, the `on_event` callback is called with the event data.  If an error occurs, the `on_error` callback
        is called with the error.

        Args:
            session_id (str): The ID of the session to listen for events.
            on_event (callable): A callback function to handle incoming events.
            on_error (callable, optional): A callback function to handle errors.
        """
        self.ws = WS(config=self.client)
        response = await self.ws.get_authorization_token(session_id=session_id)
        if response.get("errored", False):
            # raise Exception(response.get("message"))
            self.history.append(APIResponse.model_validate(response))
            self.errors += 1
            if self.on_error is not None:
                await self.on_error(Exception(response.get("message")))
            return

        authorization_key = response.get("authorization_key")
        if authorization_key is None:
            # raise Exception("Unable to obtain authorization key")
            self.history.append(APIResponse.model_validate(response))
            self.errors += 1
            if self.on_error is not None:
                await self.on_error(Exception("Unable to obtain authorization key"))
            return

        logger.debug("Starting WebSocket listener...")

        # The following stuff is like new Promise(resolve, reject) in JS
        # It will resolve when the connection is established and the listener is started
        connected_future = asyncio.get_event_loop().create_future()

        def on_connected():
            logger.debug("WebSocket connection established")
            connected_future.set_result(True)

        async def _on_event(event: MLEvent) -> None:
            if on_event is not None:
                await on_event(event)
                if (
                    event.event == "Session Ended"
                    and event.session_id == self.session_id
                ):
                    logger.debug(
                        f"Session ended event received for session ID: {event.session_id}"
                    )
                    self.seen_session_end = True
            else:
                if (
                    event.event == "Session Ended"
                    and event.session_id == self.session_id
                ):
                    logger.debug(
                        f"Session ended event received for session ID: {event.session_id}"
                    )
                    self.seen_session_end = True

        self.listener = asyncio.create_task(
            self.ws.listen_for_events(
                authorization_key=authorization_key,
                on_event=_on_event,
                on_error=on_error,
                on_connected=on_connected,
            )
        )
        await connected_future

    async def stop_listening(self) -> None:
        """Stop listening for events from the Mindlytics API.

        This method closes the WebSocket connection to the Mindlytics API and stops listening for events.
        """
        if self.ws is not None:
            if self.listener is not None:
                # Before we stop the listener, we should make sure the Session Ended event is sent
                if not self.seen_session_end:
                    attempts = 30
                    while not self.seen_session_end and attempts > 0:
                        logger.debug(
                            f"Waiting for session end event to be sent... {attempts} attempts left"
                        )
                        await asyncio.sleep(1)
                        attempts -= 1
                if self.seen_session_end:
                    logger.debug(
                        f"Session end event sent, stopping listener for session ID: {self.session_id}"
                    )
                else:
                    logger.debug(
                        f"Session end event not sent, stopping listener for session ID: {self.session_id}"
                    )
                self.listener.cancel()
                try:
                    await self.listener
                except asyncio.CancelledError:
                    pass
                self.listener = None
            self.ws = None
