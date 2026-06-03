from django.db import models
from accounts.models import Employee
from jobs.models import JobOpening


# Resume model removed.
# Resumes are now read directly from a configured server directory,
# not stored in the database.


class ScreeningResult(models.Model):
    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name='screening_results'
    )

    # Stores the filename found in the configured server directory.
    # No file is uploaded to the server via this model.
    source_filename = models.CharField(
        max_length=255,
        help_text='Filename inside the configured resume directory'
    )

    candidate_name = models.CharField(max_length=150)
    candidate_email = models.EmailField(
        blank=True,
        null=True,
        help_text='Auto-extracted from resume file'
    )
    match_score = models.PositiveIntegerField(help_text='Score out of 100')
    reason = models.TextField(help_text='LLM explanation of match')
    screened_at = models.DateTimeField(auto_now_add=True)
    
    # If screening is fully automated (e.g., via cron), this might reference a System user.
    # If triggered by an admin click, it references that Employee.
    screened_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='screening_results_triggered'
    )

    class Meta:
        ordering = ['-match_score']
        unique_together = [['job_opening', 'source_filename']]

    def __str__(self):
        return f"{self.candidate_name} — {self.job_opening.title} ({self.match_score}%)"


class Shortlist(models.Model):
    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name='shortlisted_candidates'
    )
    screening_result = models.OneToOneField(
        ScreeningResult,
        on_delete=models.CASCADE,
        related_name='shortlist'
    )
    shortlisted_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='shortlisted_candidates'
    )
    shortlisted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    STATUS_CHOICES = [
        ('SHORTLISTED', 'Shortlisted'),
        ('SCHEDULED', 'Scheduled'),
        ('HIRED', 'Hired'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SHORTLISTED')
    

    def __str__(self):
        return f"{self.screening_result.candidate_name} shortlisted for {self.job_opening.title}"


class InterviewSchedule(models.Model):

    MODE_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
    ]

    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    shortlist = models.ForeignKey(
        Shortlist,
        on_delete=models.CASCADE,
        related_name='interviews'
    )
    interview_date = models.DateField()
    interview_time = models.TimeField()
    mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default='ONLINE'
    )
    meeting_link = models.URLField(
        blank=True,
        null=True,
        help_text='Zoom/Meet link for online interviews'
    )
    venue = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Venue address for offline interviews'
    )
    assigned_interviewer = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='assigned_interviews'
    )
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SCHEDULED'
    )
    # Flag to track if notification was sent. 
    # Note: Bulk email workflow is removed, but individual status tracking remains for dashboards.
    email_sent = models.BooleanField(default=False)
    scheduled_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='scheduled_interviews'
    )
    scheduled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview for {self.shortlist.screening_result.candidate_name} on {self.interview_date}"























# from django.db import models
# from accounts.models import Employee
# from jobs.models import JobOpening


# class Resume(models.Model):
#     candidate_name = models.CharField(max_length=150)
#     candidate_email = models.EmailField(
#         help_text='Candidate email for interview notifications',
#         blank=True,
#         null=True
#     )
#     file = models.FileField(upload_to='resumes/')
#     uploaded_by = models.ForeignKey(
#         Employee,
#         on_delete=models.PROTECT,
#         related_name='uploaded_resumes'
#     )
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.candidate_name}"


# class ScreeningResult(models.Model):
#     job_opening = models.ForeignKey(
#         JobOpening,
#         on_delete=models.CASCADE,
#         related_name='screening_results'
#     )
#     resume = models.ForeignKey(
#         Resume,
#         on_delete=models.CASCADE,
#         related_name='screening_results'
#     )
#     candidate_name = models.CharField(max_length=150)
#     match_score = models.PositiveIntegerField(help_text='Score out of 100')
#     reason = models.TextField(help_text='LLM explanation of match')
#     screened_at = models.DateTimeField(auto_now_add=True)
#     screened_by = models.ForeignKey(
#         Employee,
#         on_delete=models.PROTECT,
#         related_name='screening_results_triggered'
#     )

#     class Meta:
#         ordering = ['-match_score']
#         # Only one screening result per resume per job
#         unique_together = [['job_opening', 'resume']]

#     def __str__(self):
#         return f"{self.candidate_name} — {self.job_opening.title} ({self.match_score}%)"


# class Shortlist(models.Model):
#     job_opening = models.ForeignKey(
#         JobOpening,
#         on_delete=models.CASCADE,
#         related_name='shortlisted_candidates'
#     )
#     screening_result = models.OneToOneField(
#         ScreeningResult,
#         on_delete=models.CASCADE,
#         related_name='shortlist'
#     )
#     shortlisted_by = models.ForeignKey(
#         Employee,
#         on_delete=models.PROTECT,
#         related_name='shortlisted_candidates'
#     )
#     shortlisted_at = models.DateTimeField(auto_now_add=True)
#     notes = models.TextField(blank=True, null=True)

#     def __str__(self):
#         return f"{self.screening_result.candidate_name} shortlisted for {self.job_opening.title}"


# class InterviewSchedule(models.Model):

#     MODE_CHOICES = [
#         ('ONLINE', 'Online'),
#         ('OFFLINE', 'Offline'),
#     ]

#     STATUS_CHOICES = [
#         ('SCHEDULED', 'Scheduled'),
#         ('COMPLETED', 'Completed'),
#         ('CANCELLED', 'Cancelled'),
#     ]

#     shortlist = models.ForeignKey(
#         Shortlist,
#         on_delete=models.CASCADE,
#         related_name='interviews'
#     )
#     interview_date = models.DateField()
#     interview_time = models.TimeField()
#     mode = models.CharField(
#         max_length=10,
#         choices=MODE_CHOICES,
#         default='ONLINE'
#     )
#     meeting_link = models.URLField(
#         blank=True,
#         null=True,
#         help_text='Zoom/Meet link for online interviews'
#     )
#     venue = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True,
#         help_text='Venue address for offline interviews'
#     )
#     assigned_interviewer = models.ForeignKey(
#         Employee,
#         on_delete=models.PROTECT,
#         related_name='assigned_interviews'
#     )
#     notes = models.TextField(blank=True, null=True)
#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default='SCHEDULED'
#     )
#     email_sent = models.BooleanField(default=False)
#     scheduled_by = models.ForeignKey(
#         Employee,
#         on_delete=models.PROTECT,
#         related_name='scheduled_interviews'
#     )
#     scheduled_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Interview for {self.shortlist.screening_result.candidate_name} on {self.interview_date}"