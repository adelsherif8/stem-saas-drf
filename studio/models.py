"""Projects (uploaded songs) and Jobs (stem-separation runs).

Mirrors the FastAPI `projects` and `jobs` tables, minus `workspace_id`
(workspaces are not ported; ownership is per user, see README).
"""
from django.conf import settings
from django.db import models


def upload_path(instance: "Project", filename: str) -> str:
    return f"uploads/{instance.owner_id}/{filename}"


class Project(models.Model):
    """One uploaded song."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    original_file = models.FileField(upload_to=upload_path, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    """One stem-separation run for a project."""

    class Status(models.TextChoices):
        QUEUED = "queued"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="jobs")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    progress = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True, null=True)
    # The FastAPI model stored this as a JSON string in a Text column; Django
    # has a native JSONField (jsonb on Postgres).
    stems = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progress__lte=100), name="job_progress_lte_100"
            )
        ]

    def __str__(self) -> str:
        return f"Job {self.pk} ({self.status})"
