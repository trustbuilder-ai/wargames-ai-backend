#!/usr/bin/env python3
"""
Property-based tests for LiteLLM functionality using Hypothesis.
Run with: uv run pytest tests/test_llm.py
"""

import asyncio
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from backend.llm.client import (
    LLMAPIError,
    LLMClient,
    LLMValidationError,
)
from backend.models.llm import ChatMessage, ChatRequest
from backend.util.log import logger


# Hypothesis strategies for generating test data
@st.composite
def valid_chat_message(draw):
    """Generate valid ChatMessage objects."""
    role = draw(st.sampled_from(["user", "assistant", "system"]))
    content = draw(st.text(min_size=1, max_size=1000).filter(lambda x: x.strip()))
    name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    return ChatMessage(role=role, content=content, name=name)


@st.composite
def valid_chat_request(draw):
    """Generate valid ChatRequest objects."""
    # Common model IDs (will be filtered for availability in tests)
    model = draw(
        st.sampled_from(
            [
                "gpt-4o-mini",
                "gpt-4o",
                "claude-3-5-haiku-20241022",
                "claude-3-5-sonnet-20241022",
            ]
        )
    )
    messages = draw(st.lists(valid_chat_message(), min_size=1, max_size=10))
    temperature = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=2.0)))
    max_tokens = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=8192)))
    stream = draw(st.one_of(st.none(), st.booleans()))
    user = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))

    return ChatRequest(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        user=user,
    )


@st.composite
def invalid_chat_request(draw):
    """Generate invalid ChatRequest objects for testing validation."""
    model = draw(
        st.one_of(
            st.text().filter(
                lambda x: x
                not in ["gpt-4o-mini", "gpt-4o", "claude-3-5-haiku-20241022"]
            ),
            st.just(""),  # Empty model
        )
    )
    messages = draw(
        st.one_of(
            st.just([]),  # Empty messages
            st.lists(valid_chat_message(), min_size=1, max_size=5),
        )
    )
    temperature = draw(
        st.one_of(
            st.floats(min_value=-1.0, max_value=-0.1),  # Invalid negative
            st.floats(min_value=2.1, max_value=10.0),  # Invalid too high
            st.none(),
        )
    )

    return {"model": model, "messages": messages, "temperature": temperature}


# Fixtures
@pytest.fixture
def client():
    """Create LLM client instance."""
    return LLMClient()


# Helper function instead of async fixture
async def get_available_models():
    """Get list of available models for testing."""
    client = LLMClient()
    try:
        response = await client.list_models()
        return [model.id for model in response.data]
    except Exception:
        return []


