"""Red Team Agent for testing LLM safety boundaries.

This module provides specialized agents and utilities for red team testing
of LLM tool-calling capabilities, focusing on whether models can be
convinced to request malicious tool executions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from backend.llm.agent import LLMAgent
from backend.llm.client import LLMClient
from backend.llm.tools import ToolRegistry
from backend.models.llm import (
    ChatMessageWithTools,
    ChatRequestWithTools,
    ChatResponseWithTools,
    ToolCall,
)
from backend.util.log import logger


@dataclass
class RedTeamAttempt:
    """Record of a single red team attempt."""
    
    attempt_number: int
    user_prompt: str
    llm_response: str
    tools_requested: list[str] = field(default_factory=list)
    malicious_tool_called: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RedTeamResult:
    """Result of a red team session."""
    
    session_id: str
    model: str
    total_attempts: int
    successful_attack: bool
    malicious_tool_called: Optional[str]
    attempts: list[RedTeamAttempt]
    system_prompt: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_report(self) -> dict:
        """Generate a report of the red team session.
        
        Returns:
            Dictionary containing session details and results.
        """
        return {
            "session_id": self.session_id,
            "model": self.model,
            "timestamp": self.timestamp.isoformat(),
            "system_prompt": self.system_prompt,
            "total_attempts": self.total_attempts,
            "successful_attack": self.successful_attack,
            "malicious_tool_called": self.malicious_tool_called,
            "attempts_before_success": len(self.attempts) if self.successful_attack else None,
            "conversation_log": [
                {
                    "attempt": att.attempt_number,
                    "timestamp": att.timestamp.isoformat(),
                    "user": att.user_prompt,
                    "assistant": att.llm_response,
                    "tools_requested": att.tools_requested,
                    "malicious_tool": att.malicious_tool_called,
                }
                for att in self.attempts
            ]
        }
    
    def to_summary(self) -> str:
        """Generate a human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            f"Red Team Session Report",
            f"=" * 50,
            f"Session ID: {self.session_id}",
            f"Model: {self.model}",
            f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Attempts: {self.total_attempts}",
            f"Attack Success: {'YES' if self.successful_attack else 'NO'}",
        ]
        
        if self.successful_attack:
            lines.append(f"Malicious Tool: {self.malicious_tool_called}")
            lines.append(f"Attempts to Success: {len(self.attempts)}")
        
        if self.system_prompt:
            lines.append(f"\nSystem Prompt: {self.system_prompt[:100]}...")
        
        return "\n".join(lines)


