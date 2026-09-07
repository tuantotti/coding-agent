from dotenv import load_dotenv
from deepagents import create_deep_agent

# Load environment variables from .env file
load_dotenv()


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


# Use azure_openai:<your-deployment-name>
agent = create_deep_agent(
    model="azure_openai:gpt-5.4-nano",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

# Run the agent
response = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
)

print(response["messages"][-1].content)