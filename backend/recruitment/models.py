from django.db import models

# Create your models here.
from django.db import models
from accounts.models import Employee
from jobs.models import JobOpening


class Resume(models.Model):
    candidate_name = models.CharField(max_length=150)
    file = models.FileField(upload_to='resumes/')
    uploaded_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='uploaded_resumes'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidate_name}"


class ScreeningResult(models.Model):
    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name='screening_results'
    )
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name='screening_results'
    )
    candidate_name = models.CharField(max_length=150)
    match_score = models.PositiveIntegerField(help_text='Score out of 100')
    reason = models.TextField(help_text='LLM explanation of match')
    screened_at = models.DateTimeField(auto_now_add=True)
    screened_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='screening_results_triggered'
    )

    class Meta:
        ordering = ['-match_score']
        # One result per resume per job
        unique_together = [['job_opening', 'resume']]

    def __str__(self):
        return f"{self.candidate_name} — {self.job_opening.title} ({self.match_score}%)"