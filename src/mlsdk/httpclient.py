"""The HTTP client for the Mindlytics API."""

import aiohttp
import logging
import backoff
from .types import ClientConfig, SessionConfig, APIResponse

logger = logging.getLogger(__name__)  # Use module name


class HTTPClient:
    """HTTP client for communicating with the Mindlytics API.

    This class provides methods to send requests to the backend API.

    Attributes:
        config (ClientConfig): The configuration for the HTTP client.
        headers (dict): The headers to be used in the HTTP requests.
    """

    def __init__(self, *, config: ClientConfig, sessionConfig: SessionConfig) -> None:
        """Initialize the HTTP client with the given configuration.

        Args:
            config (ClientConfig): The configuration for the HTTP client.
            sessionConfig (SessionConfig): The configuration for the session.
        """
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "X-App-ID": str(sessionConfig.project_id),
        }
        if self.config.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_time=60)
    async def send_request(self, *, method: str, url: str, data: dict) -> APIResponse:
        """Send an HTTP request to the Mindlytics API.

        Args:
            method (str): The HTTP method (GET, POST, etc.).
            url (str): The URL for the request.
            data (dict): The data to be sent in the request.

        Returns:
            APIResponse: The response from the API.
        """
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                f"{self.config.server_endpoint}{url}",
                headers=self.headers,
                json=data,
            ) as response:
                if response.status != 200:
                    return APIResponse(
                        errored=True,
                        status=response.status,
                        message=f"Error: {response.status} - {await response.text()}",
                    )
                return APIResponse(
                    errored=False,
                    status=response.status,
                    message=await response.text(),
                )
