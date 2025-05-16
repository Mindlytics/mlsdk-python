"""Client module for Mindlytics SDK."""

from typing import Optional, Dict, Union, Callable, Any
import logging
from .types import ClientConfig, SessionConfig, APIResponse
from .session import Session
from .httpclient import HTTPClient

logger = logging.getLogger(__name__)  # Use module name


class Client:
    """Client for communicating with the Mindlytics service.

    This class provides the main interface for interacting with the Mindlytics API.
    """

    def __init__(
        self,
        *,
        api_key: str,
        project_id: str,
        server_endpoint: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        """Initialize the Client with the given parameters.

        This method sets up the client configuration, including the API key.  It requires the project_id to be set,
        which is used to create sessions, although it is possible to override this on a per-session basis.

        The server endpoint can be specified, and debug logging can be enabled.  When logging is enabled,
        logging-style messages will be printed to the console.

        Once you have an instance of this class, you can create sessions using the `create_session` method.

        Args:
            api_key (str): The organization API key used for authentication.
            project_id (str): The default project ID used to create sessions.
            server_endpoint (str, optional): The URL of the Mindlytics API. Defaults to the production endpoint.
            debug (bool, optional): Enable debug logging if True.
        """
        config = ClientConfig(
            api_key=api_key,
            project_id=project_id,
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
        project_id: Optional[str] = None,
        id: Optional[str] = None,
        device_id: Optional[str] = None,
        attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
        err_callback: Optional[Callable[[APIResponse], None]] = None,
    ) -> Session:
        """Create a new session with the given parameters.

        This method creates a new session object that can be used to send events to the Mindlytics API.  The project_id
        and id can be specified, but if not provided,  the default project_id from the client configuration will
        be used.  Pass a id to associate the session with a specific user if you know the user.

        Args:
            project_id (str, optional): The ID of the project.
            id (str, optional): The ID of the user.
            device_id (str, optional): The device ID associated with the user.
            attributes (dict, optional): A dictionary of attributes associated with the session.
            err_callback (callable, optional): A callback function to handle errors.

        Returns:
            Session: A new session object.
        """
        config = SessionConfig(
            project_id=project_id or self.config.project_id,
            id=id,
            device_id=device_id,
        )
        return Session(
            client=self.config,
            config=config,
            attributes=attributes,
            err_callback=err_callback,
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
            config=self.config,
            sessionConfig=SessionConfig(
                project_id=self.config.project_id,
                id=id,
            ),
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
        if response.errored:
            raise Exception(f"Error identifying user: {response.message}")
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
            config=self.config,
            sessionConfig=SessionConfig(
                project_id=self.config.project_id,
                id=id,
            ),
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
        if response.errored:
            raise Exception(f"Error aliasing user: {response.message}")
        logger.debug(f"User {id} aliased to {previous_id}")
