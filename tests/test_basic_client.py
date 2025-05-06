from mlsdk import Client


def test_client_initialization():
    # Test with all parameters
    client = Client(api_key="test_api_key")
    assert client.api_key == "test_api_key"
    assert client.server_endpoint == "https://app.mindlytics.ai"
    assert client.debug_level == 0
