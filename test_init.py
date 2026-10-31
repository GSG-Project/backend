import os
import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.development"
)

django.setup()

from providers.gemini import GeminiProvider

provider = GeminiProvider()

result = provider.generate(
    model_id="gemini-3.8-flash",
    prompt="Explain quantum computing in two sentences."
)

print(result)