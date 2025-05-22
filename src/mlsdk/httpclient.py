"""The HTTP client for the Mindlytics API."""

import aiohttp
import logging
import backoff
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)  # Use module name


class HTTPClient:
    """HTTP client for communicating with the Mindlytics API.

    This class provides methods to send requests to the backend API.

    Attributes:
        api_key (str): The organization API key used for authentication.
        project_id (str): The default project ID used to create sessions.
        config (dict): Configuration for the HTTP client.
        headers (dict): Headers for the HTTP requests.
    """

    def __init__(
        self,
        *,
        server_endpoint: Optional[str] = None,
        api_key: str,
        project_id: str,
        debug: bool,
    ) -> None:
        """Initialize the HTTP client with the given configuration.

        Args:
            server_endpoint (str): The URL of the Mindlytics API.
            api_key (str): The organization API key used for authentication.
            project_id (str): The default project ID used to create sessions.
            debug (bool, optional): Enable debug logging if True.
        """
        self.api_key = api_key
        self.project_id = project_id
        self.server_endpoint = server_endpoint or "https://app.mindlytics.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-App-ID": self.project_id,
        }
        if debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_time=60)
    async def send_request(
        self, *, method: str, url: str, data: dict
    ) -> Dict[str, Any]:
        """Send an HTTP request to the Mindlytics API.

        Args:
            method (str): The HTTP method (GET, POST, etc.).
            url (str): The URL for the request.
            data (dict): The data to be sent in the request.

        Returns:
            APIResponse: The response from the API.
        """
        async with aiohttp.ClientSession() as session:
            request_args: Dict[str, Any] = {
                "headers": self.headers,
                "timeout": aiohttp.ClientTimeout(total=60),
            }
            if method in ["POST", "PUT", "PATCH"]:
                request_args["json"] = data
            elif method == "GET":
                request_args["params"] = data
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            async with session.request(
                method,
                f"{self.server_endpoint}{url}",
                **request_args,
            ) as response:
                if response.status != 200:
                    return {
                        "errored": True,
                        "status": response.status,
                        "message": f"Error: {response.status} - {await response.text()}",
                    }
                return await response.json()
