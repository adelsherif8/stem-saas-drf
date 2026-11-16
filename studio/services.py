"""Business rules ported from the FastAPI app's `billing.py` and upload route."""
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Job, Project


@dataclass
class Quota:
    tier: str
    used_this_month: int
    limit: int | None  # None == unlimited (pro)
    remaining: int | None


def month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def quota_for(user) -> Quota:
    used = Project.objects.filter(owner=user, created_at__gte=month_start()).count()
    if user.tier == user.Tier.PRO:
        return Quota(tier=user.tier, used_this_month=used, limit=None, remaining=None)
    limit = settings.FREE_TIER_MONTHLY_LIMIT
    return Quota(tier=user.tier, used_this_month=used, limit=limit, remaining=max(limit - used, 0))


def can_create(user) -> bool:
    q = quota_for(user)
    return q.limit is None or q.used_this_month < q.limit


def enqueue_separation(job: Job) -> None:
    """Hook where the FastAPI app calls `separate_stems.delay(job.id)`.

    The Celery worker is not part of this port, so jobs stay `queued`.
    Kept as a single function so wiring a task queue later is a one-line change.
    """


@transaction.atomic
def create_project_with_job(user, uploaded_file, name: str | None = None) -> Project:
    project = Project.objects.create(
        owner=user,
        name=name or uploaded_file.name,
        original_filename=uploaded_file.name,
    )
    project.original_file.save(uploaded_file.name, uploaded_file, save=True)
    job = Job.objects.create(project=project, owner=user, status=Job.Status.QUEUED)
    transaction.on_commit(lambda: enqueue_separation(job))
    return project
