from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Resume, ScreeningResult


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ['id', 'candidate_name', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['candidate_name']
    ordering = ['-uploaded_at']


@admin.register(ScreeningResult)
class ScreeningResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'candidate_name', 'job_opening', 'match_score', 'screened_by', 'screened_at']
    list_filter = ['job_opening', 'screened_at']
    search_fields = ['candidate_name', 'job_opening__title']
    ordering = ['-match_score']
    readonly_fields = ['screened_at']