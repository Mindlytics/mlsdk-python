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

Except for client-level user identify and alias, all other communication with Mindlytics is contained within a "session".  In a session you may send your own "user defined" events; that is, events that are not specific to Mindlytics but are meaningful to you.  In a session you may also start a "conversation" and send special Mindlytics events related to this conversation.  Events happen at a point in time, but sessions and conversations have a start and an end and thus a specific duration.  This means you have to start them and end them.  Depending on how you use the SDK, sessions and conversations can be automatically started and ended for you and you don't have to worry about it.

Sessions, conversations and events have attributes (sessions) and properties (conversations, events) that are optional, but which you can populate with meaningful data that you wish to associate with them.

### User ID and Device ID

User IDs are something you can decide to use or not use.  If you decide to use them, user ids should be unique for a organization/project pair.  You can use anything you like as long as it is a string, and is unique for each user in a project.  Device IDs should represent unique devices, like a browser instance or a mobile device uuid.  Device IDs are considered globally unique.  If you do not use user ids, then you must use device ids.  You can use both.

| TBD more detail needed here

## Architecture

The Mindlytics SDK is designed to have an absolute minimal impact on your application.  The SDK requires `asyncio` and uses an asynchronous queue to decouple your application from the actual communication with Mindlytics.  When you interact with the SDK your data gets pushed into an asynchronous FIFO and the SDK returns control to your application immediately.  In the background the SDK removes data from the queue and tries to send it to the Mindlytics service.  The SDK handles errors, and any timeouts, retries or rate limits as it tries to get the data to the server.  When your application exists there is a way to wait on the SDK to completely drain the queue so no data is lost.

## Errors

Because your application code is completely decoupled from the SDK sending data, it is not possible to get Mindlytics errors as they happen, if they happen.  At any time you may query the Mindlytics session to see if it has any errors, and get a list of these errors.

```python
if session.has_errors():
    for err in session.get_errors():
        print(f"{err.status}: {err.message}")
```

You may also register a function as a error callback if you'd like notification of errors as they occur:

```python
from mlsdk import Client, APIResponse

def ml_error_reporter(err: APIResponse):
    print(f"{err.status}: {err.message}")

client = Client(...)
session = client.create_session(err_callback=ml_error_reporter)
```

## Client API

```python
from mlsdk import Client

client = Client(api_key="KEY", project_id="ID")
```

**Arguments:**

* api_key - Your Mindlytics workspace api key.
* project_id - The ID of a project in your workspace.  Used to create sessions.
* debug (optional, False) - Enable to turn on logging.
* server_endpoint (optional) - Use a different endpoint for the Mindlytics server.

**Returns:**

An instance of the Mindlytics client object.  This is used primarily to create sessions, but has two other methods for identifying users and managing aliasing outside of normal sessions.

```python
from mlsdk import Client, MLHTTPError

try:
    await client.user_identify(
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

Used to identify new users or devices and to merge traits on existing users or devices.

**Arguments:**

* id - A unique user id for a new user or an existing user for the workspace/project specified in `client`.  If this id already exists, the given traits are merged with any existing traits.  Any existing matching traits are over written.  Mindlytics supports strings, booleans, and numbers as trait values.
* device_id - (optional, None) A unique device id.  One of id or device_id is required.
* traits - (optional, None) - A dict of user or device traits.

```python
from mlsdk import Client, MLHTTPError

try:
    await client.user_alias(
        id="jjacob",
        previous_id="JJ@mail.com",
    )
except MLHTTPError as (e):
    print(f"{e.status} - {e.message}")
```

Used to create an alias for an existing user.

**Arguments:**

* id - The new id for this user.
* previous_id - The previous id value for this user.  The previous_id is used for the lookup.

```python
session = client.create_session(id='jjacob')

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
    id="jjacob",
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

Depending on your specific needs, you can use the Mindlytics SDK in a few different ways.  The safest and easiest way is to use a session as an `asynio` context manager.  If you use it this way, then sessions and conversations are created as needed internally and are shut down gracefully when the session instance goes out of context or is destroyed.  All you have to do within the context is send events.

