import pytest
import pytest_asyncio
import os
from mlsdk import Client, MLEvent
import logging
from .utils import get_api_key, cleanup
import asyncio

debug = True

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)  # Use module name

server = os.getenv("SERVER_BASE")
wss_server = os.getenv("WSS_BASE")
session_id = None
client = None
events = []
errors = []

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
    # Specific cleanup code for test2.py
    await cleanup()


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
async def test_create_handler():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    global session_id
    global client
    global events
    global errors
    client = Client(
        api_key=api_key,
        project_id="test_project",
        debug=debug,
        server_endpoint=server,
        wss_endpoint=wss_server,
    )

    async def on_event(event: MLEvent):
        # logger.debug(f"Received event: {event}")
        assert event is not None
        assert isinstance(event, MLEvent)
        events.append(event)

    async def on_error(error: Exception):
        logger.error(f"Error: {error}")
        errors.append(error)

    await client.start_listening(
        on_event=on_event,
        on_error=on_error,
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

    count = 30
    while len(events) < 3:
        logger.debug(f"Waiting for events..., recieved {len(events)}/3 events")
        await asyncio.sleep(1)
        count -= 1
        if count == 0:
            logger.error("Timeout waiting for events")
            break

    await client.stop_listening()
    assert len(events) == 3
    assert len(errors) == 0
    assert events[0].event == "Session Started"
    assert events[1].event == "test_event"
    assert events[2].event == "Session Ended"
