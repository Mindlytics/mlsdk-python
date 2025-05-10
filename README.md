# Mindlytics Python SDK

This is the [Mindlytics](https://mindlytics.ai) client-side SDK for Python clients.  It is used to authenticate and send telemetry events to the Mindlytics analytics backend server.

This SDK uses `asyncio` and the `asyncio.Queue` to decouple your existing client code from the communication overhead of sending data to Mindlytics.  When you send events with this SDK you are simply pushing data into a queue.  A background coroutine in the SDK will pop the queue and handle the actual communication with Mindlytics, handling errors, timeouts, rate limits, etc with zero impact to your main application.

```python
import asyncio
from mlsdk import Client

async def main():
    client = Client(
        api_key="YOUR_WORKSPACE_API_KEY",
        project_id="YOUR_PROJECT_ID",
    )
    session_context = client.create_session()
    # use as a context manager
    async with session_context as session:
        await session.track_conversation_turn(
            user="I would like book an airline flight to New York.",
            assistant="No problem!  When would you like to arrive?",
        )
    # leaving the context will automatically flush any pending data in the queue and wait until
    # everything has been sent.

asyncio.run(main())
```

The SDK can be used as a context manager, but it can also be used outside a context for more control.

## Concepts

| TBD

## Client API

```python
from mlsdk import Client

client = Client(api_key="KEY", project_id="ID")
```

**Arguments**

* api_key - Your Mindlytics workspace api key.
* project_id - The ID of a project in your workspace.  Used to create sessions.
* debug (optional, False) - Enable to turn on logging.
* server_endpoint (optional) - Use a different endpoint for the Mindlytics server.

**Returns**

An instance of the Mindlytics client object.  This is used primarily to create sessions, but has two other methods for identifying users and managing aliasing outside of normal sessions.

```python
from mlsdk import Client, MLHTTPError

try:
    user = await client.user_identify(
        id="JJ@mail.com",
        traits={
            "name": "Jacob Jones",
            "email": "jj@mail.com",
            "country": "United States"
        }
    )
except MLHTTPError as (e):
    print(f"{e.status} - {e.message}")
```

Used to identify new users and to merge traits on existing users.

**Arguments**

* id - A unique user id for a new user or an existing user for the workspace/project specified in `client`.  If this id already exists, the given traits are merged with any existing traits.  Any existing matching traits are over written.  Mindlytics supports strings, booleans, and numbers as trait values.
* traits - (optional, None) - A dict of user traits.

**Returns:***

A Mindlytics user object.

```python
from mlsdk import Client, MLHTTPError

try:
    user = await client.user_alias(
        id="jjacob",
        previous_id="JJ@mail.com",
    )
except MLHTTPError as (e):
    print(f"{e.status} - {e.message}")
```

Used to create an alias for an existing user.

**Arguments**

* id - The new id for this user.
* previous_id - The previous id value for this user.  The previous_id is used for the lookup.

**Returns:***

A Mindlytics user object.

```python
session = client.create_session()

# Use session as a context manager
async with session as ml:
    await ml.track_event(event="Start Chat", properties={"from": "shopping cart"})
    await session.track_conversation_turn(
        user="I need help choosing the right lipstick for my skin color.",
        assistant="I can help you with that.  What color would you use to describe your skin tone?",

# Or send events without a context, but make sure to end the session to flush the event queue!
await session.track_event(event="Start Chat", properties={"from": "shopping cart"})
await session.track_conversation_turn(
    user="I need help choosing the right lipstick for my skin color.",
    assistant="I can help you with that.  What color would you use to describe your skin tone?",
await session.end_session()

# Or control the entire workflow manually
session_id = await sesson.start_session(
    timestamp="2025-04-03T07:35:10.0000Z",
    user_id="jjacob",
    attributes={
        "store": "135"
    }
)
await session.track_event(
    timestamp="2025-04-03T07:35:35.0000Z",
    event="Start Chat",
    properties={
        "from": "shopping cart"
    }
)
conversation_id = await session.start_conversation(
    timestamp="2025-04-03T07:35:35.0000Z",
    properties={
        "timezone": "America/Los_Angeles"
    }
)
await session.track_conversation_turn(
    conversation_id=conversation_id,
    timestamp="2025-04-03T07:36:03.0000Z",
    user="I need help choosing the right lipstick for my skin color.",
    assistant="I can help you with that.  What color would you use to describe your skin tone?",
    cost={
        "model": "gpt-4o",
        "prompt_tokens": 15,
        "completion_tokens": 19
    }
)
await session.end_conversation(
    conversation_id=conversation_id,
    timestamp="2025-04-03T07:36:40.0000Z",
    properties={
        "device": "browser"
    }
)
await session.end_session(
    timestamp="2025-04-03T07:37:15.0000Z",
    attributes={
        "resolved": True
    }
)
```

Depending on your specific needs, you can use the Mindlytics SDK in a few different ways.  The safest and easiest way is to use a session as an asynio context manager.  If you use it this way, then sessions and conversations are created as needed internally and are shut down gracefully when the session instance goes out of context or is destroyed.  All you have to do within the context is send events.

If you cannot use a context, then you can call session methods by themselves.  Sessions and conversations will be started on demand as before, but you **must** explicitly call `await session.end_session()` before exiting your application to ensure that all queued requests get sent to the Mindlytics service.

Using those two methods makes using the SDK pretty easy but does not give you complete control.  For complete control, you may explicitly start and end sessions and conversations.  If you do this, you can override timestamps if for example, you are importing past data into Mindlytics.  Sessions and conversations can also have custom attributes and properties, both on "start" and "end", but only if you call those methods directly.  If you call conversation start/end explicitly it is also possible to maintain multiple conversations in one session.

## Session API
