import logging
import os
import re
import tempfile
from datetime import datetime as _dt

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.generics import DestroyAPIView

from .models import ScreeningResult, Shortlist, InterviewSchedule
from .candidate_model import Candidate
from .serializers import (
    ScreeningResultSerializer,
    ShortlistSerializer,
    InterviewScheduleSerializer,
)
from .rag_pipeline import process_resume_upload, run_rag_screening
from accounts.models import Employee
from jobs.models import JobOpening

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_name(value):
    if not value:
        return value
    return " ".join(str(value).split())


def extract_text_from_resume(file_path):
    text = ""
    ext  = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
            if not text.strip():
                text = _ocr_fallback(file_path)
        elif ext in (".docx", ".doc"):
            import docx
            doc  = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        logger.error("[extract_text] %s", e)
    return text


def _ocr_fallback(file_path):
    text = ""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        pytesseract.pytesseract.tesseract_cmd = getattr(
            settings, "TESSERACT_CMD",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        pages = convert_from_path(
            file_path, dpi=300,
            poppler_path=getattr(settings, "POPPLER_PATH",
                                 r"C:\poppler\poppler-26.02.0\Library\bin"),
        )
        for page_image in pages:
            t = pytesseract.image_to_string(page_image, lang="eng")
            if t:
                text += t + "\n"
    except Exception as e:
        logger.error("[OCR] %s", e)
    return text


# ── BULK UPLOAD ───────────────────────────────────────────────────────────────

class BulkUploadView(APIView):
    """POST /api/recruitment/bulk-upload/"""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]
    ALLOWED_EXT        = {".pdf", ".docx"}

    def post(self, request):
        files = request.FILES.getlist("resumes")
        if not files:
            return Response(
                {"error": "No files provided. Send files under the 'resumes' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results, success, failed = [], 0, 0

        for file_obj in files:
            original_name = file_obj.name
            _, ext        = os.path.splitext(original_name)
            ext           = ext.lower()

            if ext not in self.ALLOWED_EXT:
                results.append({"filename": original_name, "status": "failed",
                                 "error": f"Unsupported type '{ext}'"})
                failed += 1
                continue

            file_bytes = file_obj.read()
            if not file_bytes:
                results.append({"filename": original_name, "status": "failed",
                                 "error": "File is empty"})
                failed += 1
                continue

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                text = extract_text_from_resume(tmp_path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            if not text.strip():
                results.append({"filename": original_name, "status": "failed",
                                 "error": "Could not extract text"})
                failed += 1
                continue

            try:
                candidate = process_resume_upload(
                    text            = text,
                    source_filename = original_name,
                    file_bytes      = file_bytes,
                )
                results.append({
                    "filename"      : original_name,
                    "status"        : "success",
                    "candidate_id"  : candidate.id,
                    "candidate_name": clean_name(candidate.full_name),
                    "email"         : candidate.email,
                    "is_embedded"   : candidate.is_embedded,
                })
                success += 1
            except Exception as exc:
                logger.error("[BulkUpload] Failed %s: %s", original_name, exc)
                results.append({"filename": original_name, "status": "failed",
                                 "error": str(exc)})
                failed += 1

        return Response({
            "total": len(files), "success": success,
            "failed": failed, "results": results,
        }, status=status.HTTP_201_CREATED)


# ── SINGLE UPLOAD ─────────────────────────────────────────────────────────────

class ScreenUploadView(APIView):
    """POST /api/recruitment/upload/"""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]
    ALLOWED_EXT        = {".pdf", ".docx"}

    def post(self, request):
        file_obj = request.FILES.get("resume")
        if not file_obj:
            return Response({"error": "No file provided under 'resume' field."},
                            status=status.HTTP_400_BAD_REQUEST)

        original_name = file_obj.name
        _, ext        = os.path.splitext(original_name)
        ext           = ext.lower()

        if ext not in self.ALLOWED_EXT:
            return Response({"error": f"Unsupported type '{ext}'. Only .pdf and .docx."},
                            status=status.HTTP_400_BAD_REQUEST)

        file_bytes = file_obj.read()
        if not file_bytes:
            return Response({"error": "File is empty."}, status=status.HTTP_400_BAD_REQUEST)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            text = extract_text_from_resume(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if not text.strip():
            return Response({"error": "Could not extract text from resume."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            candidate = process_resume_upload(
                text=text, source_filename=original_name, file_bytes=file_bytes
            )
        except Exception as exc:
            return Response({"error": f"Processing error: {exc}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message"      : "Resume uploaded and processed successfully.",
            "candidate_id" : candidate.id,
            "candidate_name": clean_name(candidate.full_name),
            "email"        : candidate.email,
            "phone"        : candidate.phone,
            "is_embedded"  : candidate.is_embedded,
        }, status=status.HTTP_201_CREATED)


# ── RAG SCREENING ─────────────────────────────────────────────────────────────

class RAGScreeningView(APIView):
    """POST /api/recruitment/rag-screen/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        job_id          = request.data.get("job_id")
        top_k           = int(request.data.get("top_k", 20))
        score_threshold = int(request.data.get("score_threshold", 80))

        if not job_id:
            return Response({"error": "job_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = JobOpening.objects.get(pk=job_id)
        except JobOpening.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            rag_result = run_rag_screening(
                job=job, request_user=request.user,
                top_k=top_k, score_threshold=score_threshold,
            )
        except Exception as exc:
            logger.exception("[RAGScreeningView] %s", exc)
            return Response({"error": f"Screening error: {exc}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        enriched = []
        for r in rag_result.get("results", []):
            # NOTE: removed `resume_source="LOCAL"` — ScreeningResult model has
            # no such field (see FieldError in logs). If you want to track this,
            # add `resume_source` to the model + migrate, then reintroduce it here.
            sr, created = ScreeningResult.objects.get_or_create(
                job_opening     = job,
                source_filename = r["source_filename"],
                defaults={
                    "candidate_name" : clean_name(r["candidate_name"]),
                    "candidate_email": r.get("candidate_email"),
                    "match_score"    : r["match_score"],
                    "reason"         : r["reason"],
                    "screened_by"    : request.user,
                }
            )
            if not created:
                sr.candidate_name = clean_name(r["candidate_name"])
                sr.match_score    = r["match_score"]
                sr.reason         = r["reason"]
                sr.save(update_fields=["candidate_name", "match_score", "reason"])

            is_shortlisted = False
            shortlist_id   = None

            if r["match_score"] >= score_threshold:
                shortlist, _ = Shortlist.objects.get_or_create(
                    job_opening      = job,
                    screening_result = sr,
                    defaults={
                        "shortlisted_by": request.user,
                        "notes": f'Auto-shortlisted — score: {r["match_score"]}% (threshold: {score_threshold}%)',
                    }
                )
                is_shortlisted = True
                shortlist_id   = shortlist.id

            enriched.append({
                **r,
                "candidate_name"    : clean_name(r["candidate_name"]),
                "screening_result_id": sr.id,
                "is_shortlisted"    : is_shortlisted,
                "shortlist_id"      : shortlist_id,
            })

        rag_result["results"] = enriched
        return Response(rag_result, status=status.HTTP_200_OK)


# ── SCREENING RESULTS ─────────────────────────────────────────────────────────

class ScreeningResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        results = ScreeningResult.objects.filter(
            job_opening_id=job_id
        ).select_related("job_opening", "screened_by")

        data = ScreeningResultSerializer(results, many=True).data
        shortlisted_filenames = set(
            Shortlist.objects.filter(job_opening_id=job_id)
            .values_list("screening_result__source_filename", flat=True)
        )
        for item in data:
            item["is_shortlisted"] = item.get("source_filename", "") in shortlisted_filenames
            if item.get("candidate_name"):
                item["candidate_name"] = clean_name(item["candidate_name"])
        return Response(data)


class AllScreeningJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            screening_results__isnull=False
        ).annotate(result_count=Count("screening_results")).distinct().order_by("-result_count")
        return Response([{
            "id": j.id, "title": j.title,
            "department": str(getattr(j, "department", "") or ""),
            "result_count": j.result_count,
            "status": j.status,
            "is_closed": j.status == "CLOSED",
        } for j in jobs])


# ── SHORTLIST ─────────────────────────────────────────────────────────────────

class ShortlistCandidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
        except ScreeningResult.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if hasattr(sr, "shortlist"):
            return Response({"error": "Already shortlisted"}, status=status.HTTP_400_BAD_REQUEST)
        shortlist = Shortlist.objects.create(
            job_opening=sr.job_opening, screening_result=sr,
            shortlisted_by=request.user, notes=request.data.get("notes", ""),
        )
        return Response({"shortlist_id": shortlist.id,
                         "candidate_name": clean_name(sr.candidate_name)},
                        status=status.HTTP_201_CREATED)

    def delete(self, request, sr_id):
        try:
            sr = ScreeningResult.objects.get(pk=sr_id)
            sr.shortlist.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ScreeningResult.DoesNotExist, Shortlist.DoesNotExist):
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class ShortlistByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        shortlists = Shortlist.objects.filter(job_opening_id=job_id).select_related(
            "screening_result", "screening_result__job_opening",
            "shortlisted_by", "job_opening"
        ).prefetch_related("interviews")
        data = ShortlistSerializer(shortlists, many=True).data
        for item in data:
            item["candidate_name"]  = clean_name(item.get("candidate_name", ""))
            item["candidate_email"] = (item.get("candidate_email") or "").strip()
        return Response({"shortlisted": data})


class AllShortlistJobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = JobOpening.objects.filter(
            shortlisted_candidates__isnull=False
        ).annotate(shortlist_count=Count("shortlisted_candidates")).distinct()
        return Response([{
            "job_id": j.id, "job_title": j.title,
            "department": str(getattr(j, "department", "") or ""),
            "shortlist_count": j.shortlist_count,
            "status": j.status,
            "is_closed": j.status == "CLOSED",
        } for j in jobs])


class UpdateShortlistStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            shortlist = Shortlist.objects.select_related(
                "screening_result", "job_opening"
            ).get(pk=pk)
        except Shortlist.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status")
        allowed    = ["SHORTLISTED", "SCHEDULED", "HIRED", "REJECTED"]
        if new_status not in allowed:
            return Response({"error": f"Allowed: {allowed}"}, status=status.HTTP_400_BAD_REQUEST)

        shortlist.status = new_status
        shortlist.save(update_fields=["status"])

        email_sent, email_message = None, None
        if new_status in ("HIRED", "REJECTED"):
            subject = request.data.get("email_subject")
            body    = request.data.get("email_body")
            email_sent, email_message = send_status_email(shortlist, new_status, subject, body)

        return Response({
            "status"       : new_status,
            "email_sent"   : email_sent,
            "email_message": email_message,
        })


# ── CANDIDATE POOL ────────────────────────────────────────────────────────────

class CandidateListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidates = Candidate.objects.all().order_by("-created_at")
        shortlisted_filenames = set(
            Shortlist.objects.values_list("screening_result__source_filename", flat=True)
        )
        data = [{
            "id"             : c.id,
            "full_name"      : clean_name(c.full_name),
            "email"          : c.email,
            "phone"          : c.phone,
            "source_filename": c.source_filename,
            "is_embedded"    : c.is_embedded,
            "is_shortlisted" : c.source_filename in shortlisted_filenames,
            "created_at"     : c.created_at.isoformat(),
        } for c in candidates]
        return Response(data)


class CandidateCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": Candidate.objects.filter(is_embedded=True).count()})


class CandidateDeleteView(DestroyAPIView):
    queryset           = Candidate.objects.all()
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        candidate = self.get_object()
        try:
            import chromadb
            client     = chromadb.PersistentClient(path=str(settings.CHROMA_DB_PATH))
            collection = client.get_collection(name=settings.CHROMA_COLLECTION_NAME)
            collection.delete(where={"candidate_id": str(candidate.id)})
        except Exception as e:
            logger.warning("[CandidateDelete] ChromaDB: %s", e)

        resumes_dir = os.path.join(settings.MEDIA_ROOT, "resumes")
        for fname in [candidate.source_filename]:
            if fname:
                path = os.path.join(resumes_dir, fname)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        candidate.delete()
        return Response(
            {"message": f'Candidate "{clean_name(candidate.full_name)}" deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


# ── EMAIL HELPERS ─────────────────────────────────────────────────────────────

DEFAULT_EMAIL_TEMPLATE = """Dear {candidate_name},

We are pleased to inform you that you have been shortlisted for the position of {job_title} at {company}.

INTERVIEW DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━
Date     : {interview_date}
Time     : {interview_time}
Mode     : {mode}
Location : {location}
━━━━━━━━━━━━━━━━━━━━━━━━

Please confirm your availability by replying to this email.

Best regards,
HR Team"""


def fill_template(template, interview, round_name="Round 1"):
    shortlist = interview.shortlist
    sr        = shortlist.screening_result
    location  = (interview.meeting_link if interview.mode == "ONLINE"
                 else (interview.venue or "To be communicated"))

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

    class SafeDict(dict):
        def __missing__(self, key): return "{" + key + "}"

    return template.format_map(SafeDict({
        "candidate_name": clean_name(sr.candidate_name),
        "job_title"     : shortlist.job_opening.title,
        "interview_date": date_str,
        "interview_time": time_str,
        "mode"          : interview.get_mode_display(),
        "location"      : location,
        "round"         : round_name,
        "company"       : "SynergyCom",
    }))


def send_candidate_email(interview, round_name="Round 1", subject=None, body=None):
    email = interview.shortlist.screening_result.candidate_email
    if not email:
        return False, "No candidate email on record"
    if not subject:
        subject = f"Interview Invitation – {interview.shortlist.job_opening.title} ({round_name})"
    body = fill_template(body or DEFAULT_EMAIL_TEMPLATE, interview, round_name)
    subject = fill_template(subject, interview, round_name)
    try:
        send_mail(subject=subject, message=body,
                  from_email=settings.DEFAULT_FROM_EMAIL,
                  recipient_list=[email], fail_silently=False)
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


def send_status_email(shortlist, new_status, subject=None, body=None):
    """Send a HIRED/REJECTED notification email using custom subject/body
    from the kanban modal. Does not require an InterviewSchedule."""
    sr    = shortlist.screening_result
    email = sr.candidate_email
    if not email:
        return False, "No candidate email on record"
    if not subject or not body:
        return False, "Subject and body are required"

    class SafeDict(dict):
        def __missing__(self, key): return "{" + key + "}"

    ctx = SafeDict({
        "candidate_name": clean_name(sr.candidate_name),
        "job_title"     : shortlist.job_opening.title,
        "company"       : "SynergyCom",
        "status"        : new_status,
    })
    try:
        filled_subject = subject.format_map(ctx)
        filled_body    = body.format_map(ctx)
    except Exception:
        filled_subject, filled_body = subject, body

    try:
        send_mail(subject=filled_subject, message=filled_body,
                  from_email=settings.DEFAULT_FROM_EMAIL,
                  recipient_list=[email], fail_silently=False)
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


# ── INTERVIEW ─────────────────────────────────────────────────────────────────

class ScheduleInterviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, shortlist_id):
        try:
            shortlist = Shortlist.objects.get(pk=shortlist_id)
        except Shortlist.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            interviewer = Employee.objects.get(pk=request.data.get("assigned_interviewer"))
        except Employee.DoesNotExist:
            return Response({"error": "Interviewer not found"}, status=status.HTTP_400_BAD_REQUEST)

        interview = InterviewSchedule.objects.create(
            shortlist            = shortlist,
            interview_date       = request.data.get("interview_date"),
            interview_time       = request.data.get("interview_time"),
            mode                 = request.data.get("mode", "ONLINE"),
            meeting_link         = request.data.get("meeting_link", ""),
            venue                = request.data.get("venue", ""),
            assigned_interviewer = interviewer,
            notes                = request.data.get("notes", ""),
            scheduled_by         = request.user,
        )
        sent, msg = send_candidate_email(
            interview, round_name="Round 1",
            subject=request.data.get("email_subject") or None,
            body=request.data.get("email_body") or None,
        )
        interview.email_sent = sent
        interview.save(update_fields=["email_sent"])

        return Response({
            **InterviewScheduleSerializer(interview).data,
            "emails_sent": {"candidate": sent}, "email_message": msg,
        }, status=status.HTTP_201_CREATED)


class ResendRoundEmailView(APIView):
    """POST /api/recruitment/interview/resend-email/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        shortlist_id = request.data.get("shortlist_id")
        round_name   = request.data.get("round_name", "Round")
        subject      = request.data.get("email_subject")
        body         = request.data.get("email_body")

        if not shortlist_id:
            return Response({"sent": False, "message": "shortlist_id is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            shortlist = Shortlist.objects.select_related(
                "screening_result", "job_opening"
            ).get(pk=shortlist_id)
        except Shortlist.DoesNotExist:
            return Response({"sent": False, "message": "Shortlist not found"},
                            status=status.HTTP_404_NOT_FOUND)

        email = shortlist.screening_result.candidate_email
        if not email:
            return Response({"sent": False, "message": "No candidate email on record"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Reuse the most recent scheduled interview for date/time/mode/location
        interview = InterviewSchedule.objects.filter(
            shortlist=shortlist
        ).order_by("-scheduled_at").first()

        if not interview:
            return Response(
                {"sent": False, "message": "No interview scheduled yet for this candidate"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sent, msg = send_candidate_email(
            interview, round_name=round_name,
            subject=subject or None, body=body or None,
        )
        return Response({
            "sent"     : sent,
            "message"  : msg,
            "round"    : round_name,
            "candidate": clean_name(shortlist.screening_result.candidate_name),
        }, status=status.HTTP_200_OK if sent else status.HTTP_502_BAD_GATEWAY)


class InterviewsByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        interviews = InterviewSchedule.objects.filter(
            shortlist__job_opening_id=job_id
        ).select_related("shortlist__screening_result", "shortlist__job_opening",
                         "assigned_interviewer", "scheduled_by")
        return Response({"interviews": InterviewScheduleSerializer(interviews, many=True).data})


class AllInterviewsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        interviews = InterviewSchedule.objects.all().select_related(
            "shortlist__screening_result", "shortlist__job_opening",
            "assigned_interviewer", "scheduled_by",
        ).order_by("-scheduled_at")
        return Response(InterviewScheduleSerializer(interviews, many=True).data)