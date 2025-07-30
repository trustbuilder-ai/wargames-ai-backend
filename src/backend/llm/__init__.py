"""
LLM integration module for TrustBuilder Wargames AI Backend.

This module provides direct integration with LiteLLM library for calling
various Large Language Models through a unified interface.

Separation of Concerns:
- client.py: LLM client implementation using direct LiteLLM calls
- config.py: Model configuration and environment setup
- settings.py: API key settings using pydantic-settings

Data models are located in backend.models.llm module.
"""
