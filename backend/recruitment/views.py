import os
import json
import requests

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Resume, ScreeningResult
from .serializers import ResumeSerializer, ScreeningResultSerializer
from jobs.models import JobOpening
from accounts.permissions import IsAdminOrHR


# ── Helper: check if user is in Recruitment department ───────────────────────

def is_recruitment(user):
    """Returns True if the employee belongs to the Recruitment department."""
    return (
        user.department and
        user.department.name.strip().upper() == 'RECRUITMENT'
    )


# ── Helper: extract text from uploaded file ───────────────────────────────────

def extract_text_from_file(file_field):
    path = file_field.path
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.pdf':
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return '\n'.join(
                    page.extract_text() or '' for page in pdf.pages
                ).strip()
        elif ext in ['.docx', '.doc']:
            import docx
            doc = docx.Document(path)
            return '\n'.join(p.text for p in doc.paragraphs).strip()
    except Exception:
        return ''
    return ''


# ── Helper: call LLM ──────────────────────────────────────────────────────────

    
def call_llm_for_screening(job, resumes_data):
    jd_text = f"""
Job Title: {job.title}
Department: {job.department.name}
Experience Required: {job.experience}
Role Summary: {job.role_summary or ''}
Responsibilities: {job.responsibilities or ''}
Required Skills: {job.required_skills_desc or ''}
Preferred Skills: {job.preferred_skills or ''}
Technologies: {job.technologies or ''}
Description: {job.description or ''}
""".strip()

    resumes_text = "\n\n".join([
        f"--- RESUME {r['id']} | {r['name']} ---\n{r['text']}"
        for r in resumes_data
    ])

    prompt = f"""
You are an expert HR recruiter. Below is a Job Description and a set of candidate resumes.

For each resume, evaluate how well the candidate matches the job description.
Return a JSON array ONLY — no explanation, no markdown.

Format:
[
  {{
    "id": <resume_id as integer>,
    "name": "<candidate name>",
    "score": <match score 0-100>,
    "reason": "<2-3 sentence explanation of why this score>"
  }}
]

Rules:
- Score 80-100: Excellent match
- Score 60-79: Good match
- Score 40-59: Partial match
- Score 0-39: Poor match

JOB DESCRIPTION:
{jd_text}

RESUMES:
{resumes_text}

Return ONLY the JSON array.
"""

    api_key = os.environ.get('GROQ_API_KEY', '')
    print("GROQ KEY:", api_key)

    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                 'model': 'llama-3.1-8b-instant',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.2,
                'max_tokens': 2000,
            },
            timeout=60
        )
        print("STATUS:", response.status_code)
        print("RESPONSE:", response.text)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content'].strip()

        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]

        return json.loads(content.strip())

    except Exception as e:
        print("FULL ERROR:", str(e))
        raise

# ── Views ─────────────────────────────────────────────────────────────────────

class ResumeListUploadView(APIView):
    """
    GET  → Recruitment dept only — list all resumes
    POST → Recruitment dept only — upload resume
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        if not is_recruitment(request.user):
            return Response(
                {'message': 'Only Recruitment department members can access resumes'},
                status=status.HTTP_403_FORBIDDEN
            )
        resumes = Resume.objects.all().order_by('-uploaded_at')
        serializer = ResumeSerializer(resumes, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not is_recruitment(request.user):
            return Response(
                {'message': 'Only Recruitment department members can upload resumes'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ResumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(uploaded_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ResumeDeleteView(APIView):
    """DELETE → Recruitment dept only"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not is_recruitment(request.user):
            return Response(
                {'message': 'Only Recruitment department members can delete resumes'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            resume = Resume.objects.get(pk=pk)
        except Resume.DoesNotExist:
            return Response({'message': 'Resume not found'}, status=status.HTTP_404_NOT_FOUND)

        if resume.file and os.path.exists(resume.file.path):
            os.remove(resume.file.path)

        resume.delete()
        return Response({'message': 'Resume deleted'})


class ScreenResumesView(APIView):
    """
    POST → Recruitment dept only — trigger LLM screening for a job.
    Body: { "resume_ids": [1, 2, 3] }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        if not is_recruitment(request.user):
            return Response(
                {'message': 'Only Recruitment department members can run screening'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            job = JobOpening.objects.get(pk=job_id, status='OPEN')
        except JobOpening.DoesNotExist:
            return Response(
                {'message': 'Job opening not found or not open'},
                status=status.HTTP_404_NOT_FOUND
            )

        resume_ids = request.data.get('resume_ids', [])
        if not resume_ids:
            return Response(
                {'message': 'Please provide at least one resume_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        resumes = Resume.objects.filter(id__in=resume_ids)
        if not resumes.exists():
            return Response({'message': 'No valid resumes found'}, status=status.HTTP_400_BAD_REQUEST)

        resumes_data = []
        for resume in resumes:
            text = extract_text_from_file(resume.file)
            resumes_data.append({
                'id': resume.id,
                'name': resume.candidate_name,
                'text': text or f'[Could not extract text from {resume.candidate_name} resume]'
            })

        try:
            llm_results = call_llm_for_screening(job, resumes_data)
        except Exception as e:
            return Response(
                {'message': f'LLM screening failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        resume_map = {r.id: r for r in resumes}
        saved = []

        for result in llm_results:
            resume_obj = resume_map.get(result.get('id'))
            if not resume_obj:
                continue
            screening, _ = ScreeningResult.objects.update_or_create(
                job_opening=job,
                resume=resume_obj,
                defaults={
                    'candidate_name': result.get('name', resume_obj.candidate_name),
                    'match_score': max(0, min(100, int(result.get('score', 0)))),
                    'reason': result.get('reason', ''),
                    'screened_by': request.user,
                }
            )
            saved.append(screening)

        serializer = ScreeningResultSerializer(saved, many=True)
        return Response({
            'message': f'Screening complete. {len(saved)} candidates evaluated.',
            'results': serializer.data
        })


class ScreeningResultsView(APIView):
    """
    GET → HR/Admin only — view screening results for a job opening.
    """
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def get(self, request, job_id):
        try:
            job = JobOpening.objects.get(pk=job_id)
        except JobOpening.DoesNotExist:
            return Response({'message': 'Job opening not found'}, status=status.HTTP_404_NOT_FOUND)

        results = ScreeningResult.objects.filter(job_opening=job).order_by('-match_score')
        serializer = ScreeningResultSerializer(results, many=True)
        return Response({
            'job_id': job.id,
            'job_title': job.title,
            'department': job.department.name,
            'results': serializer.data
        })


class AllScreeningJobsView(APIView):
    """
    GET → HR/Admin only — list all jobs that have screening results.
    """
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def get(self, request):
        from django.db.models import Count, Max, Avg
        jobs = JobOpening.objects.filter(
            screening_results__isnull=False
        ).annotate(
            candidate_count=Count('screening_results'),
            last_screened=Max('screening_results__screened_at'),
            avg_score=Avg('screening_results__match_score')
        ).distinct().order_by('-last_screened')

        data = [{
            'job_id': j.id,
            'job_title': j.title,
            'department': j.department.name,
            'status': j.status,
            'candidate_count': j.candidate_count,
            'avg_score': round(j.avg_score or 0, 1),
            'last_screened': j.last_screened,
        } for j in jobs]

        return Response(data)