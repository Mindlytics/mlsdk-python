"""Client module for Mindlytics SDK."""

from typing import Optional
import logging
from .types import ClientConfig, SessionConfig
from .session import Session

logger = logging.getLogger(__name__)  # Use module name


class Client:
    """Client for communicating with the Mindlytics service.

    This class provides methods to send requests to the backend API.

    Attributes:
        api_key (str): The organization API key used for authentication.
        server_endpoint (str, optional): The URL of the Mindlytics API. Defaults to the production endpoint.
        debug (boolean, optional): Enable debug logging if True.
    """

    def __init__(
        self,
        *,
        api_key: str,
        server_endpoint: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        """Initialize the Client with the given parameters.

        Args:
            api_key (str): The organization API key used for authentication.
            server_endpoint (str, optional): The URL of the Mindlytics API. Defaults to the production endpoint.
            debug (bool, optional): Enable debug logging if True.
        """
        config = ClientConfig(
            api_key=api_key,
            server_endpoint=server_endpoint,
            debug=debug,
        )
        self.config = config
        self.api_key = config.api_key
        self.server_endpoint = config.server_endpoint or "https://app.mindlytics.ai"
        self.debug = config.debug

        if self.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

        logger.debug(f"Client initialized with server endpoint: {self.server_endpoint}")

    def create_session(
        self,
        *,
        project_id: str,
        user_id: Optional[str] = None,
    ) -> Session:
        """Create a new session with the given parameters.

        Args:
            project_id (str): The ID of the project.
            user_id (str, optional): The ID of the user.

        Returns:
            Session: A new session object.

        Raises:
            TypeError: If project_id is not provided.
        """
        config = SessionConfig(
            project_id=project_id,
            user_id=user_id,
        )
        return Session(client=self.config, config=config)
