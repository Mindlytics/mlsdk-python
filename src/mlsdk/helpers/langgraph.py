"""Helper functions for LangGraph integration with Mindlytics."""

try:
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
except ImportError as e:
    raise ImportError(
        "mlsdk.helpers.langchain requires 'langchain'. "
        "Please install it with 'pip install langchain'."
    ) from e

import time
import uuid
import json
from typing import Any, Dict, Optional
from mlsdk import TokenBasedCost


class MLPostModellHook:
    """Post-model hook to capture conversation turns and tool calls after LLM response."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        """Initialize the post-model hook.

        Args:
            model_name (Optional[str]): The name of the model being used, if available.
        """
        self.function_calls: Dict[str, Any] = {}
        self.model_name = model_name

    async def __call__(self, state: Dict[str, Any], config: Dict[str, Any]) -> None:
        """Async post-model hook that runs after the LLM generates a response.

        Captures the most recent chat turn including human input, AI response, and tool calls.

        Args:
            state (Dict[str, Any]): The current state of the conversation, including messages.
            config (Dict[str, Any]): Configuration options, including session tracking.
        """
        messages = state.get("messages")
        if not messages:
            return

        # Find the last human message
        last_human_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                last_human_idx = i
                break

        if last_human_idx is None:
            return None

        # Collect all messages from the last human message onwards
        turn_messages = messages[last_human_idx:]

        # Parse the turn
        turn_data: Dict[str, Any] = {
            "user": None,
            "assistant": None,
            "tool_calls": {},
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model": self.model_name or "unknown",
            },
        }

        for msg in turn_messages:
            if isinstance(msg, HumanMessage):
                turn_data["user"] = msg.content

            elif isinstance(msg, AIMessage):
                # Extract tool calls if present
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_call_id = tool_call.get("id")
                        if tool_call_id is None:
                            continue
                        if self.function_calls.get(tool_call_id, None) is None:
                            self.function_calls[tool_call_id] = {
                                "name": tool_call.get("name"),
                                "args": json.dumps(tool_call.get("args", [])),
                                "started": int(time.time() * 1000),
                            }

                turn_data["assistant"] = msg.content

                usage = getattr(msg, "usage_metadata", None)
                if usage is not None:
                    turn_data["usage"]["prompt_tokens"] = usage.get("input_tokens", 0)
                    turn_data["usage"]["completion_tokens"] = usage.get(
                        "output_tokens", 0
                    )

                completed_function_calls = {}
                open_function_calls = {}
                for key, value in self.function_calls.items():
                    if value.get("result", None) is not None:
                        completed_function_calls[key] = value
                    else:
                        open_function_calls[key] = value
                turn_data["tool_calls"] = completed_function_calls
                self.function_calls = open_function_calls

            elif isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", None)
                if tool_call_id is not None:
                    if self.function_calls.get(tool_call_id, None) is not None:
                        self.function_calls[tool_call_id]["result"] = msg.content
                        self.function_calls[tool_call_id]["runtime"] = (
                            int(time.time() * 1000)
                            - self.function_calls[tool_call_id]["started"]
                        )

        if not turn_data:
            return

        if len(turn_data["assistant"]) == 0:
            return

        if config and config.get("configurable", None) is not None:
            session = config["configurable"].get("session", None)
            if session is not None:
                turn_id = str(uuid.uuid4())
                await session.track_conversation_turn(
                    user=turn_data["user"],
                    assistant=turn_data["assistant"],
                    usage=TokenBasedCost(**turn_data["usage"]),
                    properties={"turn_id": turn_id},
                )
                for tool_call_id, tc in turn_data["tool_calls"].items():
                    await session.track_function_call(
                        name=tc["name"],
                        args=tc["args"],
                        result=tc["result"],
                        runtime=tc["runtime"],
                        properties={"turn_id": turn_id},
                    )
