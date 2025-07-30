"""LLM API key settings using pydantic-settings.

This module handles loading LLM API keys from .env.litellm files
using pydantic-settings for type-safe environment variable management.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIKeySettings(BaseSettings):
    """LLM API key settings loaded from environment variables or .env.litellm file.

    This class automatically loads LLM API keys from:
    1. Environment variables (highest priority)
    2. .env.litellm file in the project root
    3. .env.litellm.local file for local overrides

    All API keys are optional to allow running with subset of providers.
    """

    model_config = SettingsConfigDict(
        env_file=[".env.litellm", ".env.litellm.local"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # OpenAI API key
    OPENAI_API_KEY: str | None = Field(
        default=None, description="OpenAI API key for GPT models"
    )

    # Anthropic API key
    ANTHROPIC_API_KEY: str | None = Field(
        default=None, description="Anthropic API key for Claude models"
    )

    # Hugging Face API key
    HUGGINGFACE_API_KEY: str | None = Field(
        default=None, description="Hugging Face API token for HF models"
    )

    # GitHub token for GitHub Models
    GITHUB_TOKEN: str | None = Field(
        default=None, description="GitHub Personal Access Token for GitHub Models"
    )

    def is_provider_available(self, provider: str) -> bool:
        """Check if a provider has its API key configured.

        Args:
            provider: Provider name (openai, anthropic, huggingface, github)

        Returns:
            True if the provider's API key is set, False otherwise.
        """
        provider_key_map = {
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "huggingface": self.HUGGINGFACE_API_KEY,
            "github": self.GITHUB_TOKEN,
        }

        key = provider_key_map.get(provider.lower())
        return key is not None and key.strip() != ""

    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a specific provider.

        Args:
            provider: Provider name (openai, anthropic, huggingface, github)

        Returns:
            API key string or None if not configured.
        """
        provider_key_map = {
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "huggingface": self.HUGGINGFACE_API_KEY,
            "github": self.GITHUB_TOKEN,
        }

        return provider_key_map.get(provider.lower())

    def get_available_providers(self) -> list[str]:
        """Get list of providers with configured API keys.

        Returns:
            List of provider names that have API keys configured.
        """
        available = []
        providers = ["openai", "anthropic", "huggingface", "github"]

        for provider in providers:
            if self.is_provider_available(provider):
                available.append(provider)

        return available


# Global settings instance
api_keys = APIKeySettings()
