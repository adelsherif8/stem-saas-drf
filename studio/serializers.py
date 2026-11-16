import os

from django.conf import settings
from rest_framework import serializers

from .models import Job, Project


class JobSerializer(serializers.ModelSerializer):
    """Same fields as the FastAPI `JobOut` schema."""

    class Meta:
        model = Job
        fields = ["id", "project_id", "status", "progress", "error", "created_at", "updated_at"]
        read_only_fields = fields


class StemSerializer(serializers.Serializer):
    name = serializers.CharField()
    path = serializers.CharField()


class ProjectSerializer(serializers.ModelSerializer):
    """Read shape + rename (PATCH). `name` is the only writable field."""

    latest_job = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "name", "original_filename", "created_at", "updated_at", "latest_job"]
        read_only_fields = ["id", "original_filename", "created_at", "updated_at", "latest_job"]
        extra_kwargs = {"name": {"allow_blank": False, "max_length": 255}}

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be blank.")
        return value

    def get_latest_job(self, obj) -> dict | None:
        # Uses the prefetched `jobs` (ordered newest first) to avoid N+1 queries.
        jobs = list(obj.jobs.all())
        return JobSerializer(jobs[0]).data if jobs else None


class ProjectUploadSerializer(serializers.Serializer):
    """Multipart upload: `file` (required) and an optional display `name`."""

    file = serializers.FileField()
    name = serializers.CharField(required=False, max_length=255, allow_blank=False)

    def validate_file(self, f):
        ext = os.path.splitext(f.name or "")[1].lower()
        if ext not in settings.ALLOWED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_AUDIO_EXTENSIONS))
            raise serializers.ValidationError(
                f"Unsupported file type: '{ext or 'none'}'. Allowed: {allowed}"
            )
        if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise serializers.ValidationError(f"File too large (max {settings.MAX_UPLOAD_MB} MB).")
        if f.size == 0:
            raise serializers.ValidationError("File is empty.")
        return f


class QuotaSerializer(serializers.Serializer):
    tier = serializers.CharField()
    used_this_month = serializers.IntegerField()
    limit = serializers.IntegerField(allow_null=True)
    remaining = serializers.IntegerField(allow_null=True)
