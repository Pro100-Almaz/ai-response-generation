from typing import Tuple
from app.providers.openai_provider import OpenAIProvider
from app.providers.base import Provider

def resolve_provider(model: str) -> Tuple[Provider, str]:
    """
    Resolve the provider by model prefix (e.g., 'openai:gpt-4o-mini').
    Returns (provider, normalized_model).
    """
    if model.startswith("openai:"):
        return OpenAIProvider(), model
    # default to OpenAI if no prefix, easy start
    return OpenAIProvider(), f"openai:{model}"
