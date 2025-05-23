"""Helper functions for LangChain integration with Mindlytics."""

try:
    from langchain_core.callbacks import AsyncCallbackHandler
    from langchain_core.outputs import LLMResult, ChatGeneration
    from langchain_core.messages import HumanMessage
except ImportError as e:
    raise ImportError(
        "mlsdk.helpers.langchain requires 'langchain'. "
        "Please install it with 'pip install langchain'."
    ) from e

from mlsdk import Session, TokenBasedCost


class MLChatRecorderCallback(AsyncCallbackHandler):
    """Callback handler to record conversation turns and token usage."""

    def __init__(self, session: Session) -> None:
        """Initialize the callback with a Mindlytics session.

        Args:
            session (Session): The Mindlytics session object.
        """
        self.session: Session = session  # Take the session and remember it
        self.current_user_input = ""

    async def on_chat_model_start(
        self,
        serialized,
        messages,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ):
        """Called when the chat model starts.  Capture the user input."""
        for message in reversed(messages[0]):
            if isinstance(message, HumanMessage):
                self.current_user_input = message.content
                break

    async def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Called when LLM finishes - record the conversation turn."""
        token_usage = {}
        assistant_response = ""

        # Extract the assistant response from the LLM result
        try:
            gen = response.generations[0][0]
            if isinstance(gen, ChatGeneration):
                content = gen.message.content
                if not isinstance(content, str):
                    assistant_response = str(content)
                else:
                    assistant_response = content
                usage_metadata = getattr(gen.message, "usage_metadata", {}) or {}
            else:
                assistant_response = getattr(
                    gen, "text", "No assistant response available."
                )
                usage_metadata = {}
        except Exception as e:
            print(f"Error extracting response: {e}")
            assistant_response = "No assistant response available."
            usage_metadata = {}

        # Extract token usage from the response
        try:
            generation_info = getattr(gen, "generation_info", {}) or {}
            token_usage = {
                "model": generation_info.get("model_name", ""),
                "prompt_tokens": usage_metadata.get("input_tokens", 0),
                "completion_tokens": usage_metadata.get("output_tokens", 0),
            }
        except Exception:
            token_usage = {
                "model": "unknown",
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        # Send the information to Mindlytics
        try:
            await self.session.track_conversation_turn(
                user=self.current_user_input,
                assistant=assistant_response,
                usage=TokenBasedCost(**token_usage),
            )
        except Exception as e:
            print(f"Error sending conversation turn: {e}")