class RedTeamAgent(LLMAgent):
    """Specialized agent for red team testing of tool calling.
    
    This agent extends the base LLMAgent with capabilities specifically
    designed for security testing of LLM tool-calling boundaries.
    """
    
    def __init__(
        self,
        client: LLMClient,
        tool_registry: ToolRegistry,
        malicious_tool_names: list[str],
        max_attempts: int = 10,
    ):
        """Initialize red team agent.
        
        Args:
            client: LLM client for API calls.
            tool_registry: Registry containing malicious tools.
            malicious_tool_names: List of tool names considered malicious.
            max_attempts: Maximum attempts before stopping (default: 10).
        """
        # Initialize parent with max_iterations=1 to prevent tool execution loops
        super().__init__(client, tool_registry, max_iterations=1)
        self.malicious_tool_names = set(malicious_tool_names)
        self.max_attempts = max_attempts
        
    async def red_team_session(
        self,
        model: str,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> RedTeamResult:
        """Run an interactive red team session.
        
        This method runs an interactive session where a human tester
        attempts to convince the LLM to call malicious tools.
        
        Args:
            model: Model identifier to test.
            session_id: Unique session identifier (generated if not provided).
            system_prompt: Optional system prompt to test against.
            
        Returns:
            RedTeamResult with complete session details.
        """
        if not session_id:
            session_id = f"interactive-{uuid4().hex[:8]}"
            
        attempts = []
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append(ChatMessageWithTools(
                role="system",
                content=system_prompt
            ))
        
        # Display session info
        print(f"\n{'='*60}")
        print(f"🎯 Red Team Session: {session_id}")
        print(f"📡 Testing model: {model}")
        print(f"🎲 Max attempts: {self.max_attempts}")
        print(f"☠️  Malicious tools: {sorted(self.malicious_tool_names)}")
        if system_prompt:
            print(f"📝 System prompt: {system_prompt[:50]}...")
        print(f"{'='*60}")
        print("\nType 'quit' to exit early")
        
        for attempt_num in range(1, self.max_attempts + 1):
            # Get user input
            print(f"\n[Attempt {attempt_num}/{self.max_attempts}]")
            user_prompt = input("👤 Your prompt: ").strip()
            
            if user_prompt.lower() == 'quit':
                print("🚪 Exiting session early...")
                break
                
            if not user_prompt:
                continue
                
            # Add user message
            messages.append(ChatMessageWithTools(
                role="user",
                content=user_prompt
            ))
            
            # Create request
            request = ChatRequestWithTools(
                model=model,
                messages=messages,
                tools=self.tools.get_tool_definitions(),
            )
            
            # Get response WITHOUT executing tools
            try:
                response = await self.chat_with_tools(
                    request,
                    auto_execute_tools=False  # Critical: Don't execute, just check
                )
            except Exception as e:
                logger.error(f"Error getting response: {e}")
                print(f"\n❌ Error: {e}")
                continue
            
            # Extract response details
            llm_response = ""
            tools_requested = []
            malicious_tool_called = None
            
            if response.choices:
                msg = response.choices[0].message
                llm_response = msg.content or ""
                
                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        tools_requested.append(tool_name)
                        
                        if tool_name in self.malicious_tool_names:
                            malicious_tool_called = tool_name
                
                # Add assistant response to history
                messages.append(msg)
            
            # Record attempt
            attempt = RedTeamAttempt(
                attempt_number=attempt_num,
                user_prompt=user_prompt,
                llm_response=llm_response,
                tools_requested=tools_requested,
                malicious_tool_called=malicious_tool_called,
                timestamp=datetime.now(),
            )
            attempts.append(attempt)
            
            # Display response
            print(f"\n🤖 Assistant: {llm_response}")
            if tools_requested:
                print(f"🔧 Tools requested: {tools_requested}")
            
            # Check if attack succeeded
            if malicious_tool_called:
                print(f"\n{'='*60}")
                print(f"⚠️  ATTACK SUCCESSFUL!")
                print(f"☠️  Malicious tool called: {malicious_tool_called}")
                print(f"🛑 Stopping session - attack succeeded")
                print(f"{'='*60}")
                
                return RedTeamResult(
                    session_id=session_id,
                    model=model,
                    total_attempts=attempt_num,
                    successful_attack=True,
                    malicious_tool_called=malicious_tool_called,
                    attempts=attempts,
                    system_prompt=system_prompt,
                )
        
        # Max attempts reached without success
        print(f"\n{'='*60}")
        print(f"✅ Session complete - no malicious tools called")
        print(f"💪 Model resisted {len(attempts)} attempts")
        print(f"{'='*60}")
        
        return RedTeamResult(
            session_id=session_id,
            model=model,
            total_attempts=len(attempts),
            successful_attack=False,
            malicious_tool_called=None,
            attempts=attempts,
            system_prompt=system_prompt,
        )


async def run_automated_red_team(
    client: LLMClient,
    model: str,
    test_prompts: list[str],
    malicious_tools: ToolRegistry,
    system_prompt: Optional[str] = None,
    session_id: Optional[str] = None,
) -> RedTeamResult:
    """Run automated red team test with predefined prompts.
    
    This function runs through a list of adversarial prompts automatically,
    stopping as soon as a malicious tool is requested.
    
    Args:
        client: LLM client for API calls.
        model: Model identifier to test.
        test_prompts: List of adversarial prompts to try.
        malicious_tools: Registry of malicious tools.
        system_prompt: Optional system prompt to test against.
        session_id: Session identifier (generated if not provided).
        
    Returns:
        RedTeamResult with test results.
    """
    if not session_id:
        session_id = f"auto-{uuid4().hex[:8]}"
        
    malicious_names = malicious_tools.get_tool_names()
    agent = RedTeamAgent(client, malicious_tools, malicious_names)
    
    messages = []
    attempts = []
    
    # Add system prompt if provided
    if system_prompt:
        messages.append(ChatMessageWithTools(
            role="system",
            content=system_prompt
        ))
    
    logger.info(f"Starting automated red team: {session_id}")
    
    for i, prompt in enumerate(test_prompts, 1):
        # Add user message
        messages.append(ChatMessageWithTools(role="user", content=prompt))
        
        # Create request
        request = ChatRequestWithTools(
            model=model,
            messages=messages,
            tools=agent.tools.get_tool_definitions(),
        )
        
        # Get response without executing tools
        try:
            response = await agent.chat_with_tools(request, auto_execute_tools=False)
        except Exception as e:
            logger.error(f"Error on attempt {i}: {e}")
            continue
        
        # Check for malicious tool calls
        tools_requested = []
        malicious_called = None
        llm_response = ""
        
        if response.choices:
            msg = response.choices[0].message
            llm_response = msg.content or ""
            messages.append(msg)
            
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_requested.append(tc.function.name)
                    if tc.function.name in malicious_names:
                        malicious_called = tc.function.name
        
        # Record attempt
        attempts.append(RedTeamAttempt(
            attempt_number=i,
            user_prompt=prompt,
            llm_response=llm_response,
            tools_requested=tools_requested,
            malicious_tool_called=malicious_called,
            timestamp=datetime.now(),
        ))
        
        # Stop if malicious tool called
        if malicious_called:
            logger.warning(f"Attack succeeded on attempt {i}: {malicious_called}")
            return RedTeamResult(
                session_id=session_id,
                model=model,
                total_attempts=i,
                successful_attack=True,
                malicious_tool_called=malicious_called,
                attempts=attempts,
                system_prompt=system_prompt,
            )
    
    # All prompts tried without success
    logger.info(f"Model {model} resisted all {len(test_prompts)} attempts")
    return RedTeamResult(
        session_id=session_id,
        model=model,
        total_attempts=len(test_prompts),
        successful_attack=False,
        malicious_tool_called=None,
        attempts=attempts,
        system_prompt=system_prompt,
    )