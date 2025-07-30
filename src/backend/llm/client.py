"""LLM client for direct LiteLLM integration.

This module provides a client class for making direct calls to LLM providers
using the LiteLLM library, which provides a unified interface to multiple providers.
"""

from typing import Any

import litellm
from pydantic import ValidationError

from backend.llm.settings import api_keys
from backend.models.llm import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatUsage,
    LLMHealthStatus,
    ModelInfo,
    ModelsResponse,
)
from backend.util.log import logger

from .config import llm_config


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMValidationError(LLMClientError):
    """Exception raised when request/response validation fails."""

    pass


class LLMAPIError(LLMClientError):
    """Exception raised when the LLM API returns an error."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class LLMClient:
    """Client for direct LiteLLM integration.

    This client provides methods for chat completions using LiteLLM's
    direct API calls to various LLM providers.

    Single Responsibility: Handle LLM API calls and response conversion.
    """

    def __init__(self):
        """Initialize the LLM client.

        API keys should be set as environment variables:
        - OPENAI_API_KEY for OpenAI models
        - ANTHROPIC_API_KEY for Anthropic models
        - etc.
        """
        # Configure litellm logging based on loguru logger level
        # Note: loguru doesn't have isEnabledFor,
        # so we'll enable verbose for DEBUG level
        from os import getenv

        litellm.set_verbose = getenv("LITELLM_LOG", "").upper() == "DEBUG"

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create a chat completion using LiteLLM.

        Args:
            request: The chat completion request.

        Returns:
            The chat completion response.

        Raises:
            LLMValidationError: If request validation fails.
            LLMAPIError: If the API call fails.
            LLMClientError: For other client errors.
        """
        try:
            # Validate that the model is configured and available
            model_config = llm_config.get_model(request.model)
            if not model_config:
                available = [m.id for m in llm_config.list_models()]
                raise LLMValidationError(
                    f"Model '{request.model}' not configured. "
                    f"Available models: {available}"
                )

            # Check if required API key is available
            if not llm_config.is_model_available(request.model):
                raise LLMAPIError(
                    f"API key '{model_config.requires_key}' not set for "
                    f"model '{request.model}'"
                )

            # Convert request to litellm format
            messages = [
                {"role": msg.role, "content": msg.content} for msg in request.messages
            ]

            # Apply defaults from configuration
            temperature = (
                request.temperature
                if request.temperature is not None
                else llm_config.default_temperature
            )
            max_tokens = (
                request.max_tokens
                if request.max_tokens is not None
                else llm_config.default_max_tokens
            )

            logger.info(f"Making LiteLLM completion request for model: {request.model}")

            # Get API key for the model's provider
            model_config = llm_config.get_model(request.model)
            api_key = api_keys.get_api_key(model_config.provider)

            # Make the LiteLLM call with API key
            response = await litellm.acompletion(
                model=request.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=request.stream or False,
                user=request.user,
                api_key=api_key,
            )

            logger.info(f"LiteLLM completion successful for model: {request.model}")

            # Convert response to our format
            return self._convert_response(response)

        except ValidationError as e:
            logger.error(f"Request validation failed: {e}")
            raise LLMValidationError(f"Request validation failed: {e}") from e
        except Exception as e:
            logger.error(f"LiteLLM completion failed: {e}")
            raise LLMAPIError(f"LLM completion failed: {str(e)}", e) from e

    async def list_models(self) -> ModelsResponse:
        """List available models.

        Returns:
            The models response containing available models.
        """
        models = []
        for model_config in llm_config.list_available_models():
            model_data = {
                "id": model_config.id,
                "object": "model",
                "created": 0,  # Static for direct integration
                "owned_by": model_config.provider,
                "display_name": model_config.display_name,
                "description": model_config.description,
                "max_tokens": model_config.max_tokens,
            }
            models.append(ModelInfo.model_validate(model_data))

        return ModelsResponse.model_validate({"data": models})

    async def health_check(self) -> LLMHealthStatus:
        """Check the health of the LLM service.

        Returns:
            Health status information.
        """
        available_models = llm_config.list_available_models()
        all_models = llm_config.list_models()

        # Determine overall health status
        if len(available_models) == 0:
            status = "unhealthy"
            message = "No models available - missing API keys"
        elif len(available_models) < len(all_models):
            status = "degraded"
            message = (
                f"Some models unavailable "
                f"({len(available_models)}/{len(all_models)} available)"
            )
        else:
            status = "healthy"
            message = f"All models available ({len(available_models)} models)"

        health_data = {
            "status": status,
            "available_models": len(available_models),
            "missing_keys": [],  # Simplified - no detailed missing key tracking
            "message": message,
            "details": {"total_models": len(all_models)},
        }
        return LLMHealthStatus.model_validate(health_data)

    def _convert_response(self, litellm_response: Any) -> ChatResponse:
        """Convert LiteLLM response to our ChatResponse format.

        Args:
            litellm_response: The response from LiteLLM.

        Returns:
            Our standardized ChatResponse.
        """
        # Convert choices
        choices = []
        for choice in litellm_response.choices:
            # Use model_validate to safely handle external data from LiteLLM
            message_data = {
                "role": choice.message.role,
                "content": choice.message.content,
            }
            # Add name if it exists
            if hasattr(choice.message, "name") and choice.message.name:
                message_data["name"] = choice.message.name

            message = ChatMessage.model_validate(message_data)

            choice_data = {
                "index": choice.index,
                "message": message,
                "finish_reason": choice.finish_reason,
            }
            choices.append(ChatChoice.model_validate(choice_data))

        # Convert usage
        usage = None
        if hasattr(litellm_response, "usage") and litellm_response.usage:
            usage_data = {
                "prompt_tokens": litellm_response.usage.prompt_tokens,
                "completion_tokens": litellm_response.usage.completion_tokens,
                "total_tokens": litellm_response.usage.total_tokens,
            }
            usage = ChatUsage.model_validate(usage_data)

        # Use model_validate for the main response to ensure data integrity
        response_data = {
            "id": litellm_response.id,
            "object": litellm_response.object,
            "created": litellm_response.created,
            "model": litellm_response.model,
            "choices": choices,
            "usage": usage,
        }
        return ChatResponse.model_validate(response_data)
