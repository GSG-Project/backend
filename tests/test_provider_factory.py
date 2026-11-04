import pytest

from providers.exceptions import ProviderModelError
from providers.factory import get_provider


def test_unknown_provider_is_rejected():
    with pytest.raises(ProviderModelError, match="Unsupported provider 'openai'"):
        get_provider('openai')
