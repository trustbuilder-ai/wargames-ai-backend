"""LLM (Large Language Model) routes for AI model interactions.

This module provides API endpoints for:
- Creating chat completions with various LLM providers
- Listing available models
- Checking LLM service health status
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.dependencies import get_current_user
from backend.llm.client import LLMClient
from backend.models.llm import (
    ChatRequest,
    ChatResponse,
    LLMHealthStatus,
    ModelsResponse,
)
from backend.util.log import logger

# Create router with prefix and tags
router = APIRouter(
    prefix="/llm",
    tags=["llm"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
)


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion(
    request: ChatRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Create a chat completion using direct LiteLLM integration.

    This endpoint uses the LiteLLM library to make direct calls to various
    LLM providers (OpenAI, Anthropic, GitHub, etc.) without requiring a
    separate proxy server.

    Args:
        request: ChatRequest object containing:
            - model: The model to use (e.g., "gpt-4", "claude-3")
            - messages: List of chat messages
            - temperature: Optional sampling temperature
            - max_tokens: Optional maximum tokens to generate
            - stream: Whether to stream the response
            - user: Optional user identifier for tracking
        current_user: Current authenticated user from JWT token

    Returns:
        ChatResponse: The LLM's response containing:
            - id: Unique completion ID
            - object: Response type (always "chat.completion")
            - created: Unix timestamp of creation
            - model: The model used
            - choices: List of completion choices
            - usage: Token usage statistics

    Raises:
        HTTPException: 500 if chat completion fails

    Example:
        ```python
        POST /llm/chat/completions
        {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Hello, how are you?"}
            ],
            "temperature": 0.7
        }
        ```
    """
    try:
        # Add user tracking for monitoring and billing
        if request.user is None:
            request.user = current_user["id"]

        client = LLMClient()
        response = await client.chat_completion(request)

        logger.info(f"Chat completion for user {current_user['id']}: {request.model}")
        return response

    except Exception as e:
        logger.error(f"Chat completion failed for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


@router.get("/models", response_model=ModelsResponse)
async def list_available_models(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List available LLM models.

    Returns a list of all configured LLM models that have their API keys
    set and are ready to use. Models without API keys are excluded.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        ModelsResponse: Object containing:
            - object: Response type (always "list")
            - data: List of available models with their metadata

    Raises:
        HTTPException: 500 if listing models fails

    Example:
        ```python
        GET /llm/models
        Response:
        {
            "object": "list",
            "data": [
                {
                    "id": "gpt-4",
                    "object": "model",
                    "created": 1686935002,
                    "owned_by": "openai"
                },
                {
                    "id": "claude-3-opus-20240229",
                    "object": "model",
                    "created": 1709251200,
                    "owned_by": "anthropic"
                }
            ]
        }
        ```
    """
    try:
        client = LLMClient()
        response = await client.list_models()

        logger.info(f"Models list requested by user {current_user['id']}")
        return response

    except Exception as e:
        logger.error(f"Failed to list models for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/health", response_model=LLMHealthStatus)
async def check_llm_health(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Check the health status of the LLM service.

    Provides comprehensive health information about the LLM service including:
    - Overall service status
    - List of available models
    - Configured providers and their status
    - Missing API keys that need configuration

    This endpoint is useful for monitoring and debugging LLM integrations.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        LLMHealthStatus: Health status object containing:
            - healthy: Overall health status boolean
            - available_models: List of ready-to-use models
            - providers: Dictionary of provider statuses
            - missing_keys: List of providers missing API keys
            - error: Optional error message if unhealthy

    Raises:
        HTTPException: 500 if health check fails

    Example:
        ```python
        GET /llm/health
        Response:
        {
            "healthy": true,
            "available_models": ["gpt-4", "claude-3-opus"],
            "providers": {
                "openai": true,
                "anthropic": true,
                "github": false
            },
            "missing_keys": ["GITHUB_API_KEY"],
            "error": null
        }
        ```
    """
    try:
        client = LLMClient()
        health_status = await client.health_check()

        logger.info(f"LLM health check requested by user {current_user['id']}")
        return health_status

    except Exception as e:
        logger.error(f"LLM health check failed for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=500, detail=f"LLM health check failed: {str(e)}"
        )