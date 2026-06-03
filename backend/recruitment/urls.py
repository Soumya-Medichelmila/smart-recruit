# from django.urls import path
# from .views import (
#     # Resume
#     ResumeListUploadView,
#     ResumeDeleteView,

#     # Screening
#     ScreenResumesView,
#     ScreeningResultsView,
#     AllScreeningJobsView,

#     # Shortlist
#     ShortlistCandidateView,
#     ShortlistByJobView,
#     AllShortlistJobsView,

#     # Interview
#     ScheduleInterviewView,
#     BulkScheduleInterviewView,
#     ResendInterviewEmailView,
#     SendInterviewerConsolidatedEmailView,
#     InterviewsByJobView,
#     AllInterviewJobsView,
#     AllInterviewsView,
# )

# urlpatterns = [

#     # ── RESUME POOL ──────────────────────────────────────────────────────────
#     path('resumes/',         ResumeListUploadView.as_view(), name='resume-list-upload'),
#     path('resumes/<int:pk>/', ResumeDeleteView.as_view(),   name='resume-delete'),

#     # ── SCREENING ────────────────────────────────────────────────────────────
#     path('screen/<int:job_id>/',    ScreenResumesView.as_view(),    name='screen-resumes'),
#     path('results/',                AllScreeningJobsView.as_view(), name='all-screening-jobs'),
#     path('results/<int:job_id>/',   ScreeningResultsView.as_view(), name='screening-results'),

#     # ── SHORTLIST (fixed paths BEFORE parameterized) ──────────────────────────
#     path('shortlist/job/<int:job_id>/', ShortlistByJobView.as_view(),   name='shortlist-by-job'),
#     path('shortlist/jobs/',             AllShortlistJobsView.as_view(), name='all-shortlist-jobs'),
#     path('shortlist/all/',              AllShortlistJobsView.as_view(), name='all-shortlist-jobs-alias'),
#     path('shortlist/<int:result_id>/',  ShortlistCandidateView.as_view(), name='shortlist-candidate'),

    # ── INTERVIEW (fixed paths BEFORE parameterized) ──────────────────────────
#     path('interview/all/',                    AllInterviewsView.as_view(),                      name='all-interviews'),
#     path('interview/jobs/',                   AllInterviewJobsView.as_view(),                   name='all-interview-jobs'),
#     path('interview/bulk-schedule/',          BulkScheduleInterviewView.as_view(),              name='bulk-schedule-interview'),
#     path('interview/send-interviewer-email/', SendInterviewerConsolidatedEmailView.as_view(),   name='send-interviewer-email'),
#     path('interview/resend-email/',           ResendInterviewEmailView.as_view(),               name='resend-interview-email'),  # ← no path param; shortlist_id in body
#     path('interview/schedule/<int:shortlist_id>/', ScheduleInterviewView.as_view(),             name='schedule-interview'),
#     path('interview/job/<int:job_id>/',       InterviewsByJobView.as_view(),                    name='interviews-by-job'),
# ]
from django.urls import path
from .views import (
    # Folder / Screening
    FolderResumeListView,
    FolderScreenView,
    ScreeningResultsView,
    AllScreeningJobsView,

    # Shortlist
    ShortlistCandidateView,
    ShortlistByJobView,
    AllShortlistJobsView,

    # Interview
    ScheduleInterviewView,
    ResendInterviewEmailView,
    InterviewsByJobView,
    AllInterviewJobsView,
    AllInterviewsView,
    UpdateShortlistStatusView,
    
)

urlpatterns = [
    # ── FOLDER & SCREENING ────────────────────────────────────────────────────
    path('folder-resumes/', FolderResumeListView.as_view(), name='folder-resumes'),
    path('folder-screen/<int:job_id>/', FolderScreenView.as_view(), name='folder-screen'),
    path('results/', AllScreeningJobsView.as_view(), name='all-screening-jobs'),
    path('results/<int:job_id>/', ScreeningResultsView.as_view(), name='screening-results'),

    # ── SHORTLIST ─────────────────────────────────────────────────────────────
    path('shortlist/job/<int:job_id>/', ShortlistByJobView.as_view(), name='shortlist-by-job'),
    path('shortlist/jobs/', AllShortlistJobsView.as_view(), name='all-shortlist-jobs'),
    path('shortlist/all/', AllShortlistJobsView.as_view(), name='all-shortlist-jobs-alias'),
    path('shortlist/<int:sr_id>/', ShortlistCandidateView.as_view(), name='shortlist-candidate'),

    # ── INTERVIEW ─────────────────────────────────────────────────────────────
    path('interview/all/', AllInterviewsView.as_view(), name='all-interviews'),
    path('interview/jobs/', AllInterviewJobsView.as_view(), name='all-interview-jobs'),
    path('interview/resend-email/', ResendInterviewEmailView.as_view(), name='resend-interview-email'),
    path('interview/schedule/<int:shortlist_id>/', ScheduleInterviewView.as_view(), name='schedule-interview'),
    path('interview/job/<int:job_id>/', InterviewsByJobView.as_view(), name='interviews-by-job'),


     path('shortlist/job/<int:job_id>/', ShortlistByJobView.as_view(), name='shortlist-by-job'),
    path('shortlist/jobs/', AllShortlistJobsView.as_view(), name='all-shortlist-jobs'),
    path('shortlist/<int:pk>/', ShortlistCandidateView.as_view(), name='shortlist-candidate'),
    path('shortlist/<int:pk>/status/', UpdateShortlistStatusView.as_view(), name='update-shortlist-status'),
]