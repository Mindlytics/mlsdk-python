"""Client module for Mindlytics SDK."""

import asyncio
from typing import Optional, Dict, Union, Callable, Any, Awaitable
import logging
import os
import re
from .types import ClientConfig, SessionConfig, MLEvent
from .session import Session
from .httpclient import HTTPClient
from .ws import WS

logger = logging.getLogger(__name__)  # Use module name


class Client:
    """Client for communicating with the Mindlytics service.

    This class provides the main interface for interacting with the Mindlytics API.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        server_endpoint: Optional[str] = None,
        wss_endpoint: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        """Initialize the Client with the given parameters.

        This method sets up the client configuration, including the API key.  It requires the project_id to be set,
        which is used to create sessions, although it is possible to override this on a per-session basis.

        The server endpoint can be specified, and debug logging can be enabled.  When logging is enabled,
        logging-style messages will be printed to the console.

        Once you have an instance of this class, you can create sessions using the `create_session` method.

        Args:
            api_key (str, optional): The organization API key used for authentication.
            project_id (str, optional): The default project ID used to create sessions.
            server_endpoint (str, optional): The URL of the Mindlytics API. Defaults to the production endpoint.
            wss_endpoint (str, optional): The URL of the Mindlytics WebSocket API. Defaults to the production endpoint.
            debug (bool, optional): Enable debug logging if True.
        """
        if api_key is None and os.getenv("MLSDK_API_KEY") is None:
            raise ValueError(
                "API key must be provided either as an argument or through the environment variable 'MLSDK_API_KEY'"
            )
        if project_id is None and os.getenv("MLSDK_PROJECT_ID") is None:
            raise ValueError(
                "Project ID must be provided either as an argument or through the environment variable 'MLSDK_PROJECT_ID'"
            )

        ep = (
            server_endpoint
            or os.getenv("MLSDK_SERVER_BASE")
            or "https://app.mindlytics.ai"
        )
        ws = wss_endpoint
        if ws is None:
            ws = re.sub(r"^http", "ws", ep)
            ws = re.sub(r"//app", "wss", ws)
            # to handle localhost
            ws = re.sub(r":300", ":400", ws)

        config = ClientConfig(
            api_key=str(api_key or os.getenv("MLSDK_API_KEY")),
            project_id=str(project_id or os.getenv("MLSDK_PROJECT_ID")),
            server_endpoint=ep,
            wss_endpoint=ws,
            debug=debug,
        )
        self.config = config
        self.api_key = config.api_key
        self.server_endpoint = config.server_endpoint
        self.wss_endpoint = wss_endpoint
        self.debug = config.debug
        self.ws = None  # type: Optional[WS]
        self.listener = None  # type: Optional[asyncio.Task[None]]
        if self.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

        logger.debug(f"Client initialized with server endpoint: {self.server_endpoint}")

    def create_session(
        self,
        *,
        id: Optional[str] = None,
        device_id: Optional[str] = None,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
        on_event: Optional[Callable[[MLEvent], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ) -> Session:
        """Create a new session with the given parameters.

        This method creates a new session object that can be used to send events to the Mindlytics API.  The project_id
        and id can be specified, but if not provided,  the default project_id from the client configuration will
        be used.  Pass a id to associate the session with a specific user if you know the user.

        Args:
            id (str, optional): The ID of the user.
            device_id (str, optional): The device ID associated with the user.
            attributes (dict, optional): A dictionary of attributes associated with the session.
            on_event (callable, optional): A callback function to handle incoming events.
            on_error (callable, optional): A callback function to handle errors.

        Returns:
            Session: A new session object.
        """
        config = SessionConfig(
            project_id=self.config.project_id,
            id=id,
            device_id=device_id,
        )
        return Session(
            client=self.config,
            config=config,
            attributes=attributes,
            on_event=on_event,
            on_error=on_error,
        )

    async def user_identify(
        self,
        *,
        id: Optional[str] = None,
        device_id: Optional[str] = None,
        traits: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    ) -> None:
        """Identify a user with the given user ID and traits.

        This method sends an identify event to the Mindlytics API, associating the user ID with the specified traits.
        The traits can include various attributes of the user.

        If the given user id is known on the server, the traits will be merged into the existing user profile.
        If the user id is not known, a new user profile will be created with the given traits.

        Use this method when there is no associated session in progress.  If a session is in progress when
        the user is identified use the session.user_identify() method instead.

        Args:
            id (str): The ID of the user to identify.
            device_id (str): The device ID associated with the user.
            traits (dict, optional): A dictionary of traits associated with the user.
        """
        client = HTTPClient(
            server_endpoint=self.server_endpoint,
            api_key=self.api_key,
            project_id=self.config.project_id,
            debug=self.debug,
        )

        data: Dict[str, Any] = {}
        if id is not None:
            data["id"] = id
        if device_id is not None:
            data["device_id"] = device_id
        if traits is not None:
            traits_dict = {}
            for key, value in traits.items():
                if isinstance(value, (str, bool, int, float)):
                    traits_dict[key] = value
                else:
                    logger.warning(
                        f"Invalid type for trait '{key}': {type(value)}. "
                        "Only str, bool, int, and float are allowed."
                    )
                    continue
            data["traits"] = traits_dict
        response = await client.send_request(
            method="POST",
            url="/bc/v1/user/identify",
            data=data,
        )
        if response.get("errored", False):
            raise Exception(f"Error identifying user: {response.get('message')}")
        if id is not None:
            logger.debug(f"User identified: {id} with traits: {traits}")
        else:
            logger.debug(
                f"User identified with device ID: {device_id} and traits: {traits}"
            )

    async def user_alias(
        self,
        *,
        id: str,
        previous_id: str,
    ) -> None:
        """Alias a user with the given user ID and previous ID.

        This method sends an alias event to the Mindlytics API, associating the user ID with the specified previous ID.
        The previous ID can be used to link different identifiers for the same user.  This is useful when a user
        changes their identifier or when you want to merge multiple identifiers into one.

        Use this method when there is no associated session in progress.  If a session is in progress when the user
        is aliased use the session.user_alias() method instead.

        Args:
            id (str): The ID of the user to alias.
            previous_id (str): The previous ID to associate with the user.
        """
        client = HTTPClient(
            server_endpoint=self.server_endpoint,
            api_key=self.api_key,
            project_id=self.config.project_id,
            debug=self.debug,
        )
        data = {
            "id": id,
            "previous_id": previous_id,
        }
        response = await client.send_request(
            method="POST",
            url="/bc/v1/user/alias",
            data=data,
        )
        if response.get("errored", False):
            raise Exception(f"Error aliasing user: {response.get('message')}")
        logger.debug(f"User {id} aliased to {previous_id}")

    async def start_listening(
        self,
        *,
        on_event: Callable[[MLEvent], Awaitable[None]],
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ) -> None:
        """Start listening for events from the Mindlytics API.

        This method sets up a WebSocket connection to the Mindlytics API and listens for events.  When an event is
        received, the `on_event` callback is called with the event data.  If an error occurs, the `on_error` callback
        is called with the error.

        You must run this function something like this:
        ```python
        asyncio.create_task(client.listen_for_events(...))
        ```

        Args:
            on_event (callable): A callback function to handle incoming events.
            on_error (callable, optional): A callback function to handle errors.
        """
        self.ws = WS(config=self.config)
        response = await self.ws.get_authorization_token()
        if response.get("errored", False):
            raise Exception(response.get("message"))
        authorization_key = response.get("authorization_key")
        if authorization_key is None:
            raise Exception("Unable to obtain authorization key")
        logger.debug("Starting WebSocket listener...")

        # The following stuff is like new Promise(resolve, reject) in JS
        # It will resolve when the connection is established and the listener is started
        connected_future = asyncio.get_event_loop().create_future()

        def on_connected():
            logger.debug("WebSocket connection established")
            connected_future.set_result(True)

        self.listener = asyncio.create_task(
            self.ws.listen_for_events(
                authorization_key=authorization_key,
                on_event=on_event,
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
                self.listener.cancel()
                try:
                    await self.listener
                except asyncio.CancelledError:
                    pass
                self.listener = None
