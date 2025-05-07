"""Session module for Mindlytics SDK!"""

import uuid
from .types import SessionConfig, ClientConfig


class Session:
    """Session class for managing a session with the Mindlytics service.

    This class is used to create a session for a specific project and user.

    Attributes:
        client (Client): The client instance used to communicate with the Mindlytics service.
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
