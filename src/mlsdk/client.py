from typing import Optional


class Client:
    def __init__(
        self,
        *,
        api_key: str,
        server_endpoint: Optional[str] = None,
        debug_level: int = 0,
    ) -> None:
        from .types import ClientConfig

        config = ClientConfig(
            api_key=api_key,
            server_endpoint=server_endpoint,
            debug_level=debug_level,
        )
        self.api_key = config.api_key
        self.server_endpoint = config.server_endpoint or "https://app.mindlytics.ai"
        self.debug_level = config.debug_level
        print("Client initialized")
