import pytest
import os
from mlsdk import Client
import logging
from .utils import get_api_key, fetch
import json
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)  # Use module name

server = os.getenv("SERVER_BASE")
api_key = None
session_id = None

if server is None:
    logger.warning(
        "SERVER_BASE environment variable is not set. Skipping tests that require a server."
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
async def test_create_session():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    global session_id
    client = Client(
        api_key=api_key, project_id="test_project", debug=True, server_endpoint=server
    )
    session_context = client.create_session()
    session_id = await session_context.start_session()
    assert session_id is not None
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    assert session_id == session_context.session_id
    await session_context.end_session()
    assert session_context.has_errors() is False

    # fetch the session
    session = await fetch(
        api_key=api_key,
        app_id="test_project",
        collection="sessions",
        op="findOne",
        filter={"session_id": session_id},
        include=["user"],
    )
    # logger.debug(f"Session: {json.dumps(session, indent=2)}")
    assert session is not None
    assert isinstance(session, dict)
    assert session["session_id"] == session_id
    assert session["user"] is not None
    assert isinstance(session["user"], dict)
    assert session["user"]["id"].startswith("anonymous") is True


@pytest.mark.asyncio
async def NOT_WORKING_create_session_and_identify_user():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    client = Client(
        api_key=api_key,
        project_id="test_project",
        debug=True,
        server_endpoint=server,
    )
    session_context = client.create_session()
    session_id = await session_context.start_session()
    await session_context.user_identify(
        id="test_user",
        traits={
            "name": "Test User",
            "email": "test@test.com",
            "age": 30,
            "is_subscribed": True,
            "height": 1.75,
        },
    )
    await session_context.end_session()
    assert session_context.has_errors() is False
    # fetch the session
    session = await fetch(
        api_key=api_key,
        app_id="test_project",
        collection="sessions",
        op="findOne",
        filter={"session_id": session_id},
        include=["user"],
    )
    logger.debug(f"Session: {json.dumps(session, indent=2)}")
    assert session is not None
    assert isinstance(session, dict)
    assert session["user"] is not None
    assert isinstance(session["user"], dict)
    assert session["user"]["id"] == "test_user"
    assert session["user"]["traits"] is not None
    assert isinstance(session["user"]["traits"], dict)
    assert session["user"]["traits"]["name"] == "Test User"
    assert session["user"]["traits"]["email"] == "test@test.com"
    assert session["user"]["traits"]["age"] == 30
    assert session["user"]["traits"]["is_subscribed"] is True
    assert session["user"]["traits"]["height"] == 1.75
    assert isinstance(session["user"]["aliases"], list)
    assert len(session["user"]["aliases"]) == 2
    assert session["user"]["aliases"][0].startswith("anonymous") is True
    assert session["user"]["aliases"][1] == "test_user"


@pytest.mark.asyncio
async def TBD_create_session_with_existing_user_id():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    pass


@pytest.mark.asyncio
async def test_create_session_with_attributes():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    client = Client(
        api_key=api_key,
        project_id="test_project",
        debug=True,
        server_endpoint=server,
    )
    session_context = client.create_session()
    session_id = await session_context.start_session(
        attributes={
            "custom": "attribute",
        }
    )
    assert session_id is not None
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    await session_context.end_session()
    assert session_context.has_errors() is False
    # fetch the session
    session = await fetch(
        api_key=api_key,
        app_id="test_project",
        collection="sessions",
        op="findOne",
        filter={"session_id": session_id},
        include=["user"],
    )
    # logger.debug(f"Session: {json.dumps(session, indent=2)}")
    assert session is not None
    assert isinstance(session, dict)
    assert session["session_id"] == session_id
    assert session["attributes"] is not None
    assert isinstance(session["attributes"], dict)
    assert session["attributes"]["custom"] == "attribute"


@pytest.mark.asyncio
async def test_simple_conversation():
    if server is None:
        pytest.skip("SERVER_BASE environment variable is not set.")
    client = Client(
        api_key=api_key,
        project_id="test_project",
        debug=True,
        server_endpoint=server,
    )
    session_context = client.create_session()
    session_id = await session_context.start_session()
    conversation_id = await session_context.start_conversation()
    assert conversation_id is not None
    assert isinstance(conversation_id, str)
    assert len(conversation_id) > 0
    assert conversation_id == session_context.conversation_id
    await session_context.track_conversation_turn(
        user="I have to pee.  Can you help me find a bathroom?",
        assistant="I am sorry to report that there are no bathrooms in this virtual world.",
    )
    await session_context.end_conversation()
    await session_context.end_session()
    assert session_context.has_errors() is False
    # wait a few seconds for mindlytics to process this event with its llms
    await asyncio.sleep(5)
    # fetch the session
    session = await fetch(
        api_key=api_key,
        app_id="test_project",
        collection="sessions",
        op="findOne",
        filter={"session_id": session_id},
        include=["user", "conversations", "events", "intents"],
    )
    # logger.debug(f"Session: {json.dumps(session, indent=2)}")
    assert session is not None
    assert isinstance(session, dict)
    assert session["session_id"] == session_id

    assert session["conversations"] is not None
    assert isinstance(session["conversations"], list)
    assert len(session["conversations"]) == 1
    assert session["conversations"][0]["conversation_id"] == conversation_id
    assert session["conversations"][0]["session_id"] == session_id

    assert session["events"] is not None
    assert isinstance(session["events"], list)
    assert len(session["events"]) > 0

    assert session["intents"] is not None
    assert isinstance(session["intents"], list)
    assert len(session["intents"]) > 0
