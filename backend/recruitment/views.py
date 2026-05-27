import os
import re
import json
import requests
from collections import defaultdict

from django.conf import settings
from django.core.mail import send_mail

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count

from .models import Resume, ScreeningResult, Shortlist, InterviewSchedule
from .serializers import (
    ResumeSerializer,
    ScreeningResultSerializer,
    ShortlistSerializer,
    InterviewScheduleSerializer,
)
from accounts.models import Employee
from jobs.models import JobOpening


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_email_from_text(text):
    """Extract the first email address found in resume text."""
    if not text:
        return None
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None


def extract_text_from_resume(file_path):
    """Extract plain text from a resume file (PDF or DOCX)."""
    text = ""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"[extract_text_from_resume] Error: {e}")
    return text


# ── Email template & helpers ──────────────────────────────────────────────────

DEFAULT_CANDIDATE_EMAIL_TEMPLATE = """Dear {candidate_name},

We are pleased to inform you that you have been shortlisted for the position of {job_title} at {company}.

INTERVIEW DETAILS:
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
Date        : {interview_date}
Time        : {interview_time}
Mode        : {mode}
Location    : {location}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

Please confirm your availability by replying to this email.

Best regards,
SynergyCom HR Team"""


def fill_template(template, interview, round_name="Round 1"):
    """
    Fill all supported placeholders in an email template.
    Uses .format_map with a SafeDict so unknown keys are left as-is.
    Handles interview_date/interview_time as either objects or raw strings.
    """
    from datetime import datetime as _dt

    shortlist = interview.shortlist
    sr        = shortlist.screening_result
    location  = (
        interview.meeting_link
        if interview.mode == "ONLINE"
        else (interview.venue or "To be communicated")
    )

    # Safely parse date (may be a date object or "2026-06-01" string)
    raw_date = interview.interview_date
    if isinstance(raw_date, str):
        try:
            raw_date = _dt.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            raw_date = None
    date_str = raw_date.strftime("%d %B %Y") if raw_date else str(interview.interview_date)

    # Safely parse time (may be a time object or "14:30" / "14:30:00" string)
    raw_time = interview.interview_time
    if isinstance(raw_time, str):
        try:
            raw_time = _dt.strptime(raw_time[:5], "%H:%M").time()
        except ValueError:
            raw_time = None
    time_str = raw_time.strftime("%I:%M %p") if raw_time else str(interview.interview_time)

    values = {
        "candidate_name" : sr.candidate_name,
        "job_title"      : shortlist.job_opening.title,
        "interview_date" : date_str,
        "interview_time" : time_str,
        "mode"           : interview.get_mode_display(),
        "location"       : location,
        "round"          : round_name,
        "company"        : "SynergyCom",
        # legacy aliases so older frontend templates also work
        "date"           : date_str,
        "time"           : time_str,
        "link_or_venue"  : location,
    }

    # Safe substitution — unknown placeholders are left unchanged
    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(SafeDict(values))


def send_candidate_email(interview, round_name="Round 1", subject=None, body=None):
    """Send interview notification email to candidate."""
    candidate_email = interview.shortlist.screening_result.resume.candidate_email
    if not candidate_email:
        return False, "No candidate email on record"

    if not subject:
        subject = f"Interview Invitation \u2013 {interview.shortlist.job_opening.title} ({round_name})"
    if not body:
        body = fill_template(DEFAULT_CANDIDATE_EMAIL_TEMPLATE, interview, round_name)
    else:
        body = fill_template(body, interview, round_name)

    # Also fill subject placeholders
    subject = fill_template(subject, interview, round_name)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[candidate_email],
            fail_silently=False,
        )
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


# ── Resume ────────────────────────────────────────────────────────────────────

class ResumeListUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        resumes = Resume.objects.all().order_by('-uploaded_at')
        return Response(ResumeSerializer(resumes, many=True).data)

    def post(self, request):
        serializer = ResumeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            resume = serializer.save(uploaded_by=request.user)

            # ✅ Auto-extract email from resume — never entered manually
            if not resume.candidate_email:
                try:
                    text  = extract_text_from_resume(resume.file.path)
                    email = extract_email_from_text(text)
                    if email:
                        resume.candidate_email = email
                        resume.save(update_fields=['candidate_email'])
                except Exception as e:
                    print(f"[auto-extract email] {e}")

            return Response(ResumeSerializer(resume).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResumeDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            resume = Resume.objects.get(pk=pk)
            resume.file.delete(save=False)
            resume.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Resume.DoesNotExist:
            return Response({'error': 'Resume not found'}, status=status.HTTP_404_NOT_FOUND)


# ── Screening ─────────────────────────────────────────────────────────────────

class ScreenResumesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = JobOpening.objects.get(pk=job_id)
        except JobOpening.DoesNotExist:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

        resume_ids = request.data.get('resume_ids', [])
        if not resume_ids:
            return Response({'error': 'No resumes selected'}, status=status.HTTP_400_BAD_REQUEST)

        resumes = Resume.objects.filter(id__in=resume_ids)
        if not resumes.exists():
            return Response({'error': 'No resumes found'}, status=status.HTTP_400_BAD_REQUEST)

        results = []
        for resume in resumes:
            existing = ScreeningResult.objects.filter(job_opening=job, resume=resume).first()
            if existing:
                results.append(ScreeningResultSerializer(existing).data)
                continue

            try:
                text = extract_text_from_resume(resume.file.path)
            except Exception:
                text = ""

            prompt = f"""You are an expert HR recruiter. Score how well this resume matches the job.

JOB TITLE: {job.title}
JOB DESCRIPTION: {job.description}

RESUME TEXT:
{text[:3000]}

Respond in JSON only:
{{"score": <0-100>, "reason": "<2-3 sentence explanation>"}}"""

            try:
                api_key = settings.GROQ_API_KEY
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "max_tokens": 300,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                raw  = resp.json()["choices"][0]["message"]["content"].strip()
                raw  = re.sub(r"```json|```", "", raw).strip()
                data = json.loads(raw)
                score  = int(data.get("score", 0))
                reason = data.get("reason", "")
            except Exception as e:
                score  = 0
                reason = f"Screening error: {e}"

            sr = ScreeningResult.objects.create(
                job_opening=job,
                resume=resume,
                candidate_name=resume.candidate_name,
                match_score=score,
                reason=reason,
                screened_by=request.user,
            )
            results.append(ScreeningResultSerializer(sr).data)

        return Response({
            'message': f'Screened {len(results)} candidate(s) successfully',
            'screened': len(results),
            'results': results,
        }, status=status.HTTP_200_OK)


class ScreeningResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        results = ScreeningResult.objects.filter(job_opening_id=job_id).select_related(
            'resume', 'job_opening', 'screened_by'
        )
        return Response(ScreeningResultSerializer(results, many=True).data)


class AllScreeningJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(screening_results__isnull=False).annotate(
            result_count=Count('screening_results')
        ).distinct().order_by('-result_count')
        return Response([{
            'id': j.id, 'title': j.title,
            'department': str(getattr(j, 'department', '') or ''),
            'result_count': j.result_count,
        } for j in jobs])


# ── Shortlist ─────────────────────────────────────────────────────────────────

class ShortlistCandidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, result_id):
        try:
            sr = ScreeningResult.objects.get(pk=result_id)
        except ScreeningResult.DoesNotExist:
            return Response({'error': 'Screening result not found'}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(sr, 'shortlist'):
            return Response({'error': 'Already shortlisted'}, status=status.HTTP_400_BAD_REQUEST)

        shortlist = Shortlist.objects.create(
            job_opening=sr.job_opening,
            screening_result=sr,
            shortlisted_by=request.user,
            notes=request.data.get('notes', ''),
        )
        return Response(ShortlistSerializer(shortlist).data, status=status.HTTP_201_CREATED)

    def delete(self, request, result_id):
        try:
            sr = ScreeningResult.objects.get(pk=result_id)
            sr.shortlist.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ScreeningResult.DoesNotExist, Shortlist.DoesNotExist):
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class ShortlistByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        shortlists = Shortlist.objects.filter(job_opening_id=job_id).select_related(
            'screening_result__resume', 'screening_result__job_opening',
            'shortlisted_by', 'job_opening'
        ).prefetch_related('interviews')
        return Response({'shortlisted': ShortlistSerializer(shortlists, many=True).data})


class AllShortlistJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(shortlisted_candidates__isnull=False).annotate(
            shortlist_count=Count('shortlisted_candidates')
        ).distinct().order_by('-shortlist_count')
        return Response([{
            'job_id'        : j.id,
            'job_title'     : j.title,
            'department'    : str(getattr(j, 'department', '') or ''),
            'shortlist_count': j.shortlist_count,
        } for j in jobs])


