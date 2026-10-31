"""Shared interface that every AI provider integration implements."""

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Common interface for all AI providers."""

    @abstractmethod
    def generate(self, model_id: str, prompt: str) -> dict[str, Any]:
        """
        Generate a response from an AI model.

        Args:
            model_id: The model identifier.
            prompt: The user's input prompt.

        Returns:
            A standardized response containing text,
            latency, and token usage.
        """
        raise NotImplementedError
