# Mindlytics Python SDK

This is the [Mindlytics](https://mindlytics.ai) client-side SDK for Python clients.  It is used to authenticate and send telemetry events to the Mindlytics analytics backend server.

This SDK uses `asyncio` and the `asyncio.Queue` to decouple your existing client code from the communication overhead of sending data to Mindlytics.  When you send events with this SDK you are simply pushing data into a queue.  A background coroutine in the SDK will pop the queue and handle the actual communication with Mindlytics, handling errors, timeouts, rate limits, etc with zero impact to your main application.

```python
# A simple chatbot server that integrates with the Mindlytics service

from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import asyncio
import os
from openai import OpenAI
from dotenv import load_dotenv
from mlsdk import Client as MLClient

load_dotenv()
app = FastAPI()
openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.middleware("http")
async def add_session_to_request(request: Request, call_next):
    # Get client-side ids from headers
    session_id = request.headers.get("x-session-id")
    conversation_id = request.headers.get("x-conversation-id")
    user_id = request.headers.get("x-user-id")
    device_id = request.headers.get("x-device-id")

    # Instanciate a client object with your organization api key and project id
    ml = MLClient(
        api_key=os.environ.get("MLSDK_API_KEY",
        project_id=os.environ.get("MLSDK_PROJECT_ID",
    )

    # session_id is required.  It should be a unique uuid representing a unique user session.
    # conversation_id is optional, but required if sending conversation-related events.
    # One of user_id or device_id is required.
    request.state.mlsession = ml.create_session(
        session_id=session_id,
        conversation_id=conversation_id,
        id=user_id,
        device_id=device_id,
    )

    try:
        response = await call_next(request)
    finally:
        # Flush the mindlytics event queue to ensure all messages are sent
        await request.state.mlsession.flush()

    return response

# Simple streamer function to stream tokens back to the client.
async def openai_streamer(mlsession, question: str):
    assistant = ""
    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": question}],
        stream=True,
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        assistant.append(content)  # Capture the entire response ...
        yield content

    # Send the complete "turn" to the Mindlytics service
    await mlsession.track_conversation_turn(
        user: question,
        assistant: assistant
    )

class AskRequest(BaseModel):
    question: str

# Endpoint for asking a question of the assistant
@app.post("/ask-assistant")
async def ask_assistant(ask_request: AskRequest):
    return StreamingResponse(openai_streamer(ask_request.state.mlsession, ask_request.question), media_type="text/event-stream")

# Call this when the session/conversation is finished.
@app.post("end-session")
async def end-session(request: Request):
    await request.state.mlsession.end_session()
    return {"status": "ok"}
```

The SDK is stateless as long as you are consistent with session_ids and conversation_ids.  You must explicitly call `end_conversation()` when a conversation is finished, or an `end_session()` which will automatically end all open conversations associated with the session.  This is required so that Mindlytics can perform post-conversation analysis.

## Concepts

Except for client-level user identify and alias, all other communication with Mindlytics is contained within a "session".  In a session you may send your own "user defined" events; that is, events that are not specific to Mindlytics but are meaningful to you.  In a session you may also send special Mindlytics events related to conversations.  Events happen at a point in time, but sessions and conversations they belong to have a start and an end and thus a specific duration.

### User ID and Device ID

User IDs are something you can decide to use or not use.  If you decide to use them, user ids should be unique for a organization/project pair.  You can use anything you like as long as it is a string, and is unique for each user in a project.  Device IDs should represent unique devices, like a browser instance or a mobile device uuid.  Device IDs are considered globally unique.  If you do not use user ids, then you must use device ids.  You can use both.

For example, when a session begins you may not know the id of the user who starts it.  If this is the case, you must supply a "device_id" that is globally unique and represents the device the user is communicating on.  This might be a mobile device uuid.  This is harder on a browser, but you might use a uuid stored in a local cookie.  Sometime during the session/conversation you might discover who the user is and then you can issue a "session_user_identify" event with the user id, who will then be associated with the device_id and the session.

## Architecture

The Mindlytics SDK is designed to have a minimal impact on your application.  The SDK requires `asyncio` and uses an asynchronous queue to decouple your application from the actual communication with Mindlytics.  When you interact with the SDK your data gets pushed into an asynchronous FIFO and the SDK returns control to your application immediately.  In the background the SDK removes data from the queue and tries to send it to the Mindlytics service.  The SDK handles errors, and any timeouts, retries or rate limits as it tries to get the data to the server.  When your application exits there is a way to wait on the SDK to completely drain the queue so no data is lost.

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

def ml_error_reporter(err: Exception):
    print(str(err))

client = Client(...)
session = client.create_session(on_error=ml_error_reporter)
```

Since your application is decoupled from the Mindlytics backend, you can only get communication errors this way.  Deeper errors that might happen on the Mindlytics backend while processing queued messages are not possible to get this way.  However, this SDK supports an optional websockets mechanism which you might choose to employ to receive these processing errors, and to receive Mindlytics generated events as they are generated.  See [Websocket Support](#websocket-support) below.

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

You can set environment variables for `MLSDK_API_KEY` and `MLSDK_PROJECT_ID` which will be used unless you supply the value to the constructor.

**Returns:**

An instance of the Mindlytics client object.  This is used primarily to create sessions, but has two other methods for identifying users and managing aliasing outside of normal sessions.

```python
from mlsdk import Client

try:
    await client.user_identify(
        id="JJ@mail.com",
        traits={
            "name": "Jacob Jones",
            "email": "jj@mail.com",
            "country": "United States"
        }
    )
except Exception as (e):
    print(e.message)
```

Used to identify new users or devices and to merge traits on existing users or devices.

**Arguments:**

* id - A unique user id for a new user or an existing user for the workspace/project specified in `client`.  If this id already exists, the given traits are merged with any existing traits.  Any existing matching traits are over written.  Mindlytics supports strings, booleans, and numbers as trait values.
* device_id - (optional, None) A unique device id.  One of id or device_id is required.
* traits - (optional, None) - A dict of user or device traits.

```python
from mlsdk import Client

try:
    await client.user_alias(
        id="jjacob",
        previous_id="JJ@mail.com",
    )
except Exception as (e):
    print(e.message)
```

Used to create an alias for an existing user.

**Arguments:**

* id - The new id for this user.
* previous_id - The previous id value for this user.  The previous_id is used for the lookup.

```python
session = client.create_session(
    session_id=str(uuid.uuid4()),
    conversation_id=str(uuid.uuid4()),
    id='jjacob'
)

await session.track_event(event="Start Chat", properties={"from": "shopping cart"})
await session.track_conversation_turn(
    user="I need help choosing the right lipstick for my skin color.",
    assistant="I can help you with that.  What color would you use to describe your skin tone?",
await session.end_session()
await session.flush()
```

In the example above, the session consists of one conversation and all events are associated with that conversation.  But you can have multiple ongoing conversations within a single session, as long as those conversations belong to the same user or device.  You can do this by passing a conversation_id in a more granular way and by calling `end_conversation()`.  You can still call `end_session()` and that will automatically end all open conversations.  Here is an example:

```python
conversation_id_1 = str(uuid.uuid4())
conversation_id_2 = str(uuid.uuid4())

session = client.create_session(
    session_id=str(uuid.uuid4()),
    id='jjacob'
)

# custom events do not have to be associated with a conversation.
await session.track_event(event="Start Chat", properties={"from": "shopping cart"})

await session.track_conversation_turn(
    conversation_id=conversation_id_1,
    user="I need help choosing the right lipstick for my skin color.",
    assistant="I can help you with that.  What color would you use to describe your skin tone?",

await session.track_conversation_turn(
    conversation_id=conversation_id_2,
    user="Do we sell lipstick?",
    assistant="Yes",
)

await session.end_conversation(conversation_id=conversation_id_2)
await session.end_conversation(conversation_id=conversation_id_1)

await session.flush()
```

**Arguments:**

* session_id - (required, str) A globally unique session id for this session.
* conversation_id - (optional, None) A globally unique conversation_id to associated with all events in the session.
* id - (optional, None) If the user id for this session is known, you can pass it here.
* device_id - (optional, None) A device id.  If user id is not passed, then device_id is required.
* on_error - (optional, None) A function that will be called whenever SDK detects an error with the Mindlytics service.
* on_event - (optional, None) If specified, will start a websocket client session and report events as they are generated my Mindlytics

If an `id` is not passed, the session will be associated with a temporary anonymous user until the actual user is identified.

## Session API

```python
await session.flush()
```

This method will block and wait until all pending events are send off to the Mindlytics server.  If you do **not** call this method, there is a chance you can lose data if it has not been transferred yet.  Once this method is called you can no longer send any events to the Mindlytics service using this session instance.

```python
await session.flush_and_continue()
```

This method will block and wait until all pending events are send off to the Mindlytics server.  Calling this version of "flush" lets you continue to send messages to the Mindlyitcs service using this session instance.  You should eventually call `session.flush()` before destroying the session instance to make sure all asyncio tasks are cleaned up.

```python
await session.end_session()
```

You must call this method to end a session.  If there are open conversations associated with the session they are automatically closed.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for the end of this session.
* attributes - (optional, None) A dictionary of arbitrary attributes you may want to associated with this session.

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
await session.user_alias(
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
await session.end_conversation()
```

This method is used to close a conversation.  Conversations have a duration, and this method is needed to identify the end.  When `session.end_session()` is called, any open conversations are also closed.

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
* usage - (optional, None) Use this to track your conversational LLM costs.

You can optionally track your own conversational LLM costs in Mindlytics.  You can do this on a turn-by-turn basis using this method, or on a less granular basis using the method described below.  You can specify costs in one of two ways; if your LLM is a popular, known LLM you may send your model's name and the prompt and completion token counts, and Mindlytics will use an online database to look up the per-token costs for this model and do the math.  Or you may pass in an actual cost as a float, if you know it or are using a less popular LLM.  The "usage" property can be one of:

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

```python
await session.track_function_call(
    name="my_function_name",
    args='{"input1": 5, "input2": 6}',
    result="17",
    runtime=4093
)
```

Use this to track tool calls during a conversation.

**Arguments:**

* timestamp - (optional, None) If importing past data you can specify a timestamp for this event.
* conversation_id - (optional, None) The conversation id for this usage.  Defaults to current conversation.
* name - (required, str) The function name.
* args - (optional, str) The arguments to the function (usually a JSON string).
* result - (optional, str) The function result as a string.
* runtime - (optional, int) Number of milliseconds the function took to run.
* properties - (optional, dict) A dictionary of arbitrary properties you may want to associate with this function call.

## HTTPClient

There is a class you can use to communicate with the raw Mindlytics backend service endpoints.

```python
from mlsdk import HTTPClient

client = HTTPClient(
    api_key="YOUR_WORKSPACE_API_KEY",
    project_id="YOUR_PROJECT_ID",
)

response = await send_request(
    url="/bc/v1/events/queue",
    method="POST",
    data={
        # your data
    }
)
```

The response is a dictionary that looks like:

```python
{
    "errored": True, # or False
    "status": 500,   # http status code
    "message": "..." # Error message
}
```

## Websocket Support

While your application code is decoupled from the Mindlytics service in terms of sending events, it is possible to receive the events you send as well as the analytics events that Mindlytics generates over a websocket connection.  You can do this by registering callback handlers when you create a new session.

```python
from mlsdk import Client, MLEvent

async def main():
    client = Client(
        api_key="YOUR_WORKSPACE_API_KEY",
        project_id="YOUR_PROJECT_ID",
    )

    async def on_event(event: MLEvent) -> None:
        print(f"Received event: {event}")

    async def on_error(error: Exception) -> None:
        print(f"Error: {error}")

    session_context = client.create_session(
        device_id="test_device_id",
        on_event=on_event,
        on_error=on_error,
    )

    async with session_context as session:
        await session.track_conversation_turn(
            user="I would like book an airline flight to New York.",
            assistant="No problem!  When would you like to arrive?",
        )
    # leaving the context will automatically flush any pending data in the queue and wait until
    # everything has been sent.  Because you registered callbacks for websockets, the websocket connection
    # will wait until a "Session Ended" event arrives, and then close down the websocket connection.

asyncio.run(main())
```

## Helpers

The Mindlytics SDK comes with some built in "helpers" to make integrating the SDK easier with some popular AI frameworks.  See the "examples" directory for ideas of how to take advantage of these helpers.

## Examples

```sh
poetry run python -m ipykernel install --user --name=mindlytics --display-name "Mindlytics Python SDK"
```

On a mac, this command reported: `Installed kernelspec mindlytics in $HOME/Library/Jupyter/kernels/mindlytics`.

You should create a file named `.env.examples` with some key environment variables that are required by the demos, something like this (with your real values of course):

```sh
OPENAI_API_KEY="yours"
MLSDK_API_KEY="yours"
MLSDK_PROJECT_ID="yours"
```

And if you are using a non-standard Mindlytics backend, add

```sh
MLSDK_SERVER_BASE="http://localhost:3000"
```

Then execute:

```sh
eval `cat .env.examples` poetry run jupyter lab examples
```
