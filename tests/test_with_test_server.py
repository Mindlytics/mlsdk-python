import pytest
import pytest_asyncio
import os
from mlsdk import Client
import logging
from .utils import get_api_key, cleanup

debug = False

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)  # Use module name

server = os.getenv("MLSDK_SERVER_BASE")
api_key = None

if server is None:
    logger.warning(
        "SERVER_BASE environment variable is not set. Skipping tests that require a server."
    )


@pytest_asyncio.fixture(scope="module", autouse=True)
async def after():
    # Setup for test2.py
    logger.debug("Setting up test2.py resources")
    yield  # This allows all tests to run
    # Cleanup after all tests in test2.py have finished
    logger.debug("Cleaning up test2.py resources")
    await cleanup()
    # Specific cleanup code for test2.py


@pytest.mark.asyncio
async def test_basic_auth_failure():
    # Test session as context manager
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    client = Client(
        api_key="test_api_key",
        project_id="test_project",
        debug=debug,
        server_endpoint=server,
    )
    session_context = client.create_session(device_id="test_device_id")
    async with session_context as session:
        await session._enqueue({"foo": "bar"})
    assert session.has_errors() is True
    errors = session.get_errors()
    assert len(errors) == 3  # because of start_session, enqueue, and end_session
    assert errors[0].status == 403
    assert (
        errors[0].message
        == "Error: 403 - Unauthorized: No organization found for given apikey: test_api_key"
    )


@pytest.mark.asyncio
async def test_get_api_key():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    global api_key
    api_key = await get_api_key("org-1")
    assert api_key is not None
    assert isinstance(api_key, str)
    assert len(api_key) > 0


@pytest.mark.asyncio
async def test_basic_event_failure():
    # Test session as context manager
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    client = Client(
        api_key=api_key, project_id="test_project", debug=debug, server_endpoint=server
    )
    session_context = client.create_session(device_id="test_device_id")
    async with session_context as session:
        await session._enqueue({"foo": "bar"})
    assert session.has_errors() is True
    errors = session.get_errors()
    assert len(errors) == 1
    assert errors[0].status == 400
    assert errors[0].message == "Error: 400 - Invalid wire type: undefined"


@pytest.mark.asyncio
async def test_basic_event_success():
    # Test session as context manager
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    client = Client(
        api_key=api_key, project_id="test_project", debug=debug, server_endpoint=server
    )
    session_context = client.create_session(device_id="test_device_id")
    async with session_context as session:
        await session.track_event(
            event="test_event",
            properties={
                "foo": "bar",
                "bool": True,
                "int": 42,
                "float": 3.14,
            },
        )
    if session.has_errors():
        errors = session.get_errors()
        logger.error("Errors: %s", errors)
    assert session.has_errors() is False
    errors = session.get_errors()
    assert len(errors) == 0
    assert session.has_errors() is False
