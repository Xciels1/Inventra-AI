# integrations/__init__.py
"""Inventra AI — Integrations Package (Azure OpenAI, Anthropic)"""
from integrations.azure_provider import AzureOpenAIProvider, get_ai_provider

__all__ = ["AzureOpenAIProvider", "get_ai_provider"]
