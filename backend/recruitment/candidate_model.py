from django.db import models


class Candidate(models.Model):

    # ── Personal Information ──────────────────────────────────────────────────
    full_name = models.CharField(
        max_length=150,
        help_text="Extracted via spaCy NER or filename fallback"
    )
    email = models.EmailField(
        blank=True, null=True,
        help_text="Extracted via Regex"
    )
    phone = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="Extracted via Regex"
    )

    # ── Resume File Reference ─────────────────────────────────────────────────
    source_filename = models.CharField(
        max_length=255,
        help_text="Original uploaded filename"
    )

    # ── Resume file on disk ───────────────────────────────────────────────────
    resume_file = models.FileField(
        upload_to='resumes/',
        blank=True, null=True,
        help_text="Resume file saved on disk"
    )

    # ── Duplicate Detection ───────────────────────────────────────────────────
    content_hash = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text="SHA-256 of file bytes — prevents duplicate uploads"
    )

    # ── Embedding Status ──────────────────────────────────────────────────────
    is_embedded = models.BooleanField(
        default=False,
        help_text="True once resume chunks are stored in ChromaDB"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email or 'no email'})"