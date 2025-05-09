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
