from django.contrib import admin

from .models import Experiment, ExperimentModel, ModelResponse, Run


class ExperimentModelInline(admin.TabularInline):
    model = ExperimentModel
    extra = 0


class RunInline(admin.TabularInline):
    model = Run
    extra = 0
    show_change_link = True


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ('id', 'prompt', 'created_at')
    search_fields = ('prompt',)
    inlines = [ExperimentModelInline, RunInline]


class ModelResponseInline(admin.TabularInline):
    model = ModelResponse
    extra = 0


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('id', 'experiment', 'status', 'evaluation_status', 'started_at')
    list_filter = ('status', 'evaluation_status')
    inlines = [ModelResponseInline]
