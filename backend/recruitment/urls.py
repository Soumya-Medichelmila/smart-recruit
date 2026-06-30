from django.urls import path
from .views import (
    ScreenUploadView,
    BulkUploadView,
    RAGScreeningView,
    ScreeningResultsView,
    AllScreeningJobsView,
    ShortlistCandidateView,
    ShortlistByJobView,
    AllShortlistJobsView,
    UpdateShortlistStatusView,
    ScheduleInterviewView,
    InterviewsByJobView,
    AllInterviewsView,
    ResendRoundEmailView,
    CandidateListView,
    CandidateCountView,
    CandidateDeleteView,
)

urlpatterns = [
    # Upload
    path("upload/",           ScreenUploadView.as_view(),    name="resume-upload"),
    path("bulk-upload/",      BulkUploadView.as_view(),      name="bulk-upload"),

    # Screening
    path("rag-screen/",                   RAGScreeningView.as_view(),     name="rag-screen"),
    path("results/",                      AllScreeningJobsView.as_view(), name="all-screening-jobs"),
    path("results/<int:job_id>/",         ScreeningResultsView.as_view(), name="screening-results"),

    # Shortlist
    path("shortlist/<int:sr_id>/",         ShortlistCandidateView.as_view(),    name="shortlist-candidate"),
    path("shortlist/job/<int:job_id>/",    ShortlistByJobView.as_view(),        name="shortlist-by-job"),
    path("shortlist/jobs/",                AllShortlistJobsView.as_view(),      name="all-shortlist-jobs"),
    path("shortlist/<int:pk>/status/",     UpdateShortlistStatusView.as_view(), name="shortlist-status"),

    # Interviews
    path("interview/schedule/<int:shortlist_id>/", ScheduleInterviewView.as_view(), name="schedule-interview"),
    path("interview/resend-email/",                 ResendRoundEmailView.as_view(),  name="resend-round-email"),
    path("interview/job/<int:job_id>/",              InterviewsByJobView.as_view(),   name="interviews-by-job"),
    path("interviews/",                              AllInterviewsView.as_view(),     name="all-interviews"),

    # Candidates
    path("candidates/",              CandidateListView.as_view(),   name="candidate-list"),
    path("candidates/<int:pk>/",     CandidateDeleteView.as_view(), name="candidate-delete"),
    path("candidate-count/",         CandidateCountView.as_view(),  name="candidate-count"),
]