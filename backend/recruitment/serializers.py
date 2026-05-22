from rest_framework import serializers
from .models import Resume, ScreeningResult


class ResumeSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name', read_only=True
    )

    class Meta:
        model = Resume
        fields = [
            'id', 'candidate_name', 'file',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at']


class ScreeningResultSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(
        source='job_opening.title', read_only=True
    )
    resume_file = serializers.FileField(
        source='resume.file', read_only=True
    )

    class Meta:
        model = ScreeningResult
        fields = [
            'id', 'job_opening', 'job_title',
            'resume', 'resume_file',
            'candidate_name', 'match_score', 'reason',
            'screened_at', 'screened_by'
        ]
        read_only_fields = [
            'id', 'job_opening', 'job_title',
            'resume', 'resume_file',
            'candidate_name', 'match_score', 'reason',
            'screened_at', 'screened_by'
        ]