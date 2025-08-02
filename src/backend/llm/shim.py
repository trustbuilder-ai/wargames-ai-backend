# A shim file to provide boiler plate for LLM-related functionality.


import json
from typing import Iterable, Literal, Optional
from backend.llm.agent import LLMAgent
from backend.llm.client import LLMClient
from backend.llm.tools import ToolRegistry
from backend.models.llm import ChatMessage, ChatEntry, ChatMessageWithTools, ChatRequest, ChatRequestWithTools, ChatResponse, ChatResponseWithTools
from backend.llm.config import llm_config
from backend.models.supplemental import Message

DEFAULT_CHAT_COMPLETION_MODEL: str = "gpt-4o-mini"


def map_chat_entries_to_messages(chat_entries: list[ChatEntry]) -> Iterable[Message]:
    for chat_entry in chat_entries:
        if isinstance(chat_entry, ChatMessageWithTools):
            if chat_entry.tool_calls is None:
                yield Message(
                    role=chat_entry.role,
                    content=chat_entry.content,
                )
            else:
                for tool_call in chat_entry.tool_calls:
                    yield Message(
                        role=chat_entry.role,
                        content=json.dumps(tool_call.function.arguments),
                        is_tool_call=True,
                        tool_name=tool_call.function.name
                    )
        elif isinstance(chat_entry, ChatResponseWithTools):
            if chat_entry.choices[0].message.tool_calls is None:
                yield Message(
                    role=chat_entry.choices[0].message.role,
                    content=chat_entry.choices[0].message.content,
                )
            else:
                for tool_call in chat_entry.choices[0].message.tool_calls:
                    yield Message(
                        role=chat_entry.choices[0].message.role,
                        content=json.dumps(tool_call.function.arguments),
                        is_tool_call=False,
                        tool_name=tool_call.function.name
                    )
        elif isinstance(chat_entry, ChatMessage):
            yield Message(
                role=chat_entry.role,
                content=chat_entry.content,
            )
        elif isinstance(chat_entry, ChatResponse): # type: ignore
            yield Message(
                role=chat_entry.choices[0].message.role,
                content=chat_entry.choices[0].message.content,
            )
        else:
            raise TypeError(f"Unsupported chat entry type: {type(chat_entry)}")


def map_chat_response_with_tools(item: ChatResponseWithTools) -> ChatMessageWithTools:
    assert isinstance(item, ChatResponseWithTools), "Item must be a ChatResponseWithTools"
    # Mutate the object
    return ChatMessageWithTools(
        role=item.choices[0].message.role,
        content=item.choices[0].message.content,
        tool_calls=item.choices[0].message.tool_calls,
        tool_call_id=item.choices[0].message.tool_call_id,
    )


def map_chat_response(item: ChatEntry) -> ChatMessage:
    assert isinstance(item, ChatResponse), "Item must be a ChatResponse"
    # Mutate the object
    return ChatMessage(
        role=item.choices[0].message.role, # type: ignore
        content=item.choices[0].message.content,
    )


async def send_shim_request(message: str,
                            role: Literal["user", "assistant", "system"] = "user") -> ChatResponse:
    """
    This is a wrapper around the more complex functions to provide a standard interface.
    The raw data types are stored in the db.
    """
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
    return response  # type: ignore