If you cannot use a context, then you can call session methods by themselves.  Sessions and conversations will be started on demand as before, but you **must** explicitly call `await session.end_session()` before exiting your application to ensure that all queued requests get sent to the Mindlytics service.

Using those two methods makes using the SDK pretty easy but does not give you complete control.  For complete control, you may explicitly start and end sessions and conversations.  If you do this, you can override timestamps if for example, you are importing past data into Mindlytics.  Sessions and conversations can also have custom attributes and properties, both on "start" and "end", but only if you call those methods directly.  If you call conversation start/end explicitly it is also possible to maintain multiple conversations in one session.

**Arguments:**

* project_id - (optional, None) If specified, will overwrite the value given when creating the client.
* id - (optional, None) If the user id for this session is known, you can pass it here.
* device_id - (optional, None) A device id.  If user id is not passed, then device_id is required.
* attributes - (optional, None) Can pass a dictionary of str|int|float|bool of custom attributes.
* err_callback - (optional, None) A function that will be called whenever SDK detects an error with the Mindlytics service.

If an `id` is not passed, the session will be associated with a temporary anonymous user until the actual user is identified.

## Session API

```python
session_id = await session.start_session(id='jjacob')
```

To send events to Mindlytics you must start a session.  In some cases, this session is created for you and you don't need to worry about it.

**Arguments:**

* session_id - (optional, None) You can supply your own globally unique session id.  If you do not, then a uuid string is created by the SDK.
* timestamp - (optional, None) If importing past data you can specify a timestamp for the creation of this session.
* project_id - (optional, None) The project_id for this session.  Defaults to the project_id passed to the Mindlytics client.
* id - (optional, None) The user id for this session, if you know it.  Otherwise an anonymous user will be created.
* device_id - (optional, None) A unique device id.  If user id is not passed, then device_id is required.
* attributes - (optional, None) A dictionary of arbitrary attributes you may want to associated with this session.

**Returns:**

* session_id - The id for this session.  This session_id should be passed as an argument to subsequent events sent into this session.

```python
await session.send_session()
```

You must call this method to send a session.  This will block and wait until all pending events are send off to the Mindlytics server.  If you do **not** call this method, there is a chance you can lose data if it has not been transferred yet.  If there are open conversations associated with the session they are automatically closed.  When using the SDK as an asyncio context manager, this method is automatically called when the context is exited.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for the end of this session.
* attributes - (optional, None) A dictionary of arbitrary attributes you may want to associated with this session.  If specified, these attributes will be merged into any attributes added when the session was created.

```python
if session.has_errors():
    errors = session.get_errors()
```

The `has_errors()` method can be used to check if there have been any errors communicating with the Mindlytics service.  The `get_errors()` method can be used to retrieve any errors.  It returns a list of `APIResponse` objects (pydantic data models):

```python
class APIResponse(BaseModel):
    """Base class for API responses.

    Attributes:
        errored (bool): Indicates if the API response contains an error.
        status (str): The status of the API response.
        message (str): A message associated with the API response.
    """

    errored: bool
    status: int
    message: str
```

```python
await session.user_identify(
    id="JJ@mail.com",
    traits={
        "name": "Jacob Jones",
        "email": "jj@mail.com",
        "country": "United States"
    }
)
```

If the user involved in a session becomes know during the session, or if the user should have some new traits added, you can call this method.

**Attributes:**

* timestamp - (optional, None) If specified, the timestamp associated with this event.  For new users, this becomes their start date.
* id - (optional, None) A unique user id for a new user or an existing user for the workspace/project specified in `client`.  If this id already exists, the given traits are merged with any existing traits.  Any existing matching traits are over written.  Mindlytics supports strings, booleans, and numbers as trait values.
* device_id - (optional, None) A unique device id.  If user id is not passed then device_id is requiredd.
* traits - (optional, None) - A dict of user traits.

```python
await sessuin.user_alias(
    id="jjacob",
    previous_id="JJ@mail.com",
)
```

Used to create an alias for an existing user within a session.

**Arguments:**

