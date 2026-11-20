from django.db import models


class AIModel(models.Model):
    """A model in the catalog: either one users can compare, or a judge."""

    class Provider(models.TextChoices):
        GEMINI = 'gemini', 'Gemini'
        GROQ = 'groq', 'Groq'
        OPENROUTER = 'openrouter', 'OpenRouter'
        NVIDIA = 'nvidia', 'NVIDIA'
        OVHCLOUD = 'ovhcloud', 'OVHcloud'

    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, choices=Provider.choices)
    api_model_identifier = models.CharField(
        max_length=100,
        unique=True,
        help_text='The model id sent to the provider API.',
    )
    # Prices are per 1M tokens. NULL means the price is unknown, so the cost
    # of a request cannot be calculated (reported as unavailable, never 0).
    input_price_per_million = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
    )
    output_price_per_million = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
    )
    currency = models.CharField(max_length=3, default='USD')
    # Inactive models are hidden from every list but stay in the database
    # because past experiments (and judge runs) refer to them.
    is_active = models.BooleanField(default=True)
    # Judges evaluate responses and are not offered as models to compare.
    is_judge = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
