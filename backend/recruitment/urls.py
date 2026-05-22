from django.urls import path
from .views import (
    ResumeListUploadView,
    ResumeDeleteView,
    ScreenResumesView,
    ScreeningResultsView,
    AllScreeningJobsView,
)

urlpatterns = [
    # Resume pool
    path('resumes/', ResumeListUploadView.as_view(), name='resume-list-upload'),
    path('resumes/<int:pk>/', ResumeDeleteView.as_view(), name='resume-delete'),

    # Screening (Recruitment triggers)
    path('screen/<int:job_id>/', ScreenResumesView.as_view(), name='screen-resumes'),

    # Results (HR views)
    path('results/', AllScreeningJobsView.as_view(), name='all-screening-jobs'),
    path('results/<int:job_id>/', ScreeningResultsView.as_view(), name='screening-results'),
]