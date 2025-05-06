from typing import Optional
import uuid
import logging

logger = logging.getLogger(__name__)  # Use module name


class Client:
    def __init__(
        self,
        *,
        api_key: str,
        server_endpoint: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        from .types import ClientConfig

        config = ClientConfig(
            api_key=api_key,
            server_endpoint=server_endpoint,
            debug=debug,
        )
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
        session_id: Optional[str] = None,
        project_id: str,
        user_id: Optional[str] = None,
    ) -> "Session":
        """
        Create a new session with the given parameters.
        :param session_id: Optional session ID.
        :param project_id: Project ID.
        :param user_id: Optional user ID.
        :return: A Session object.
        """
        from .types import SessionConfig

        config = SessionConfig(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
        )
        return Session(self, config)


class Session:
    from .types import SessionConfig

    def __init__(self, client: Client, config: SessionConfig) -> None:
        self.client = client
        self.project_id = config.project_id
        self.session_id = config.session_id
        self.user_id = config.user_id
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())
