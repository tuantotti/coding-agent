"""Normalize LangGraph streaming into public text, activity, and final state."""

from collections.abc import AsyncIterator
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.types import Interrupt


class AgentGraph(Protocol):
    """Only the streaming graph capability required by the service."""

    def astream(
        self, input: Any, config: dict, **kwargs: Any
    ) -> AsyncIterator[tuple[tuple[str, ...], str, Any]]:
        """Stream LangGraph v1 frames including nested subgraphs."""
        ...


def assistant_text(message: BaseMessage) -> str:
    """Extract visible text while excluding reasoning and tool-call blocks."""
    if not isinstance(message, AIMessage):
        return ""
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block.get("text", "")
        for block in message.content
        if isinstance(block, dict)
        and block.get("type") in {"text", "output_text"}
        and isinstance(block.get("text"), str)
    )


class GraphStream:
    """Accumulate root state while forwarding normalized incremental events."""

    def __init__(self) -> None:
        """Start a fresh execution segment, including after a resume."""
        self.final_state: dict = {}
        self.interrupts: dict[str, Interrupt] = {}

    async def events(self, graph: AgentGraph, input: Any, config: dict):
        """Yield public events without exposing graph state or tool arguments."""
        async for namespace, mode, data in graph.astream(
            input,
            config,
            stream_mode=["messages", "updates", "values"],
            subgraphs=True,
            version="v1",
        ):
            agent_path = list(namespace)
            if mode == "messages":
                message, metadata = data
                text = assistant_text(message)
                if text:
                    yield (
                        "text_delta",
                        {
                            "text": text,
                            "message_id": message.id,
                            "agent": metadata.get("lc_agent_name")
                            or metadata.get("langgraph_node", "agent"),
                            "agent_path": agent_path,
                        },
                    )
            elif mode == "values" and not namespace:
                self.final_state = data
            elif mode == "updates":
                for interrupt in data.get("__interrupt__", ()):
                    self.interrupts[interrupt.id] = interrupt
                for node in data:
                    if node != "__interrupt__":
                        yield (
                            "agent_activity",
                            {
                                "agent": node,
                                "agent_path": agent_path,
                                "status": "updated",
                            },
                        )
        for interrupt in self.final_state.get("__interrupt__", ()):
            self.interrupts[interrupt.id] = interrupt

    def output(self) -> str:
        """Return the final root assistant text, not a specialist's result."""
        return next(
            (
                text
                for message in reversed(self.final_state.get("messages", []))
                if (text := assistant_text(message))
            ),
            "",
        )
