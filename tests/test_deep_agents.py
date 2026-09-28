"""Manual smoke script, not a pytest test.

Run directly, e.g. ``uv run python tests/test_deep_agents.py``. Guarded by
``__main__`` so pytest can collect this file (matches the ``test_*.py`` glob)
without making a real Azure OpenAI call, which would fail collection without
credentials.
"""

from deepagents import create_deep_agent
from dotenv import load_dotenv


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


def main() -> None:
    """Build a minimal deep agent and print its response to a sample query."""
    load_dotenv()

    # Use azure_openai:<your-deployment-name>
    agent = create_deep_agent(
        model="azure_openai:gpt-5.4-nano",
        tools=[get_weather],
        system_prompt="You are a helpful assistant",
    )

    response = agent.invoke(
        {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
    )
    print(response["messages"][-1].content)


if __name__ == "__main__":
    main()