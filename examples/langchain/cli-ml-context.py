#!/usr/bin/env python3
"""
Async LangChain CLI application using GPT-4o-mini with streaming output.
This example demonstrates how to use the Mindlytics SDK with LangChain to create a
chat application that records conversations and events.
It uses the Mindlytics API to track events and errors during the conversation.
"""

import os
import sys
import asyncio
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.callbacks import AsyncCallbackHandler

# import Mindlytics API client
from mlsdk import Client, Session, MLEvent

# import mindlytics llm callback handler for langchain
from mlsdk.helpers.langchain import MLChatRecorderCallback

# to get a unique device id for a session
import uuid


class AsyncStreamingCallbackHandler(AsyncCallbackHandler):
    """Custom async callback handler for streaming output to stdout."""

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called when a new token is generated."""
        print(token, end="", flush=True)


def initialize_llm(session: Session):
    """Initialize the ChatOpenAI model with async streaming enabled.

    Args:
        session (Session): The Mindlytics session object.
    """
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)

    # Initialize the LLM with async streaming callback
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        streaming=True,
        # Add this to enable token counts from OpenAI, which we can send to Mindlytics in ConversationRecorderCallback
        model_kwargs={
            "stream_options": {"include_usage": True},
        },
        callbacks=[
            AsyncStreamingCallbackHandler(),
            MLChatRecorderCallback(session),  # Add the conversation recorder callback
        ],
    )

    return llm


async def get_user_input(prompt: str) -> str:
    """Get user input asynchronously."""
    # Run input() in a thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)


async def chat_loop(llm):
    """Main async chat loop that prompts for input and streams responses."""
    print("Async LangChain CLI Chat Application")
    print("Using GPT-4o-mini with streaming output")
    print("Type 'quit', 'exit', or press Ctrl+C to exit\n")

    message_history: List[BaseMessage] = []

    while True:
        try:
            # Get user input asynchronously
            user_input = await get_user_input("You: ")
            user_input = user_input.strip()

            # Check for exit commands
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            # Skip empty input
            if not user_input:
                continue

            # Create message and send to LLM
            message = HumanMessage(content=user_input)
            message_history.append(message)
            print("Assistant: ", end="", flush=True)

            # Stream the response asynchronously
            response = await llm.ainvoke(message_history)
            if hasattr(response, "content"):
                assistant_message = AIMessage(content=response.content)
                message_history.append(assistant_message)

            print("\n")  # Add newline after streaming response

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try again.\n")


async def main():
    api_key = os.getenv("MLSDK_API_KEY")
    project_id = os.getenv("MLSDK_PROJECT_ID")
    # Need a unique device id for the session
    mac = uuid.getnode()
    device_id = f"{mac:012x}"

    # REMOVE ME!!
    server_endpoint = os.getenv("SERVER_BASE")
    wss_endpoint = os.getenv("WSS_BASE")

    if not api_key or not project_id:
        print(
            "Error: MLSDK_API_KEY and MLSDK_PROJECT_ID environment variables must be set."
        )
        sys.exit(1)

    # callbacks to gather Mindlytics events and errors
    ml_events: List[MLEvent] = []

    async def on_event(event: MLEvent):
        # Handle Mindlytics events here
        ml_events.append(event)

    ml_errors: List[Exception] = []

    async def on_error(error: Exception):
        # Handle Mindlytics errors here
        ml_errors.append(error)

    """Main async function to run the CLI application."""
    try:
        # Initialize the Mindlytics client
        ml_client = Client(
            api_key=api_key,
            project_id=project_id,
            server_endpoint=server_endpoint,
            wss_endpoint=wss_endpoint,
        )
        # Create a session context.
        session_context = ml_client.create_session(
            device_id=device_id,
            on_event=on_event,
            on_error=on_error,
        )

        # Start the session
        async with session_context as session:
            # Initialize the LLM with the session context
            llm = initialize_llm(session)

            # Start the async chat loop
            await chat_loop(llm)

        # Print out Mindlytics events and errors
        print()
        print("Mindlytics Events:")
        for event in ml_events:
            if event.origin_event_id is not None:
                print("  ", event.event)
            else:
                print(event.event)
            if event.event == "Conversation Summary":
                # print each key/value in properties
                for key, value in event.properties.items():
                    print(f"    {key}: {value}")
        if len(ml_errors) > 0:
            print()
            print("Mindlytics Errors:")
            for error in ml_errors:
                print("------------------------------------------------")
                print(error)

    except Exception as e:
        print(f"Failed to initialize application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
