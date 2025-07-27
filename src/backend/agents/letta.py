from functools import cache
from typing import Any
import backend.database.connection as connlib
from sqlmodel import Session
from backend.database.locking import Locker
from time import sleep

from letta_client import Letta
import os


LETTA_PROJECT_NAME: str = "trustbuilder-ai"


@cache
def get_letta_client():
    client = Letta(project=LETTA_PROJECT_NAME, token=os.environ.get("LETTA_API_KEY"))
    return client

def send_message_and_check_tools(agent_id: str, message: str):
    # Send message to agent
    response = get_letta_client().agents.messages.create(
        agent_id=agent_id,
        messages=[
            {
                "role": "user",
                "content": message
            }
        ]
    )
    
    # Check for tool calls in the response
    tool_was_called = False
    tool_calls = []
    tool_results = []
    
    for msg in response.messages:
        # Check message type for tool calls
        if msg.message_type == 'tool_call_message':
            tool_was_called = True
            tool_calls.append({
                'name': msg.tool_call.name,
                'arguments': msg.tool_call.arguments,
                'id': msg.tool_call.tool_call_id
            })
        
        # Check for tool results
        elif msg.message_type == 'tool_return_message':
            tool_results.append({
                'tool_name': msg.name,
                'result': msg.tool_return,
                'status': msg.status,
                'tool_call_id': msg.tool_call_id
            })
        
        # Hidden reasoning messages (omitted by default)
        elif msg.message_type == 'hidden_reasoning_message':
            # These are typically omitted unless specifically requested
            pass
    
    return {
        'tool_was_called': tool_was_called,
        'tool_calls': tool_calls,
        'tool_results': tool_results,
        'response': response
    }


def create_agent(name: str, agent_template: str):
    agent = get_letta_client().agents.create(
        name="theagent",
        model="openai/o4-mini-2025-04-16",  # Using the provider/model-name format
        embedding="openai/text-embedding-3-small",  # Embedding model
        # Memory configuration
        memory_blocks=[],
        # System prompt (optional - will use default if not specified)
        system="You are a helpful AI assistant. Be concise and informative in your responses.",
        # Context window configuration
        # Include core Letta tools
        include_base_tools=False,  # Includes memory management tools
        # Optional: Add specific tools
        tools=["roll_d20"],
        # Optional: Initial conversation
        initial_message_sequence=[
            {
                "role": "system",
                "content": "Welcome! I'm ready to help you."
            }
        ],
        # Optional: Description and metadata
        description="A ChatGPT 3.5 powered assistant for general conversation",
    )
    return agent