#!/usr/bin/env python3
"""
Async LangChain CLI application using GPT-4o-mini with streaming output.
"""

import os
import sys
import asyncio
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.callbacks import AsyncCallbackHandler


class AsyncStreamingCallbackHandler(AsyncCallbackHandler):
    """Custom async callback handler for streaming output to stdout."""

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called when a new token is generated."""
        print(token, end="", flush=True)


def initialize_llm():
    """Initialize the ChatOpenAI model with async streaming enabled."""
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
        callbacks=[AsyncStreamingCallbackHandler()],
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
    """Main async function to run the CLI application."""
    try:
        # Initialize the LLM
        llm = initialize_llm()

        # Start the async chat loop
        await chat_loop(llm)

    except Exception as e:
        print(f"Failed to initialize application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
