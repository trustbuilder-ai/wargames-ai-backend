"""LLM configuration management.

This module handles model configuration loading from YAML file.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.llm.settings import api_keys
from backend.llm.tools import ToolRegistry
import backend

@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""

    id: str
    provider: str
    display_name: str
    description: str
    requires_key: str
    max_tokens: int = 4096


class LLMConfig:
    """Simple LLM configuration manager."""

    # Default to LLMConfig in project root (backend/llm_config.yaml),
    # deriving the path from the backend module directory using pathlib.
    # for path compatibility across different environments.
    def __init__(self, config_path: str|Path = Path(backend.__path__[0]).parent.parent / "llm_config.yaml"): # type: ignore
        """Initialize LLM configuration from YAML file."""
        print(f"Config path: {config_path}")
        self._models: dict[str, ModelConfig] = {}
        self._tool_registry: ToolRegistry | None = None
        self.default_temperature = 0.7
        self.default_max_tokens = 4096
        self.default_model = "gpt-4o-mini"

        self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load configuration from YAML file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                # Fallback to basic config if file doesn't exist
                self._load_default_config()
                return

            with open(config_file) as f:
                config = yaml.safe_load(f)

            # Load models
            for model_id, model_data in config.get("models", {}).items():
                self._models[model_id] = ModelConfig(
                    id=model_id,
                    provider=model_data["provider"],
                    display_name=model_data["display_name"],
                    description=model_data["description"],
                    requires_key=model_data["requires_key"],
                    max_tokens=model_data.get("max_tokens", 4096),
                )

            # Load defaults
            defaults = config.get("defaults", {})
            self.default_temperature = defaults.get("temperature", 0.7)
            self.default_max_tokens = defaults.get("max_tokens", 4096)
            self.default_model = defaults.get("default_model", "gpt-4o-mini")

            # Load tools if present
            if "tools" in config:
                self._tool_registry = ToolRegistry()
                self._tool_registry.load_from_config(config["tools"])

        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
            self._load_default_config()

    def _load_default_config(self):
        """Load basic fallback configuration."""
        self._models = {
            "gpt-4o-mini": ModelConfig(
                id="gpt-4o-mini",
                provider="openai",
                display_name="GPT-4o Mini",
                description="OpenAI GPT-4o Mini model",
                requires_key="OPENAI_API_KEY",
            )
        }

    def get_model(self, model_id: str) -> ModelConfig | None:
        """Get model configuration by ID."""
        return self._models.get(model_id)

    def list_models(self) -> list[ModelConfig]:
        """List all configured models."""
        return list(self._models.values())

    def list_available_models(self) -> list[ModelConfig]:
        """List models that have their API keys configured."""
        available = []
        for model in self._models.values():
            if api_keys.is_provider_available(model.provider):
                available.append(model)
        return available

    def is_model_available(self, model_id: str) -> bool:
        """Check if a model is available (has API key configured)."""
        model = self.get_model(model_id)
        if model is None:
            return False
        return api_keys.is_provider_available(model.provider)

    def get_tool_registry(self) -> ToolRegistry | None:
        """Get the tool registry if tools are configured.

        Returns:
            ToolRegistry instance or None if no tools configured.
        """
        return self._tool_registry

    def has_tools(self) -> bool:
        """Check if any tools are configured.

        Returns:
            True if tools are available.
        """
        return self._tool_registry is not None


# Global configuration instance
llm_config = LLMConfig()
