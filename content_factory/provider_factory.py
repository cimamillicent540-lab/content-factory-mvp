import os

from content_factory.ai_provider import MockAIProvider, OpenAIProvider


class ProviderConfigurationError(ValueError):
    """Raised when provider environment variables are invalid."""


def create_provider(env=None, client=None):
    source = os.environ if env is None else env
    provider_name = (source.get("CONTENT_FACTORY_PROVIDER") or source.get("AI_PROVIDER") or "mock").strip().lower()
    if provider_name == "mock":
        return MockAIProvider()
    if provider_name == "openai":
        api_key = source.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required when CONTENT_FACTORY_PROVIDER=openai.")
        return OpenAIProvider(api_key=api_key, model=source.get("OPENAI_MODEL"), client=client)
    raise ProviderConfigurationError(f"Unsupported CONTENT_FACTORY_PROVIDER: {provider_name}")
