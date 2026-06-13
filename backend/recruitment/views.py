


import os
import re
import json
import requests
from datetime import datetime as _dt

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import ScreeningResult, Shortlist, InterviewSchedule
from .serializers import (
    ScreeningResultSerializer,
    ShortlistSerializer,
    InterviewScheduleSerializer,
)
from accounts.models import Employee
from jobs.models import JobOpening


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def extract_email_from_text(text):
    if not text:
        return None
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None


def extract_text_from_resume(file_path):
    text = ""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"

            # If pdfplumber got nothing → scanned PDF → use OCR
            if not text.strip():
                print(f"[extract_text] No text found, trying OCR: {file_path}")
                text = extract_text_with_ocr(file_path)

        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])

    except Exception as e:
        print(f"[extract_text] {e}")
    return text


def extract_text_with_ocr(file_path):
    """Fallback OCR for scanned/image-based PDFs using Tesseract."""
    text = ""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )

        pages = convert_from_path(file_path, dpi=300, poppler_path=r"C:\poppler\poppler-26.02.0\Library\bin")
        for i, page_image in enumerate(pages):
            page_text = pytesseract.image_to_string(page_image, lang='eng')
            if page_text:
                text += page_text + "\n"
            print(f"[OCR] Page {i+1} extracted {len(page_text)} chars")

    except Exception as e:
        print(f"[OCR error] {e}")
    return text


def _score_resume(job, fname, file_path, request_user):
    """
    Extract text from file_path, call LLM, save and return a
    ScreeningResult. Re-uses an existing DB row if one exists.
    """
    # Re-use existing result if already screened for this job + filename
    existing = ScreeningResult.objects.filter(
        job_opening=job, source_filename=fname
    ).first()
    if existing:
        return ScreeningResultSerializer(existing).data

    # Extract text + email
    try:
        text  = extract_text_from_resume(file_path)
        email = extract_email_from_text(text)
    except Exception:
        text  = ''
        email = None

    raw_name     = os.path.splitext(fname)[0]
    display_name = re.sub(r'[_\-]+', ' ', raw_name).title()

    # LLM scoring
    prompt = f"""You are an expert HR recruiter. Score how well this resume matches the job.

JOB TITLE: {job.title}
JOB DESCRIPTION: {job.description}

RESUME TEXT:
{text[:3000]}

Also extract the candidate's full name from the resume if clearly visible.

Respond in JSON only — no markdown, no explanation:
{{"score": <0-100>, "reason": "<2-3 sentence explanation>", "name": "<candidate full name or empty string>"}}"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
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

        score          = int(data.get("score", 0))
        reason         = data.get("reason", "")
        llm_name       = (data.get("name") or "").strip()
        candidate_name = llm_name or display_name

    except Exception as e:
        score          = 0
        reason         = f"Screening error: {e}"
        candidate_name = display_name

    sr = ScreeningResult.objects.create(
        job_opening    = job,
        source_filename= fname,
        candidate_name = candidate_name,
        candidate_email= email,
        match_score    = score,
        reason         = reason,
        screened_by    = request_user,
    )
    return ScreeningResultSerializer(sr).data


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN BY FOLDER PATH  (new — replaces folder-screen)
# ══════════════════════════════════════════════════════════════════════════════

class ScreenByPathView(APIView):
    """
    POST /api/recruitment/screen-by-path/
    Body: { "folder_path": "C:\\Users\\HR\\Resumes", "job_id": 5 }

    Reads ALL PDF/DOC/DOCX files from the given folder_path on the server,
    scores each with the LLM, saves ScreeningResult rows, returns ranked list.
    """
    permission_classes = [IsAuthenticated]

    ALLOWED_EXT = {'.pdf', '.doc', '.docx'}

    def post(self, request):
        folder_path = (request.data.get('folder_path') or '').strip()
        job_id      = request.data.get('job_id')

        if not folder_path:
            return Response(
                {'error': 'folder_path is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not job_id:
            return Response(
                {'error': 'job_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate job
        try:
            job = JobOpening.objects.get(pk=job_id)
        except JobOpening.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate folder
        if not os.path.isdir(folder_path):
            return Response(
                {'error': f'Folder not found or not accessible: {folder_path}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Collect resume files
        try:
            candidates = [
                f for f in sorted(os.listdir(folder_path))
                if os.path.splitext(f)[1].lower() in self.ALLOWED_EXT
            ]
        except PermissionError:
            return Response(
                {'error': f'Permission denied reading folder: {folder_path}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not candidates:
            return Response(
                {'error': 'No PDF/DOC/DOCX files found in the specified folder'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        for fname in candidates:
            file_path = os.path.join(folder_path, fname)
            if not os.path.isfile(file_path):
                continue
            row = _score_resume(job, fname, file_path, request.user)
            results.append(row)

        results.sort(key=lambda r: r['match_score'], reverse=True)

        return Response({
            'job_id'   : job.id,
            'job_title': job.title,
            'folder'   : folder_path,
            'total'    : len(results),
            'results'  : results,
        })


# ══════════════════════════════════════════════════════════════════════════════
# SCREENING — read results
# ══════════════════════════════════════════════════════════════════════════════

class ScreeningResultsView(APIView):
    """GET /api/recruitment/results/<job_id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        results = ScreeningResult.objects.filter(
            job_opening_id=job_id
        ).select_related('job_opening', 'screened_by')
        return Response(ScreeningResultSerializer(results, many=True).data)


