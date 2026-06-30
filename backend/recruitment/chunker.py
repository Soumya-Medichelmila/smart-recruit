import re
from typing import List, Dict


SECTION_HEADINGS: Dict[str, str] = {
    "summary": "summary", "professional summary": "summary",
    "career summary": "summary", "objective": "summary",
    "career objective": "summary", "profile": "summary", "about me": "summary",

    "skills": "skills", "technical skills": "skills",
    "core competencies": "skills", "competencies": "skills",
    "key skills": "skills", "technologies": "skills",
    "tech stack": "skills", "tools": "skills",
    "tools & technologies": "skills", "skills & technologies": "skills",
    "technical expertise": "skills",

    "experience": "experience", "work experience": "experience",
    "professional experience": "experience", "employment history": "experience",
    "work history": "experience", "career history": "experience",
    "internship": "experience", "internships": "experience",

    "education": "education", "educational background": "education",
    "academic background": "education", "qualifications": "education",
    "academic qualifications": "education",

    "projects": "projects", "personal projects": "projects",
    "academic projects": "projects", "project experience": "projects",
    "key projects": "projects", "notable projects": "projects",

    "certifications": "certifications", "certification": "certifications",
    "licenses": "certifications", "licenses & certifications": "certifications",
    "achievements": "certifications", "awards": "certifications",
    "awards & achievements": "certifications",
}


def _detect_section(line: str) -> str | None:
    cleaned = line.strip().rstrip(":").strip()
    if not cleaned or len(cleaned) > 60:
        return None
    lower = cleaned.lower()
    if lower in SECTION_HEADINGS:
        return SECTION_HEADINGS[lower]
    if cleaned.isupper() and 2 <= len(cleaned.split()) <= 6:
        return "other"
    return None


def chunk_resume(text: str, candidate_id: int, source_filename: str) -> List[Dict]:
    lines = text.splitlines()
    sections = []
    for i, line in enumerate(lines):
        section = _detect_section(line)
        if section:
            sections.append((i, section))

    if not sections:
        clean = text.strip()
        if clean:
            return [{
                "text": clean, "section": "full_resume",
                "candidate_id": candidate_id,
                "source_filename": source_filename, "chunk_index": 0,
            }]
        return []

    chunks = []
    chunk_index = 0

    pre_text = "\n".join(lines[:sections[0][0]]).strip()
    if pre_text and len(pre_text) > 30:
        chunks.append({
            "text": pre_text, "section": "summary",
            "candidate_id": candidate_id,
            "source_filename": source_filename, "chunk_index": chunk_index,
        })
        chunk_index += 1

    for idx, (line_i, section_name) in enumerate(sections):
        end_line = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines)
        section_text = "\n".join(lines[line_i + 1: end_line]).strip()
        if not section_text or len(section_text) < 10:
            continue
        chunks.append({
            "text": section_text, "section": section_name,
            "candidate_id": candidate_id,
            "source_filename": source_filename, "chunk_index": chunk_index,
        })
        chunk_index += 1

    return chunks