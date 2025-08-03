"""LLM Agent with tool-calling capabilities.

This module extends the base LLMClient with agentic capabilities,
enabling tool calling and multi-turn conversations with tool execution.
"""

from typing import Any

import litellm

from backend.llm.client import LLMClient
from backend.llm.tools import ToolRegistry
from backend.models.llm import (
    ChatMessageWithTools,
    ChatRequestWithTools,
    ChatResponseWithTools,
    ChatChoiceWithTools,
    ChatUsage,
    ConversationTurn,
    ToolCall,
    FunctionCall,
    ToolExecutionResult,
)
from backend.util.log import logger


class LLMAgent:
    """Agent that extends LLMClient with tool-calling capabilities.

    This agent manages:
    - Tool-augmented conversations with LLMs
    - Automatic tool execution loops
    - Conversation history with tool interactions
    - Support for both mock and real tool execution
    """

    def __init__(
        self,
        client: LLMClient,
        tool_registry: ToolRegistry,
        max_iterations: int = 10,
    ):
        """Initialize the LLM Agent.

        Args:
            client: The base LLM client for making API calls.
            tool_registry: Registry of available tools.
            max_iterations: Maximum tool-calling iterations to prevent infinite loops.
        """
        self.client = client
        self.tools = tool_registry
        self.max_iterations = max_iterations
        self.conversation_history: list[ConversationTurn] = []

    async def chat_with_tools(
        self,
        request: ChatRequestWithTools,
        mock_mode: bool = True,
        auto_execute_tools: bool = True,
    ) -> list[ChatResponseWithTools|ChatMessageWithTools]:
        """Execute a chat completion with tool calling support.

        Args:
            request: The chat request with optional tool definitions.
            mock_mode: Use mock tool responses even for real tools.
            auto_execute_tools: Automatically execute tool calls and continue conversation.

        Returns:
            The final response after all tool executions.

        Raises:
            LLMAPIError: If the LLM API call fails.
            ValueError: If max iterations exceeded.
        """
        # Add available tools to the request if not provided
        if request.tools is None:
            request.tools = self.tools.get_tool_definitions()

        # Ensure we have tool support for the model
        if not self._model_supports_tools(request.model):
            logger.warning(
                f"Model '{request.model}' may not support tool calling. "
                "Proceeding with standard completion."
            )
            # Fall back to regular completion
            return [await self._standard_completion(request)]

        # Execute the tool-calling loop
        current_messages: list[ChatMessageWithTools|ChatResponseWithTools] = list(request.messages)

        # Create request with current messages
        current_request = ChatRequestWithTools(
            model=request.model,
            messages=list(request.messages),
            tools=request.tools,
            tool_choice=request.tool_choice,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,  # Tool calling doesn't support streaming
            user=request.user,
        )

        # Make the API call
        response = await self._make_tool_aware_request(current_request)
        # Check if any tools were called
        tool_calls = self._extract_tool_calls(response)

        if not tool_calls or not auto_execute_tools:
            # No tools called or auto-execution disabled, return the response
            return [response]

        # Execute the tool calls
        tool_results = await self._execute_tool_calls(tool_calls, mock_mode)

        response_messages: list[ChatMessageWithTools|ChatResponseWithTools] = []

        # Add assistant message with tool calls to history
        assistant_message: ChatMessageWithTools = response.choices[0].message
        response_messages.append(assistant_message)

        # Add tool results to messages
        for result in tool_results:
            tool_message: ChatMessageWithTools = ChatMessageWithTools(
                role="tool",
                content=result.output or result.error or "No output",
                tool_call_id=result.tool_call_id,
            )
            response_messages.append(tool_message)

        return response_messages

    async def _make_tool_aware_request(
        self,
        request: ChatRequestWithTools,
    ) -> ChatResponseWithTools:
        """Make a request to the LLM with tool definitions.

        Args:
            request: The request with tools.

        Returns:
            Response with potential tool calls.
        """
        # Convert our extended request to LiteLLM format
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
                **({"tool_calls": [self._tool_call_to_dict(tc) for tc in msg.tool_calls]} 
                   if msg.tool_calls else {}),
            }
            for msg in request.messages
        ]

        # Convert tools to LiteLLM format
        tools = None
        if request.tools:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]

        # Prepare the LiteLLM call
        llm_params = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if tools:
            llm_params["tools"] = tools
            if request.tool_choice:
                llm_params["tool_choice"] = request.tool_choice

        logger.info(f"Making tool-aware request to {request.model}")

        # Make the API call via LiteLLM
        response = await litellm.acompletion(**llm_params)

        # Convert response to our format
        return self._convert_tool_response(response)

    def _convert_tool_response(self, litellm_response: Any) -> ChatResponseWithTools:
        """Convert LiteLLM response to our tool-aware format.

        Args:
            litellm_response: Raw response from LiteLLM.

        Returns:
            Our standardized tool-aware response.
        """
        choices = []

        for choice in litellm_response.choices:
            message = choice.message

            # Extract tool calls if present
            tool_calls = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type="function",
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in message.tool_calls
                ]

            # Create the message
            msg = ChatMessageWithTools(
                role=message.role,
                content=message.content or "",
                tool_calls=tool_calls,
            )

            # Create the choice
            choice_data = ChatChoiceWithTools(
                index=choice.index,
                message=msg,
                finish_reason=choice.finish_reason,
            )
            choices.append(choice_data)

        # Convert usage if present
        usage = None
        if hasattr(litellm_response, "usage") and litellm_response.usage:
            # Use model_dump with include filter to extract only the fields we need
            usage_data = litellm_response.usage.model_dump(
                include={"prompt_tokens", "completion_tokens", "total_tokens"}
            )
            usage = ChatUsage.model_validate(usage_data)

        # Build the response
        return ChatResponseWithTools(
            id=litellm_response.id,
            object=litellm_response.object,
            created=litellm_response.created,
            model=litellm_response.model,
            choices=choices,
            usage=usage,
        )

    def _extract_tool_calls(self, response: ChatResponseWithTools) -> list[ToolCall]:
        """Extract tool calls from the response.

        Args:
            response: The LLM response.

        Returns:
            List of tool calls, empty if none found.
        """
        if not response.choices:
            return []

        message = response.choices[0].message
        return message.tool_calls or []

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        mock_mode: bool,
    ) -> list[ToolExecutionResult]:
        """Execute a list of tool calls.

        Args:
            tool_calls: List of tool calls to execute.
            mock_mode: Use mock execution.

        Returns:
            List of execution results.
        """
        results = []

        for tool_call in tool_calls:
            result = await self.tools.execute_tool(
                tool_name=tool_call.function.name,
                arguments=tool_call.function.arguments,
                tool_call_id=tool_call.id,
                mock_mode=mock_mode,
            )
            results.append(result)

        return results

    async def _standard_completion(
        self,
        request: ChatRequestWithTools,
    ) -> ChatResponseWithTools:
        """Fall back to standard completion without tools.

        Args:
            request: The request (tools will be ignored).

        Returns:
            Standard response wrapped in tool-aware format.
        """
        # Convert to standard request
        from backend.models.llm import ChatRequest, ChatMessage

        standard_messages = [
            ChatMessage(role=msg.role, content=msg.content, name=msg.name)
            for msg in request.messages
            if msg.role in ["user", "assistant", "system"]
        ]

        standard_request = ChatRequest(
            model=request.model,
            messages=standard_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
            user=request.user,
        )

        # Make standard call
        standard_response = await self.client.chat_completion(standard_request)

        # Convert to tool-aware format
        choices = []
        for choice in standard_response.choices:
            msg = ChatMessageWithTools(
                role=choice.message.role,
                content=choice.message.content,
                tool_calls=None,
            )
            extended_choice = ChatChoiceWithTools(
                index=choice.index,
                message=msg,
                finish_reason=choice.finish_reason,
            )
            choices.append(extended_choice)

        return ChatResponseWithTools(
            id=standard_response.id,
            object=standard_response.object,
            created=standard_response.created,
            model=standard_response.model,
            choices=choices,
            usage=standard_response.usage,
        )


    def _model_supports_tools(self, model: str) -> bool:
        """Check if a model supports tool calling.

        Args:
            model: Model identifier.

        Returns:
            True if model likely supports tools.
        """
        # Models known to support function/tool calling
        tool_capable_models = {
            "gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo",
            "claude-3", "claude-3.5",
            "github/gpt-4o",
        }

        # Check if model matches known patterns
        model_lower = model.lower()
        return any(
            pattern in model_lower
            for pattern in tool_capable_models
        )

    def _tool_call_to_dict(self, tool_call: ToolCall) -> dict[str, Any]:
        """Convert ToolCall to dictionary format for LiteLLM.

        Args:
            tool_call: The tool call object.

        Returns:
            Dictionary representation.
        """
        return {
            "id": tool_call.id,
            "type": tool_call.type,
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
        }

    def get_conversation_summary(self) -> dict[str, Any]:
        """Get a summary of the conversation history.

        Returns:
            Summary statistics and information.
        """
        total_turns = len(self.conversation_history)
        total_tool_calls = sum(
            len(turn.tool_results) if turn.tool_results else 0
            for turn in self.conversation_history
        )

        tool_usage = {}
        for turn in self.conversation_history:
            if turn.tool_results:
                for result in turn.tool_results:
                    # Extract tool name from the turn's response
                    for choice in turn.response.choices:
                        if choice.message.tool_calls:
                            for tc in choice.message.tool_calls:
                                if tc.id == result.tool_call_id:
                                    tool_name = tc.function.name
                                    tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1

        return {
            "total_turns": total_turns,
            "total_tool_calls": total_tool_calls,
            "tool_usage": tool_usage,
            "models_used": list(set(turn.request.model for turn in self.conversation_history)),
        }

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")