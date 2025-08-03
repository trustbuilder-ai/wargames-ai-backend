"""
This file is the sole LLM access point for the Challenge API. The intent of
which is to provide a standard interface for the LLM client and agentic
interactions.
"""
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
    """
    Maps chat entries, which contain the full OpenAI chat message format(s), to simple
    Message objects for easier handling in the UI and in logical inspection.
    """
    for chat_entry in chat_entries:
        if isinstance(chat_entry, ChatMessageWithTools):
            tool_call_id = chat_entry.tool_call_id if chat_entry.tool_call_id else None
            if chat_entry.tool_calls is None:
                yield Message(
                    role=chat_entry.role,
                    content=chat_entry.content,
                    tool_call_id=tool_call_id
                )
            else:
                yield Message(
                    role=chat_entry.role,
                    content=json.dumps([tool_call.function.arguments for tool_call in chat_entry.tool_calls]),
                    is_tool_call=True,
                    tool_calls = chat_entry.tool_calls,
                    #tool_call_id=chat_entry.tool_calls[0].id if chat_entry.tool_calls else None
                )
        elif isinstance(chat_entry, ChatResponseWithTools):
            if chat_entry.choices[0].message.tool_calls is None:
                yield Message(
                    role=chat_entry.choices[0].message.role,
                    content=chat_entry.choices[0].message.content,
                )
            else:
                yield Message(
                    role=chat_entry.choices[0].message.role,
                    content="",
                    is_tool_call=False,
                    tool_calls=chat_entry.choices[0].message.tool_calls,
                    tool_call_id=chat_entry.choices[0].message.tool_call_id
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


def map_message_to_chat_message(message: Message) -> ChatMessage:
    """
    Maps a Message object to a ChatMessage object.
    """
    return ChatMessage(
        role=message.role, # type: ignore
        content=message.content,
    )


def map_message_to_chat_message_with_tools(message: Message) -> ChatMessageWithTools:
    """
    Maps a Message object to a ChatMessageWithTools object.
    This is used for messages that may include tool calls.
    """
    return ChatMessageWithTools(
        role=message.role, # type: ignore
        content=message.content,
        tool_calls=message.tool_calls,
        tool_call_id=message.tool_call_id
    )


async def send_shim_request(message: str, context: Optional[list[Message]] = None,
                            role: Literal["user", "assistant", "system"] = "user") -> ChatResponse:
    """
    Send a message to the chat API.

    Args:
        message (str): The message to send.
        context (Optional[list[Message]], optional): List of context messages to include. Defaults to None.
        role (Literal["user", "assistant", "system"], optional): Role of the sender. Defaults to "user".

    Returns:
        ChatResponse: The chat response from the API.
    """
    client: LLMClient = LLMClient()
    messages: list[ChatMessage] = [ChatMessage(
        role=role,
        content=message
    )]
    if context:
        messages.extend(map_message_to_chat_message(m) for m in context)
    chat_request: ChatRequest = ChatRequest(
       model=DEFAULT_CHAT_COMPLETION_MODEL,
       messages=messages
    )
    return await client.chat_completion(chat_request)


async def send_shim_request_with_tools(message: str, tools: list[str], context: Optional[list[Message]] = None,
                                       role: Literal["user", "assistant", "system"] = "user", )  -> list[ChatResponseWithTools|ChatMessageWithTools]:
    """Send a message with tools to the chat API.

    Args:
        message (str): The message to send.
        tools (list[str]): List of tool names to use in the request.
        context (Optional[list[Message]], optional): List of context messages to include. Defaults to None.
        role (Literal["user", "assistant", "system"], optional): Role of the sender. Defaults to "user".

    Returns:
        list[ChatResponseWithTools|ChatMessageWithTools]: List of chat responses or messages with tools.
    """
    tool_registry: Optional[ToolRegistry] = llm_config.get_tool_registry(allowed_tools=tools)
    assert tool_registry is not None, "Tool registry must e initialized in LLMConfig"
    client: LLMClient = LLMClient()

    messages: list[ChatMessageWithTools] = [ChatMessageWithTools(
        role=role,
        content=message
    )]
    if context:
        messages.extend(map_message_to_chat_message_with_tools(m) for m in context)
    agent: LLMAgent = LLMAgent(client, tool_registry, max_iterations = 2)
    response: list[ChatResponseWithTools|ChatMessageWithTools] = await agent.chat_with_tools(
        ChatRequestWithTools(
            model=DEFAULT_CHAT_COMPLETION_MODEL,
            messages=messages,
        )
    )
    return response  # type: ignore