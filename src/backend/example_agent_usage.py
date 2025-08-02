#!/usr/bin/env python3
"""Example usage of the LLM Agent with tool calling capabilities.

This script demonstrates how to use the backend LLM infrastructure
with agentic tool-calling capabilities.
"""

import asyncio
import json
from typing import Any

from backend.llm.agent import LLMAgent
from backend.llm.client import LLMClient
from backend.llm.config import llm_config
from backend.llm.tools import create_example_tools
from backend.models.llm import (
    ChatMessageWithTools,
    ChatRequestWithTools,
)
from backend.util.log import logger


def print_conversation_turn(turn_num: int, message: str, response: Any) -> None:
    """Pretty print a conversation turn."""
    print(f"\n{'='*60}")
    print(f"Turn {turn_num}")
    print(f"{'='*60}")
    print(f"\n👤 User: {message}")
    
    if hasattr(response, "choices") and response.choices:
        assistant_msg = response.choices[0].message
        
        # Print assistant's text response
        if assistant_msg.content:
            print(f"\n🤖 Assistant: {assistant_msg.content}")
        
        # Print any tool calls
        if assistant_msg.tool_calls:
            print("\n🔧 Tool Calls:")
            for tc in assistant_msg.tool_calls:
                print(f"  • {tc.function.name}({tc.function.arguments})")


async def example_basic_tool_usage():
    """Example: Basic tool usage with mock tools."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Tool Usage with Mock Tools")
    print("="*80)
    
    # Initialize components
    client = LLMClient()
    
    # Check if we have tools configured
    tool_registry = llm_config.get_tool_registry()
    if not tool_registry:
        print("No tools configured in llm_config.yaml, using example tools")
        tool_registry = create_example_tools()
    
    # Create agent
    agent = LLMAgent(client, tool_registry)
    
    # Create a request
    messages = [
        ChatMessageWithTools(
            role="user",
            content="What's the weather in San Francisco and calculate 15 + 27 for me?"
        )
    ]
    
    request = ChatRequestWithTools(
        model=llm_config.default_model,
        messages=messages,
        temperature=0.7,
    )
    
    # Execute with tools
    print(f"\n📡 Using model: {request.model}")
    print(f"🔧 Available tools: {tool_registry.get_tool_names()}")
    
    response = await agent.chat_with_tools(request, mock_mode=True)
    
    print_conversation_turn(1, messages[0].content, response)
    
    # Show summary
    summary = agent.get_conversation_summary()
    print(f"\n📊 Conversation Summary:")
    print(f"  • Total turns: {summary['total_turns']}")
    print(f"  • Tool calls: {summary['total_tool_calls']}")
    print(f"  • Tools used: {summary['tool_usage']}")


async def example_multi_turn_conversation():
    """Example: Multi-turn conversation with context."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Multi-turn Conversation")
    print("="*80)
    
    # Initialize
    client = LLMClient()
    tool_registry = llm_config.get_tool_registry() or create_example_tools()
    agent = LLMAgent(client, tool_registry)
    
    # Conversation flow
    conversations = [
        "Search for information about Python async programming",
        "Based on what you found, what's the main benefit of using async?",
        "Calculate 1000 / 25 to see how many requests we could handle per second"
    ]
    
    messages = []
    
    for i, user_msg in enumerate(conversations, 1):
        # Add user message
        messages.append(ChatMessageWithTools(role="user", content=user_msg))
        
        # Create request with full history
        request = ChatRequestWithTools(
            model=llm_config.default_model,
            messages=messages,
        )
        
        # Get response
        response = await agent.chat_with_tools(request, mock_mode=True)
        
        print_conversation_turn(i, user_msg, response)
        
        # Add assistant response to history
        if response.choices:
            messages.append(response.choices[0].message)
            
            # Add tool responses if any
            for turn in agent.conversation_history:
                if turn.tool_results:
                    for result in turn.tool_results:
                        messages.append(ChatMessageWithTools(
                            role="tool",
                            content=result.output or result.error or "",
                            tool_call_id=result.tool_call_id,
                        ))


async def example_no_tools_fallback():
    """Example: Models without tool support fall back gracefully."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Fallback for Models Without Tool Support")
    print("="*80)
    
    client = LLMClient()
    tool_registry = create_example_tools()
    agent = LLMAgent(client, tool_registry)
    
    # Use a model that doesn't support tools
    messages = [
        ChatMessageWithTools(
            role="user",
            content="Tell me a joke about programming"
        )
    ]
    
    request = ChatRequestWithTools(
        model="huggingface/microsoft/DialoGPT-large",  # Doesn't support tools
        messages=messages,
    )
    
    print(f"\n📡 Using model: {request.model}")
    print("⚠️  This model doesn't support tool calling")
    
    try:
        response = await agent.chat_with_tools(request)
        print_conversation_turn(1, messages[0].content, response)
    except Exception as e:
        print(f"\n❌ Error: {e}")


async def example_manual_tool_control():
    """Example: Manual control over tool execution."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Manual Tool Control")
    print("="*80)
    
    client = LLMClient()
    tool_registry = create_example_tools()
    agent = LLMAgent(client, tool_registry)
    
    messages = [
        ChatMessageWithTools(
            role="user",
            content="What tools do you have available? List them but don't use them yet."
        )
    ]
    
    request = ChatRequestWithTools(
        model=llm_config.default_model,
        messages=messages,
        tool_choice="none",  # Prevent automatic tool use
    )
    
    print(f"\n📡 Using model: {request.model}")
    print("🚫 Tool choice: none (manual control)")
    
    response = await agent.chat_with_tools(
        request,
        auto_execute_tools=False  # Don't auto-execute even if called
    )
    
    print_conversation_turn(1, messages[0].content, response)


async def main():
    """Run all examples."""
    print("\n🚀 LLM Agent Tool-Calling Examples")
    print("=" * 80)
    
    # Check configuration
    if not llm_config.list_available_models():
        print("\n⚠️  Warning: No models available. Please set API keys:")
        print("  - OPENAI_API_KEY for OpenAI models")
        print("  - ANTHROPIC_API_KEY for Anthropic models")
        print("  - etc.")
        return
    
    print(f"\n✅ Available models: {[m.id for m in llm_config.list_available_models()]}")
    
    # Run examples
    try:
        await example_basic_tool_usage()
        await example_multi_turn_conversation()
        await example_no_tools_fallback()
        await example_manual_tool_control()
        
        print("\n" + "="*80)
        print("✅ All examples completed successfully!")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())