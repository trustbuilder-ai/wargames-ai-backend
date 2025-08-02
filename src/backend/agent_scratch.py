import pprint
from typing import Optional
from backend.llm.agent import LLMAgent
from backend.llm.config import llm_config
from backend.llm.tools import ToolRegistry
from backend.llm.client import LLMClient
from backend.models.llm import ChatRequestWithTools, ChatMessageWithTools, ChatResponseWithTools, ToolCall, ToolFunction



async def main():
    tool_registry: Optional[ToolRegistry] = llm_config.get_tool_registry(allowed_tools=["weather", "calculator"])
    assert tool_registry is not None, "Tool registry must be initialized in LLMConfig"
    #for tool_name, tool in tool_registry._tools.items():
        #assert isinstance(tool, ToolFunction), f"Tool must be a ToolFunction instance. Found: {type(tool)}"
        #print(f"Tool: {tool.name}, Description: {tool.description}")
    assert tool_registry is not None, "Tool registry must be initialized in LLMConfig"
    client: LLMClient = LLMClient()
    agent: LLMAgent = LLMAgent(client, tool_registry, max_iterations = 2)
    response: ChatResponseWithTools = await agent.chat_with_tools(
        ChatRequestWithTools(
            model="gpt-4o",
            messages = [
                ChatMessageWithTools(
                    role="user",
                    content="What's the weather in San Francisco?"
                )
            ],
        )
    ) # type: ignore

    for element in response:
        assert isinstance(element, (ChatResponseWithTools, ChatMessageWithTools)), "Response must be a ChatResponseWithTools or ChatMessageWithTools"

    print("Response:")
    pprint.pprint([r.model_dump() for r in response], indent=2)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
