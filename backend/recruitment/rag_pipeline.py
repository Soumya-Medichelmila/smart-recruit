import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from typing import List, Dict, Any

import requests
from django.conf import settings

from .candidate_model import Candidate
from .chunker import chunk_resume
from .embedder import store_chunks, search_similar_chunks, delete_candidate_chunks
from .pii_extractor import extract_pii, strip_pii

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# UPLOAD FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def process_resume_upload(
    text: str,
    source_filename: str,
    file_bytes: bytes = b"",
) -> Candidate:

    logger.info("[RAG] Processing upload: %s", source_filename)

    # ── Duplicate detection via content hash ──────────────────────────────────
    content_hash = hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""
    if content_hash:
        existing = Candidate.objects.filter(content_hash=content_hash).first()
        if existing:
            logger.info("[RAG] Duplicate detected — returning candidate_id=%d", existing.id)
            return existing

    # ── Step 1: Extract PII ───────────────────────────────────────────────────
    pii = extract_pii(text, filename_hint=source_filename)
    logger.info("[RAG] PII — name:%s email:%s phone:%s", pii["name"], pii["email"], pii["phone"])

    # ── Step 2: Save Candidate ────────────────────────────────────────────────
    candidate = Candidate.objects.create(
        full_name           = pii["name"],
        email               = pii["email"],
        phone               = pii["phone"],
        source_filename     = source_filename,
        content_hash        = content_hash,
        is_embedded         = False,
    )
    logger.info("[RAG] Candidate saved — id=%d", candidate.id)

    # ── Step 3: Save file to disk ─────────────────────────────────────────────
    if file_bytes:
        try:
            resumes_dir = os.path.join(settings.MEDIA_ROOT, "resumes")
            os.makedirs(resumes_dir, exist_ok=True)
            disk_path = os.path.join(resumes_dir, source_filename)
            with open(disk_path, "wb") as f:
                f.write(file_bytes)
            candidate.resume_file = f"resumes/{source_filename}"
            candidate.save(update_fields=["resume_file"])
        except Exception as e:
            logger.error("[RAG] File save failed: %s", e)

    # ── Step 4: Chunk ─────────────────────────────────────────────────────────
    chunks = chunk_resume(text=text, candidate_id=candidate.id, source_filename=source_filename)
    logger.info("[RAG] %d chunks created", len(chunks))

    # ── Step 5: Embed + store in ChromaDB ────────────────────────────────────
    if chunks:
        store_chunks(chunks)

    # ── Step 6: Mark embedded ─────────────────────────────────────────────────
    candidate.is_embedded = True
    candidate.save(update_fields=["is_embedded"])
    logger.info("[RAG] Upload done — candidate_id=%d", candidate.id)
    return candidate


# ═══════════════════════════════════════════════════════════════════════════════
# SCREENING FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def _build_jd_text(job) -> str:
    parts = [
        f"Job Title: {job.title}",
        f"Description: {job.description or ''}",
        f"Required Skills: {getattr(job, 'required_skills_desc', '') or ''}",
        f"Technologies: {getattr(job, 'technologies', '') or ''}",
        f"Experience Required: {getattr(job, 'experience', '') or ''}",
    ]
    try:
        skill_names = ", ".join(s.name for s in job.skills.all())
        if skill_names:
            parts.append(f"Skills: {skill_names}")
    except Exception:
        pass
    return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())


def _group_chunks_by_candidate(chunks: List[Dict]) -> Dict[str, List[Dict]]:
    grouped = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.get("candidate_id", "unknown")].append(chunk)
    return dict(grouped)


def _score_candidate_with_llm(job, candidate: Candidate, chunks: List[Dict]) -> Dict[str, Any]:
    sorted_chunks = sorted(chunks, key=lambda c: c.get("distance", 1.0))

    # Build resume context WITHOUT PII
    resume_context = ""
    for chunk in sorted_chunks[:5]:
        section = chunk.get("section", "").upper()
        text    = strip_pii(chunk.get("text", ""))   # ← strip PII before LLM
        resume_context += f"\n[{section}]\n{text}\n"

    prompt = f"""You are an expert HR recruiter. Score how well this candidate matches the job.

JOB TITLE: {job.title}
JOB DESCRIPTION: {job.description or ''}
REQUIRED SKILLS: {getattr(job, 'required_skills_desc', '') or ''}
TECHNOLOGIES: {getattr(job, 'technologies', '') or ''}
EXPERIENCE REQUIRED: {getattr(job, 'experience', '') or ''}

CANDIDATE RESUME (PII removed, most relevant sections):
{resume_context[:2500]}

Respond in JSON only — no markdown:
{{
  "score": <0-100>,
  "reason": "<2-3 sentence explanation>",
  "skills": "<comma-separated skills found in resume>"
}}"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type" : "application/json",
            },
            json={
                "model"      : "llama-3.3-70b-versatile",
                "max_tokens" : 400,
                "messages"   : [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw  = resp.json()["choices"][0]["message"]["content"].strip()
        raw  = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        skills = re.sub(r'[\[\]"\']', "", (data.get("skills") or "")).strip()
        return {
            "score" : int(data.get("score", 0)),
            "reason": data.get("reason", ""),
            "skills": skills,
        }
    except Exception as exc:
        logger.error("[RAG] LLM error for candidate_id=%d: %s", candidate.id, exc)
        return {"score": 0, "reason": f"Scoring error: {exc}", "skills": ""}


def run_rag_screening(
    job,
    request_user,
    top_k: int = 20,
    score_threshold: int = 80,
) -> Dict[str, Any]:

    logger.info("[RAG] Screening job_id=%d threshold=%d%%", job.id, score_threshold)

    jd_text        = _build_jd_text(job)
    similar_chunks = search_similar_chunks(jd_text, top_k=top_k)
    logger.info("[RAG] ChromaDB returned %d chunks", len(similar_chunks))

    if not similar_chunks:
        return {
            "job_id": job.id, "job_title": job.title,
            "total_candidates_found": 0, "total_above_threshold": 0,
            "score_threshold": score_threshold, "results": [],
            "message": "No resumes in database. Upload resumes first.",
        }

    grouped = _group_chunks_by_candidate(similar_chunks)
    logger.info("[RAG] %d unique candidates found", len(grouped))

    results = []
    for candidate_id_str, chunks in grouped.items():
        try:
            candidate = Candidate.objects.get(id=int(candidate_id_str))
        except (Candidate.DoesNotExist, ValueError):
            continue

        llm_result = _score_candidate_with_llm(job, candidate, chunks)
        best_chunk = min(chunks, key=lambda c: c.get("distance", 1.0))

        results.append({
            "candidate_id"   : candidate.id,
            "candidate_name" : " ".join(candidate.full_name.split()),
            "candidate_email": candidate.email,
            "candidate_phone": candidate.phone,
            "source_filename": candidate.source_filename,
            "match_score"    : llm_result["score"],
            "reason"         : llm_result["reason"],
            "skills"         : llm_result["skills"],
            "best_section"   : best_chunk.get("section", ""),
            "chunks_matched" : len(chunks),
            "above_threshold": llm_result["score"] >= score_threshold,
        })

    results.sort(key=lambda r: r["match_score"], reverse=True)
    logger.info("[RAG] Scoring done — total=%d", len(results))

    return {
        "job_id"                : job.id,
        "job_title"             : job.title,
        "total_candidates_found": len(results),
        "total_above_threshold" : len([r for r in results if r["above_threshold"]]),
        "score_threshold"       : score_threshold,
        "results"               : results,
    }