from core.gateway.base import BaseProvider
from core.gateway.ollama import OllamaProvider


class ModelGateway:
    """Registry and router for model providers."""

    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}
        # Default local provider
        self.register_provider("ollama", OllamaProvider())

    def register_provider(self, name: str, provider: BaseProvider) -> None:
        self._providers[name] = provider

    def get_provider_for_model(self, model: str) -> BaseProvider:
        """Resolve the appropriate provider for a given model.
        
        Currently routes all models to the local Ollama provider.
        Future providers (e.g. 'claude-*' -> AnthropicProvider, 'gpt-*' -> OpenAIProvider)
        can be registered and routed here without changing call sites.
        """
        # Default routing: all local models handled by Ollama
        return self._providers["ollama"]


# Global gateway singleton
gateway = ModelGateway()

