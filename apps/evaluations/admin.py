from django.contrib import admin

from .models import Evaluation, EvaluationCriterion, ResponseEvaluation


@admin.register(EvaluationCriterion)
class EvaluationCriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active')
    list_editable = ('is_active',)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('response', 'criterion', 'score')
    list_filter = ('criterion',)


@admin.register(ResponseEvaluation)
class ResponseEvaluationAdmin(admin.ModelAdmin):
    list_display = ('response', 'label', 'overall_score')