# Property-based tests
class TestLLMClient:
    """Property-based tests for LLM client functionality."""

    @pytest.mark.asyncio
    async def test_health_check_properties(self, client):
        """Test that health check always returns valid structure."""
        health = await client.health_check()

        # Properties that should always hold
        assert health.status in ["healthy", "unhealthy", "degraded"]
        assert isinstance(health.available_models, int)
        assert health.available_models >= 0
        assert isinstance(health.missing_keys, list)
        assert isinstance(health.message, str)
        assert len(health.message) > 0

    @pytest.mark.asyncio
    async def test_list_models_properties(self, client):
        """Test that model listing returns valid structure."""
        response = await client.list_models()

        # Properties that should always hold
        assert response.object == "list"
        assert isinstance(response.data, list)

        for model in response.data:
            assert isinstance(model.id, str)
            assert len(model.id) > 0
            assert model.object == "model"
            assert isinstance(model.created, int)
            assert isinstance(model.owned_by, str)
            assert len(model.owned_by) > 0

    @pytest.mark.asyncio
    @given(st.data())
    @settings(
        max_examples=5,  # Limit API calls
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=30000,  # 30 second timeout for API calls
    )
    async def test_chat_completion_with_valid_requests(self, client, data):
        """Test that valid requests produce valid responses."""
        # Get available models dynamically
        available_models = await get_available_models()
        if not available_models:
            pytest.skip("No models available for testing")

        # Use only available models
        model = data.draw(st.sampled_from(available_models))
        messages = data.draw(st.lists(valid_chat_message(), min_size=1, max_size=3))

        request = ChatRequest(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=50,  # Keep small for faster tests
        )

        try:
            response = await client.chat_completion(request)

            # Properties that should always hold for successful responses
            assert isinstance(response.id, str)
            assert len(response.id) > 0
            assert response.object == "chat.completion"
            assert isinstance(response.created, int)
            # Model name may be versioned by provider
            # (e.g., github/gpt-4o -> github/gpt-4o-2024-11-20)
            assert model in response.model or response.model == model
            assert isinstance(response.choices, list)
            assert len(response.choices) > 0

            for choice in response.choices:
                assert isinstance(choice.index, int)
                assert choice.index >= 0
                assert choice.message.role == "assistant"
                assert isinstance(choice.message.content, str)
                assert len(choice.message.content) > 0

            if response.usage:
                assert response.usage.prompt_tokens > 0
                assert response.usage.completion_tokens > 0
                assert response.usage.total_tokens > 0
                assert response.usage.total_tokens == (
                    response.usage.prompt_tokens + response.usage.completion_tokens
                )

        except (LLMAPIError, LLMValidationError) as e:
            # These are expected for some edge cases
            logger.info(f"Expected error during testing: {e}")

    @pytest.mark.asyncio
    @given(invalid_chat_request())
    @settings(
        max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_chat_completion_with_invalid_requests(self, client, request_data):
        """Test that invalid requests raise appropriate errors."""
        with pytest.raises((LLMValidationError, LLMAPIError, ValueError)):
            # Try to create request - should fail validation
            request = ChatRequest(**request_data)
            await client.chat_completion(request)

    @pytest.mark.asyncio
    @given(st.text(min_size=1, max_size=100))
    @settings(
        max_examples=3,
        deadline=15000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    async def test_chat_completion_response_consistency(self, client, content):
        """Test that same input produces consistent response structure."""
        # Get available models dynamically
        available_models = await get_available_models()
        if not available_models:
            pytest.skip("No models available for testing")

        # Try to use Claude model first (since we have a valid Anthropic key)
        model = None
        for model_id in available_models:
            if "claude" in model_id:
                model = model_id
                break

        # Fallback to first available model if no Claude model found
        if not model:
            model = available_models[0]
        message = ChatMessage(role="user", content=content)
        request = ChatRequest(
            model=model,
            messages=[message],
            temperature=0.0,  # Deterministic
            max_tokens=20,
        )

        try:
            response1 = await client.chat_completion(request)
            await asyncio.sleep(0.5)  # Small delay
            response2 = await client.chat_completion(request)

            # Structure should be consistent
            assert type(response1) is type(response2)
            assert response1.model == response2.model
            assert len(response1.choices) == len(response2.choices)

            # With temperature=0, responses might be similar but not guaranteed
            # identical due to different model implementations

        except (LLMAPIError, LLMValidationError):
            pytest.skip("Model not available or request invalid")


# Stateful testing
class LLMConversationMachine(RuleBasedStateMachine):
    """Stateful testing for LLM conversations."""

    def __init__(self):
        super().__init__()
        self.client = LLMClient()
        self.conversation = []
        self.available_models = []

    @initialize()
    async def setup(self):
        """Initialize the conversation machine."""
        try:
            models_response = await self.client.list_models()
            self.available_models = [m.id for m in models_response.data]
        except Exception:
            self.available_models = []

    @rule(content=st.text(min_size=1, max_size=200))
    async def add_user_message(self, content):
        """Add a user message to the conversation."""
        assume(len(self.conversation) < 10)  # Limit conversation length
        assume(len(self.available_models) > 0)

        user_msg = ChatMessage(role="user", content=content)
        self.conversation.append(user_msg)

        # Try to get AI response
        try:
            request = ChatRequest(
                model=self.available_models[0],
                messages=self.conversation,
                temperature=0.7,
                max_tokens=50,
            )

            response = await self.client.chat_completion(request)
            if response.choices:
                ai_msg = ChatMessage(
                    role="assistant", content=response.choices[0].message.content
                )
                self.conversation.append(ai_msg)

        except (LLMAPIError, LLMValidationError):
            # Remove the user message if AI response failed
            self.conversation.pop()

    @invariant()
    def conversation_alternates_properly(self):
        """Conversation should alternate between user and assistant."""
        if len(self.conversation) <= 1:
            return

        for i in range(len(self.conversation) - 1):
            current_role = self.conversation[i].role
            next_role = self.conversation[i + 1].role

            # Conversations should generally alternate, but system messages are allowed
            if current_role == "user":
                assert next_role in ["assistant", "system"]
            elif current_role == "assistant":
                assert next_role in ["user", "system"]

    @invariant()
    def all_messages_have_content(self):
        """All messages should have non-empty content."""
        for message in self.conversation:
            assert isinstance(message.content, str)
            assert len(message.content.strip()) > 0


# Manual test runner (for backwards compatibility)
async def manual_test_runner():
    """Manual test runner for interactive testing."""
    print("🤖 LiteLLM Property-Based Testing Suite")
    print("=" * 50)

    client = LLMClient()

    # Test health check
    print("Testing health check properties...")
    health = await client.health_check()
    print(f"✅ Health: {health.status}, Models: {health.available_models}")

    # Test model listing
    print("\nTesting model listing properties...")
    models_response = await client.list_models()
    print(f"✅ Found {len(models_response.data)} models")

    if models_response.data:
        # Test a simple chat completion
        print(f"\nTesting chat completion with {models_response.data[0].id}...")
        try:
            request = ChatRequest(
                model=models_response.data[0].id,
                messages=[ChatMessage(role="user", content="Hello!")],
                max_tokens=50,
            )
            response = await client.chat_completion(request)
            print(f"✅ Response: {response.choices[0].message.content[:100]}...")
        except Exception as e:
            print(f"❌ Chat completion failed: {e}")

    print("\n✅ Manual tests completed!")
    print("Run with pytest for full property-based testing:")
    print("  uv run pytest tests/test_llm.py -v")


if __name__ == "__main__":
    asyncio.run(manual_test_runner())
