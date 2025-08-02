# A shim file to provide boiler plate for LLM-related functionality.


from typing import Literal, Optional
from backend.llm.agent import LLMAgent
from backend.llm.client import LLMClient
from backend.llm.tools import ToolRegistry
from backend.models.llm import ChatMessage, ChatMessageWithTools, ChatRequest, ChatRequestWithTools, ChatResponse, ChatResponseWithTools
from backend.llm.config import llm_config

DEFAULT_CHAT_COMPLETION_MODEL: str = "gpt-4o-mini"


async def send_shim_request(message: str,
                            role: Literal["user", "assistant", "system"] = "user") -> ChatResponse:
    client: LLMClient = LLMClient()
    chat_request: ChatRequest = ChatRequest(
       model=DEFAULT_CHAT_COMPLETION_MODEL,
       messages = [
            ChatMessage(
                role=role,
                content=message
            ),
       ]
    )
    return await client.chat_completion(chat_request)


async def send_shim_request_with_tools(message: str, tools: list[str],
                                      role: Literal["user", "assistant", "system"] = "user") -> list[ChatResponseWithTools|ChatMessageWithTools]:
    tool_registry: Optional[ToolRegistry] = llm_config.get_tool_registry(allowed_tools=tools)
    assert tool_registry is not None, "Tool registry must be initialized in LLMConfig"
    #for tool_name, tool in tool_registry._tools.items():
        #assert isinstance(tool, ToolFunction), f"Tool must be a ToolFunction instance. Found: {type(tool)}"
        #print(f"Tool: {tool.name}, Description: {tool.description}")
    assert tool_registry is not None, "Tool registry must be initialized in LLMConfig"
    client: LLMClient = LLMClient()
    agent: LLMAgent = LLMAgent(client, tool_registry, max_iterations = 2)
    response: list[ChatResponseWithTools|ChatMessageWithTools] = await agent.chat_with_tools(
        ChatRequestWithTools(
            model=DEFAULT_CHAT_COMPLETION_MODEL,
            messages = [
                ChatMessageWithTools(
                    role = role,
                    content = message
                )
            ],
        )
    )
    return response