class AllScreeningJobsView(APIView):
    """GET /api/recruitment/results/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            screening_results__isnull=False
        ).annotate(
            result_count=Count('screening_results')
        ).distinct().order_by('-result_count')
        return Response([{
            'id'          : j.id,
            'title'       : j.title,
            'department'  : str(getattr(j, 'department', '') or ''),
            'result_count': j.result_count,
        } for j in jobs])


# ══════════════════════════════════════════════════════════════════════════════
# SHORTLIST
# ══════════════════════════════════════════════════════════════════════════════

class ShortlistCandidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
        except ScreeningResult.DoesNotExist:
            return Response({'error': 'Screening result not found'}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(sr, 'shortlist'):
            return Response({'error': 'Already shortlisted'}, status=status.HTTP_400_BAD_REQUEST)

        shortlist = Shortlist.objects.create(
            job_opening     = sr.job_opening,
            screening_result= sr,
            shortlisted_by  = request.user,
            notes           = request.data.get('notes', ''),
        )
        return Response({
            'shortlist_id'  : shortlist.id,
            'candidate_name': sr.candidate_name,
        }, status=status.HTTP_201_CREATED)

    def patch(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
        except ScreeningResult.DoesNotExist:
            return Response({'error': 'Screening result not found'}, status=status.HTTP_404_NOT_FOUND)

        if not hasattr(sr, 'shortlist'):
            return Response({'error': 'Candidate is not shortlisted yet'}, status=status.HTTP_400_BAD_REQUEST)

        shortlist = sr.shortlist
        if 'notes' in request.data:
            shortlist.notes = request.data['notes']
        if 'status' in request.data:
            allowed = ['SHORTLISTED', 'SCHEDULED', 'HIRED', 'REJECTED']
            if request.data['status'] not in allowed:
                return Response({'error': f'Invalid status. Allowed: {allowed}'}, status=400)
            shortlist.status = request.data['status']
        shortlist.save()

        return Response({
            'shortlist_id'  : shortlist.id,
            'candidate_name': sr.candidate_name,
            'status'        : shortlist.status,
        })

    def delete(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
            sr.shortlist.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ScreeningResult.DoesNotExist, Shortlist.DoesNotExist):
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class ShortlistByJobView(APIView):
    """GET /api/recruitment/shortlist/job/<job_id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        shortlists = Shortlist.objects.filter(
            job_opening_id=job_id
        ).select_related(
            'screening_result', 'screening_result__job_opening',
            'shortlisted_by', 'job_opening'
        ).prefetch_related('interviews')
        return Response({'shortlisted': ShortlistSerializer(shortlists, many=True).data})


class AllShortlistJobsView(APIView):
    """GET /api/recruitment/shortlist/jobs/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            shortlisted_candidates__isnull=False
        ).annotate(
            shortlist_count=Count('shortlisted_candidates')
        ).distinct().order_by('-shortlist_count')
        return Response([{
            'job_id'         : j.id,
            'job_title'      : j.title,
            'department'     : str(getattr(j, 'department', '') or ''),
            'shortlist_count': j.shortlist_count,
        } for j in jobs])


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_CANDIDATE_EMAIL_TEMPLATE = """Dear {candidate_name},

We are pleased to inform you that you have been shortlisted for the position of {job_title} at {company}.

INTERVIEW DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━
Date        : {interview_date}
Time        : {interview_time}
Mode        : {mode}
Location    : {location}
━━━━━━━━━━━━━━━━━━━━━━━━

Please confirm your availability by replying to this email.