# ── Interview ─────────────────────────────────────────────────────────────────

class ScheduleInterviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, shortlist_id):
        try:
            shortlist = Shortlist.objects.get(pk=shortlist_id)
        except Shortlist.DoesNotExist:
            return Response({'error': 'Shortlist entry not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            interviewer = Employee.objects.get(pk=request.data.get('assigned_interviewer'))
        except Employee.DoesNotExist:
            return Response({'error': 'Interviewer not found'}, status=status.HTTP_400_BAD_REQUEST)

        interview = InterviewSchedule.objects.create(
            shortlist=shortlist,
            interview_date=request.data.get('interview_date'),
            interview_time=request.data.get('interview_time'),
            mode=request.data.get('mode', 'ONLINE'),
            meeting_link=request.data.get('meeting_link', ''),
            venue=request.data.get('venue', ''),
            assigned_interviewer=interviewer,
            notes=request.data.get('notes', ''),
            scheduled_by=request.user,
        )

        # ✅ Use custom subject/body from frontend if provided, else default
        email_subj = request.data.get('email_subject') or None
        email_body = request.data.get('email_body') or None

        sent, _ = send_candidate_email(
            interview,
            round_name='Round 1',
            subject=email_subj,
            body=email_body,
        )
        interview.email_sent = sent
        interview.save(update_fields=['email_sent'])

        return Response({
            **InterviewScheduleSerializer(interview).data,
            'emails_sent': {'candidate': sent},
        }, status=status.HTTP_201_CREATED)


class BulkScheduleInterviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        job_id     = request.data.get('job_id')
        date       = request.data.get('interview_date')
        time       = request.data.get('interview_time')
        mode       = request.data.get('mode', 'ONLINE')
        link       = request.data.get('meeting_link', '')
        venue      = request.data.get('venue', '')
        iv_id      = request.data.get('assigned_interviewer')
        notes      = request.data.get('notes', '')
        email_subj = request.data.get('email_subject') or None
        email_body = request.data.get('email_body') or None

        if not all([job_id, date, time, iv_id]):
            return Response(
                {'error': 'job_id, interview_date, interview_time, and assigned_interviewer are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            interviewer = Employee.objects.get(pk=iv_id)
        except Employee.DoesNotExist:
            return Response({'error': 'Interviewer not found'}, status=status.HTTP_400_BAD_REQUEST)

        # Only schedule candidates that don't have an interview yet
        pending   = Shortlist.objects.filter(job_opening_id=job_id).exclude(interviews__isnull=False)
        scheduled = 0
        skipped   = 0
        emails_ok = 0

        for shortlist in pending:
            interview = InterviewSchedule.objects.create(
                shortlist=shortlist,
                interview_date=date,
                interview_time=time,
                mode=mode,
                meeting_link=link,
                venue=venue,
                assigned_interviewer=interviewer,
                notes=notes,
                scheduled_by=request.user,
            )
            scheduled += 1

            sent, _ = send_candidate_email(
                interview,
                round_name='Round 1',
                subject=email_subj,
                body=email_body,
            )
            if sent:
                emails_ok += 1
                interview.email_sent = True
                interview.save(update_fields=['email_sent'])

        # Send consolidated interviewer email
        iv_email_sent = False
        try:
            interviews_qs = InterviewSchedule.objects.filter(
                shortlist__job_opening_id=job_id,
                assigned_interviewer=interviewer,
            ).select_related(
                'shortlist__screening_result__resume',
                'shortlist__job_opening',
                'assigned_interviewer__user',
            )

            interviewer_email = (
                getattr(getattr(interviewer, 'user', None), 'email', None)
                or getattr(interviewer, 'email', None)
            )
            interviewer_name_bulk = (
                interviewer.user.get_full_name()
                if hasattr(interviewer, 'user') and interviewer.user
                else (
                    interviewer.get_full_name()
                    if hasattr(interviewer, 'get_full_name')
                    else str(interviewer)
                )
            )

            if interviewer_email and interviews_qs.exists():
                job_title = interviews_qs.first().shortlist.job_opening.title
                lines = [
                    f"Dear {interviewer_name_bulk},",
                    "",
                    f"Here are your scheduled interviews for: {job_title}",
                    "",
                ]
                for idx, iv in enumerate(interviews_qs, 1):
                    sr       = iv.shortlist.screening_result
                    location = iv.meeting_link if iv.mode == 'ONLINE' else (iv.venue or 'TBD')
                    lines += [
                        f"CANDIDATE {idx}",
                        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
                        f"Name          : {sr.candidate_name}",
                        f"Email         : {sr.resume.candidate_email or 'Not available'}",
                        f"Match Score   : {sr.match_score}%",
                        f"AI Assessment : {sr.reason}",
                        f"Date          : {iv.interview_date.strftime('%d %B %Y')}",
                        f"Time          : {iv.interview_time.strftime('%I:%M %p')}",
                        f"Mode          : {iv.get_mode_display()}",
                        f"Location/Link : {location}",
                        f"Notes         : {iv.notes or '\u2014'}",
                        "",
                        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
                        "",
                    ]
                lines += ["Best regards,", "SynergyCom HR Team"]
                send_mail(
                    subject=f"Your Interview Schedule \u2013 {job_title}",
                    message="\n".join(lines),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[interviewer_email],
                    fail_silently=False,
                )
                iv_email_sent = True
        except Exception as e:
            print(f"[bulk-schedule] Interviewer email failed: {e}")

        return Response({
            'scheduled'               : scheduled,
            'skipped_already_scheduled': skipped,
            'emails_sent_successfully' : emails_ok,
            'interviewer_email_sent'   : iv_email_sent,
        }, status=status.HTTP_201_CREATED)


class BulkEmailView(APIView):
    """
    POST → Send a custom email to ALL shortlisted candidates for a job,
    regardless of whether they are scheduled or not.
    Body: { "job_id": 1, "email_subject": "...", "email_body": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        job_id     = request.data.get('job_id')
        email_subj = request.data.get('email_subject', '').strip()
        email_body = request.data.get('email_body', '').strip()

        if not job_id:
            return Response({'error': 'job_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not email_subj or not email_body:
            return Response({'error': 'email_subject and email_body are required'}, status=status.HTTP_400_BAD_REQUEST)

        shortlists = Shortlist.objects.filter(job_opening_id=job_id).select_related(
            'screening_result__resume', 'job_opening'
        )
        if not shortlists.exists():
            return Response({'error': 'No shortlisted candidates for this job'}, status=status.HTTP_404_NOT_FOUND)

        sent    = 0
        skipped = 0

        for shortlist in shortlists:
            sr              = shortlist.screening_result
            candidate_email = sr.resume.candidate_email
            candidate_name  = sr.candidate_name
            job_title       = shortlist.job_opening.title

            if not candidate_email:
                skipped += 1
                continue

            # Fill simple placeholders — no interview object needed
            class SafeDict(dict):
                def __missing__(self, key):
                    return "{" + key + "}"

            values = {
                'candidate_name': candidate_name,
                'job_title'     : job_title,
                'company'       : 'SynergyCom',
            }
            try:
                filled_subj = email_subj.format_map(SafeDict(values))
                filled_body = email_body.format_map(SafeDict(values))
                send_mail(
                    subject=filled_subj,
                    message=filled_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[candidate_email],
                    fail_silently=False,
                )
                sent += 1
            except Exception as e:
                print(f"[bulk-email] Failed for {candidate_name}: {e}")
                skipped += 1

        return Response({
            'sent'   : sent,
            'skipped': skipped,
            'total'  : shortlists.count(),
        })


class ResendInterviewEmailView(APIView):
    """Send another round email for an already-scheduled interview."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        shortlist_id = request.data.get('shortlist_id')
        if not shortlist_id:
            return Response({'error': 'shortlist_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            shortlist = Shortlist.objects.get(pk=shortlist_id)
        except Shortlist.DoesNotExist:
            return Response({'error': 'Shortlist entry not found'}, status=status.HTTP_404_NOT_FOUND)

        interview = shortlist.interviews.order_by('-scheduled_at').first()
        if not interview:
            return Response(
                {'error': 'No interview scheduled yet for this candidate'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        round_name     = request.data.get('round_name', 'Round 1')
        custom_subject = request.data.get('email_subject') or None
        custom_body    = request.data.get('email_body') or None

        success, msg = send_candidate_email(
            interview,
            round_name=round_name,
            subject=custom_subject,
            body=custom_body,
        )
        if success:
            return Response({
                'sent'     : True,
                'round'    : round_name,
                'candidate': shortlist.screening_result.candidate_name,
                'message'  : f'Email sent for {round_name}',
            })
        return Response({'sent': False, 'message': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendInterviewerConsolidatedEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        job_id         = request.data.get('job_id')
        interviewer_id = request.data.get('interviewer_id')

        if not job_id:
            return Response({'error': 'job_id required'}, status=status.HTTP_400_BAD_REQUEST)

        qs = InterviewSchedule.objects.filter(
            shortlist__job_opening_id=job_id
        ).select_related(
            'shortlist__screening_result__resume',
            'shortlist__job_opening',
            'assigned_interviewer',
            'assigned_interviewer__user',
        ).order_by('assigned_interviewer', 'interview_date', 'interview_time')

        if interviewer_id:
            qs = qs.filter(assigned_interviewer_id=interviewer_id)

        if not qs.exists():
            return Response({'error': 'No interviews found for this job'}, status=status.HTTP_404_NOT_FOUND)

        by_interviewer = defaultdict(list)
        for iv in qs:
            by_interviewer[iv.assigned_interviewer].append(iv)

        sent_to = []
        for interviewer, ivs in by_interviewer.items():
            # Employee model uses a user FK — email lives on user
            interviewer_email = (
                getattr(getattr(interviewer, 'user', None), 'email', None)
                or getattr(interviewer, 'email', None)
            )
            print(f"[interviewer-email] {interviewer} -> email={interviewer_email}")
            interviewer_name = (
                interviewer.user.get_full_name()
                if hasattr(interviewer, 'user') and interviewer.user
                else (
                    interviewer.get_full_name()
                    if hasattr(interviewer, 'get_full_name')
                    else str(interviewer)
                )
            )
            if not interviewer_email:
                continue

            job_title = ivs[0].shortlist.job_opening.title
            lines = [
                f"Dear {interviewer_name},", "",
                f"Here are your scheduled interviews for: {job_title}", "",
            ]
            for idx, iv in enumerate(ivs, 1):
                sr       = iv.shortlist.screening_result
                location = iv.meeting_link if iv.mode == "ONLINE" else (iv.venue or "TBD")
                lines += [
                    f"CANDIDATE {idx}",
                    f"\u2500" * 37,
                    f"Name          : {sr.candidate_name}",
                    f"Email         : {sr.resume.candidate_email or 'Not available'}",
                    f"Match Score   : {sr.match_score}%",
                    f"AI Assessment : {sr.reason}",
                    f"Shortlist Note: {iv.shortlist.notes or '\u2014'}",
                    "",
                    f"INTERVIEW SLOT",
                    f"Date          : {iv.interview_date.strftime('%d %B %Y')}",
                    f"Time          : {iv.interview_time.strftime('%I:%M %p')}",
                    f"Mode          : {iv.get_mode_display()}",
                    f"Location/Link : {location}",
                    f"Interview Note: {iv.notes or '\u2014'}",
                    "",
                    "\u2501" * 37, "",
                ]
            lines += ["Best regards,", "SynergyCom HR Team"]

            try:
                send_mail(
                    subject=f"Your Interview Schedule \u2013 {job_title}",
                    message="\n".join(lines),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[interviewer_email],
                    fail_silently=False,
                )
                sent_to.append(interviewer_name)
            except Exception as e:
                print(f"[send-interviewer-email] Failed for {interviewer}: {e}")

        if sent_to:
            return Response({'sent': True, 'sent_to': sent_to, 'total': len(sent_to)})
        return Response(
            {'sent': False, 'message': 'No emails sent (check interviewer email addresses)'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class InterviewsByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        interviews = InterviewSchedule.objects.filter(
            shortlist__job_opening_id=job_id
        ).select_related(
            'shortlist__screening_result__resume',
            'shortlist__job_opening',
            'assigned_interviewer',
            'scheduled_by',
        )
        return Response({'interviews': InterviewScheduleSerializer(interviews, many=True).data})


class AllInterviewJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            shortlisted_candidates__interviews__isnull=False
        ).annotate(
            interview_count=Count('shortlisted_candidates__interviews')
        ).distinct()
        return Response([{
            'job_id'        : j.id,
            'job_title'     : j.title,
            'department'    : str(getattr(j, 'department', '') or ''),
            'interview_count': j.interview_count,
        } for j in jobs])


class AllInterviewsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        interviews = InterviewSchedule.objects.all().select_related(
            'shortlist__screening_result__resume',
            'shortlist__job_opening',
            'assigned_interviewer',
            'scheduled_by',
        ).order_by('-scheduled_at')
        return Response(InterviewScheduleSerializer(interviews, many=True).data)