* timestamp - (optional, None) If specified, the timestamp associated with this event.
* id - The new id for this user.
* previous_id - The previous id value for this user.  The previous_id is used for the lookup.

```python
await session.track_event(event="My Custom Event")
await session.track_event(
    event="Another Event",
    properties={
        "email": "test@test.com", # str
        "age": 30,                # int
        "is_subscribed": True,    # bool
        "height": 1.75,           # float
    }
)
```

Use this method to send your own custom events to the Mindlytics service.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for the occurrence of this event.
* event - (str, required) The name of the event.
* conversation_id - (optional, None) The conversation_id if this event is to be associated with an open conversation.
* properties (optional, dict) A dictionary of arbitrary properties you may want to associate with this event.  Supported value types are str, int, bool and float.

```python
conversation_id = await session.start_conversation()
```

This opens a new conversation within the session.  You may have multiple conversations open within a single session.  Some special events (describes below) require a conversation id.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for this event.  This would be the start date of the conversation.
* conversation_id - (optional, None) You can supply your own globally unique conversation id.  If you do not, then a uuid string is created by the SDK.
* properties (optional, dict) A dictionary of arbitrary properties you may want to associate with this conversation.  Supported value types are str, int, bool and float.

**Returns:**

* conversation_id (str) - The conversation id.

```python
await session.end_conversation()
```

This method is used to close a conversation.  Conversations have a duration, and this method is needed to identify the end.  When using the SDK as an asynio context, this method will be called automatically when the context is closed.  Also, when `session.end_session()` is called, any open conversations are also closed.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for this event.  This would be the end date of the conversation.
* conversation_id - (optional, None) To close a specific conversation if there are more than one open, the conversation id if the one you want to close.
* properties (optional, dict) A dictionary of arbitrary properties you may want to associate with this conversation.  These values will be merged with any you might have specified when the conversation was created.

```python
await session.track_conversation_turn(
    user="I am feeling hungry so I would like to find a place to eat.",
    assistant="Do you have a specific which you want the eating place to be located at?"
)
```

Send a single "turn" of a conversation to the Mindlytics service for analysis.

**Arguments:**

* timestamp - (optional, None) The timestamp of the conversation turn. Defaults to the current time.  Use this to import past data.
* conversation_id - (optional, None) The conversation id for this turn.  Defaults to current conversation.  Required if there are multiple opened conversations in this session.
* user - (required, str) The user utterance.
* assistant - (required, str) The assistant utterance.
* assistant_id - (optional, None) An assistant id for the assistant, used to identify agents.
* properties - (optional, dict) A dictionary of arbitrary properties you may want to associate with this conversation turn.
* cost - (optional, None) Use this to track your conversational LLM costs.

You can optionally track your own conversational LLM costs in Mindlytics.  You can do this on a turn-by-turn basis using this method, or on a less granular basis using the method described below.  You can specify costs in one of two ways; if your LLM is a popular, known LLM you may send your model's name and the prompt and completion token counts, and Mindlytics will use an online database to look up the per-token costs for this model and do the math.  Or you may pass in an actual cost as a float, if you know it or are using a less popular LLM.  The "cost" property can be one of:

```python
class TokenBasedCost(BaseModel):
    """Common models have costs that are provided by a service on the web.

    If you are using one of these models, you can provide the model name and the
    number of tokens in the prompt and completion, and the cost will be calculated for you.
    """

    model: str = Field(..., min_length=1, max_length=100)
    prompt_tokens: int
    completion_tokens: int


class Cost(BaseModel):
    """If you know the cost of a conversation turn, you can provide it directly.

    This will be accumulated in the conversation analysis.
    """

    cost: float
```

```python
await session.track_conversation_usage(
    cost: TokenBasedCost(model="gpt-4o", prompt_tokens=134, completion_tokens=237)
)
```

Use this method to track your own LLM costs.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for this event.
* conversation_id - (optional, None) The conversation id for this usage.  Defaults to current conversation.
* cost: (required, Union[TokenBasedCost, Cost]) - A cost to be added to the conversation cost so far.
