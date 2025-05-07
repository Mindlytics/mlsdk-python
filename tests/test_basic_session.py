import pytest
from mlsdk import Client
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)  # Use module name


@pytest.mark.asyncio
async def test_session_as_context_manager():
    # Test session as context manager
    client = Client(api_key="test_api_key", debug=True)
    session_context = client.create_session(
        session_id="test_session", project_id="test_project", user_id="test_user"
    )
    logger.debug("Session context created successfully.")
    async with session_context as session:
        assert session.project_id == "test_project"
        assert session.session_id == "test_session"
        assert session.user_id == "test_user"
        assert session.client.api_key == "test_api_key"
        assert session.queue is not None
        assert session.listen_task is not None
        await session.enqueue({"test": "data"})
        logger.debug("Enqueued data successfully.")

    # Check if session is closed
    assert session.queue is None
    assert session.listen_task is None


@pytest.mark.asyncio
async def test_session_no_context_manager():
    # Test session without context manager
    client = Client(api_key="test_api_key", debug=True)
    session = client.create_session(
        session_id="test_session", project_id="test_project", user_id="test_user"
    )
    await session.start_session()
    await session.enqueue({"test": "data"})
    await session.end_session()
    assert session.queue is None
    assert session.listen_task is None
    logger.debug("Session ended successfully.")
