from mlsdk import Client
import logging

logging.basicConfig(level=logging.DEBUG)


def test_client_initialization():
    # Test with all parameters
    client = Client(api_key="test_api_key", debug=True)
    assert client.api_key == "test_api_key"
    assert client.server_endpoint == "https://app.mindlytics.ai"
    assert client.debug is True


def test_create_session():
    # Test session creation with all parameters
    client = Client(api_key="test_api_key", debug=True)
    session = client.create_session(
        session_id="test_session", project_id="test_project", user_id="test_user"
    )
    assert session.project_id == "test_project"
    assert session.session_id == "test_session"
    assert session.user_id == "test_user"
    assert session.client.api_key == "test_api_key"


def test_create_session_without_session_id():
    # Test session creation without session_id
    client = Client(api_key="test_api_key", debug=True)
    session = client.create_session(project_id="test_project", user_id="test_user")
    assert session.project_id == "test_project"
    assert session.session_id is not None  # Check if session_id is generated
    assert session.user_id == "test_user"


def test_create_session_without_project_id():
    # Test session creation without project_id
    client = Client(api_key="test_api_key", debug=True)
    try:
        client.create_session(session_id="test_session", user_id="test_user")
    except TypeError as e:
        assert (
            str(e)
            == "Client.create_session() missing 1 required keyword-only argument: 'project_id'"
        )
    else:
        assert False, "Expected TypeError not raised"
