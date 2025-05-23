"""Mindlytics WebSocket Client."""

from typing import Optional, Dict, Callable, Any, Awaitable
import logging
import json
from .types import ClientConfig, MLEvent
from .httpclient import HTTPClient
import asyncio

logger = logging.getLogger(__name__)  # Use module name
logging.getLogger("websockets").setLevel(logging.ERROR)


class WS:
    """Client for communicating with the Mindlytics WebSocket API.

    This class provides the main interface for interacting with the Mindlytics WebSocket API.
    """

    def __init__(
        self,
        *,
        config: ClientConfig,
    ) -> None:
        """Initialize the WS client with the given parameters.

        This method sets up the client configuration, including the API key.  It requires the project_id to be set,
        which is used to create sessions, although it is possible to override this on a per-session basis.

        The server endpoint can be specified, and debug logging can be enabled.  When logging is enabled,
        logging-style messages will be printed to the console.

        Args:
            config (ClientConfig): The configuration for the Mindlytics API client.
        """
        self.config = config
        self.api_key = config.api_key
        self.wss_endpoint = config.wss_endpoint
        self.server_endpoint = config.server_endpoint
        if config.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

    async def get_authorization_token(
        self,
        *,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the authorization token for the WebSocket connection.

        This method retrieves the authorization token from the Mindlytics API.  The token is used to authenticate
        the WebSocket connection.  If a session ID is provided, it will be included in the request.

        Args:
            session_id (str, optional): The ID of the session to retrieve the token for.

        Returns:
            str: The authorization token.
        """
        http_client = HTTPClient(
            server_endpoint=self.server_endpoint,
            api_key=self.api_key,
            project_id=self.config.project_id,
            debug=self.config.debug,
        )
        data = {}
        if session_id is not None:
            data["session_id"] = session_id
        try:
            response = await http_client.send_request(
                method="GET",
                url="/bc/v1/live-events/realtime",
                data=data,
            )
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            raise

        return response

    async def listen_for_events(
        self,
        *,
        authorization_key: str,
        on_event: Callable[[MLEvent], Awaitable[None]],
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
        on_connected: Optional[Callable[[], None]] = None,
    ) -> None:
        """Listen for events from the Mindlytics API.

        This method sets up a WebSocket connection to the Mindlytics API and listens for events.  When an event is
        received, the `on_event` callback is called with the event data.  If an error occurs, the `on_error` callback
        is called with the error.

        You must run this function something like this:
        ```python
        asyncio.create_task(client.listen_for_events(...))
        ```

        Args:
            authorization_key (str): The authorization key for the WebSocket connection.
            on_event (callable): A callback function to handle incoming events.
            on_error (callable, optional): A callback function to handle errors.
            on_connected (callable, optional): A callback function to handle successful connection.
        """
        import websockets
        from websockets.asyncio.client import connect

        ws_url = self.wss_endpoint
        headers = [("Authorization", f"Bearer {authorization_key}")]

        async def log_error(error: Exception) -> None:
            logger.error(f"Mindlytics Error: {str(error)}")
            if on_error:
                await on_error(error)

        try:
            async with connect(ws_url, additional_headers=headers) as websocket:
                if on_connected:
                    on_connected()
                try:
                    async for message in websocket:
                        try:
                            event = json.loads(message)
                            e = MLEvent(**event)
                            if e.event == "MLError":
                                error_message = (
                                    e.properties.get("error_message", "Unknown error")
                                    if e.properties and isinstance(e.properties, dict)
                                    else "Unknown error"
                                )
                                await log_error(Exception(error_message))
                            else:
                                await on_event(e)
                        except Exception as e:
                            await log_error(e)
                except asyncio.CancelledError:
                    pass
                except websockets.exceptions.ConnectionClosedError:
                    pass
                except Exception as e:
                    await log_error(e)
        except websockets.exceptions.ConnectionClosedError:
            pass
        except websockets.exceptions.WebSocketException as e:
            await log_error(e)
        except Exception as e:
            await log_error(e)
