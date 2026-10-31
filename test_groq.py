
import os
import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.development"
)

django.setup()

from django.conf import settings
from groq import Groq

client = Groq(api_key=settings.GROQ_API_KEY)

response = client.chat.completions.create(
    model=settings.JUDGE_MODEL,
    messages=[
        {
            "role": "user",
            "content": "Explain quantum computing in two sentences."
        }
    ],
    temperature=0.2,
    max_tokens=300
)

print("Answer:")
print(response.choices[0].message.content)

print("\nUsage:")
print(response.usage)