Best regards,
SynergyCom HR Team"""


def fill_template(template, interview, round_name="Round 1"):
    shortlist = interview.shortlist
    sr        = shortlist.screening_result

    location = (
        interview.meeting_link
        if interview.mode == "ONLINE"
        else (interview.venue or "To be communicated")
    )

    raw_date = interview.interview_date
    if isinstance(raw_date, str):
        try:
            raw_date = _dt.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            raw_date = None
    date_str = raw_date.strftime("%d %B %Y") if raw_date else str(interview.interview_date)

    raw_time = interview.interview_time
    if isinstance(raw_time, str):
        try:
            raw_time = _dt.strptime(raw_time[:5], "%H:%M").time()
        except ValueError:
            raw_time = None
    time_str = raw_time.strftime("%I:%M %p") if raw_time else str(interview.interview_time)

    values = {
        "candidate_name": sr.candidate_name,
        "job_title"     : shortlist.job_opening.title,
        "interview_date": date_str,
        "interview_time": time_str,
        "mode"          : interview.get_mode_display(),
        "location"      : location,
        "round"         : round_name,
        "company"       : "SynergyCom",
        "date"          : date_str,
        "time"          : time_str,
        "link_or_venue" : location,
    }

    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(SafeDict(values))


def send_candidate_email(interview, round_name="Round 1", subject=None, body=None):
    candidate_email = interview.shortlist.screening_result.candidate_email
    if not candidate_email:
        return False, "No candidate email on record"

    if not subject:
        subject = f"Interview Invitation – {interview.shortlist.job_opening.title} ({round_name})"
    if not body:
        body = fill_template(DEFAULT_CANDIDATE_EMAIL_TEMPLATE, interview, round_name)
    else:
        body = fill_template(body, interview, round_name)

    subject = fill_template(subject, interview, round_name)

    try:
        send_mail(
            subject      = subject,
            message      = body,
            from_email   = settings.DEFAULT_FROM_EMAIL,
            recipient_list=[candidate_email],
            fail_silently= False,
        )
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# INTERVIEW
# ══════════════════════════════════════════════════════════════════════════════

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
            shortlist           = shortlist,
            interview_date      = request.data.get('interview_date'),
            interview_time      = request.data.get('interview_time'),
            mode                = request.data.get('mode', 'ONLINE'),
            meeting_link        = request.data.get('meeting_link', ''),
            venue               = request.data.get('venue', ''),
            assigned_interviewer= interviewer,
            notes               = request.data.get('notes', ''),
            scheduled_by        = request.user,
        )

        sent, msg = send_candidate_email(
            interview,
            round_name  = 'Round 1',
            subject     = request.data.get('email_subject') or None,
            body        = request.data.get('email_body') or None,
        )
        interview.email_sent = sent
        interview.save(update_fields=['email_sent'])

        return Response({
            **InterviewScheduleSerializer(interview).data,
            'emails_sent'  : {'candidate': sent},
            'email_message': msg,
        }, status=status.HTTP_201_CREATED)


class ResendInterviewEmailView(APIView):
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

        round_name = request.data.get('round_name', 'Round 1')
        success, msg = send_candidate_email(
            interview,
            round_name = round_name,
            subject    = request.data.get('email_subject') or None,
            body       = request.data.get('email_body') or None,
        )
        if success:
            return Response({
                'sent'     : True,
                'round'    : round_name,
                'candidate': shortlist.screening_result.candidate_name,
                'message'  : f'Email sent for {round_name}',
            })
        return Response({'sent': False, 'message': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InterviewsByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        interviews = InterviewSchedule.objects.filter(
            shortlist__job_opening_id=job_id
        ).select_related(
            'shortlist__screening_result',
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
            'shortlist__screening_result',
            'shortlist__job_opening',
            'assigned_interviewer',
            'scheduled_by',
        ).order_by('-scheduled_at')
        return Response(InterviewScheduleSerializer(interviews, many=True).data)


class UpdateShortlistStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            shortlist = Shortlist.objects.get(pk=pk)
        except Shortlist.DoesNotExist:
            return Response({'error': 'Shortlist entry not found'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        allowed    = ['SHORTLISTED', 'SCHEDULED', 'HIRED', 'REJECTED']

        if new_status not in allowed:
            return Response(
                {'error': f'Invalid status. Allowed: {allowed}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shortlist.status = new_status
        shortlist.save(update_fields=['status'])

        messages = {
            'SHORTLISTED': 'Candidate returned to Shortlist.',
            'SCHEDULED'  : 'Candidate status updated to Scheduled.',
            'HIRED'      : 'Candidate marked as Selected / Hired.',
            'REJECTED'   : 'Candidate rejected and archived.',
        }
        return Response({'status': new_status, 'message': messages[new_status]})