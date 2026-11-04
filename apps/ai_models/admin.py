from django.contrib import admin

from .models import AIModel


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'provider', 'api_model_identifier',
        'input_price_per_million', 'output_price_per_million', 'currency', 'is_active',
    )
    list_filter = ('provider', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'api_model_identifier')
