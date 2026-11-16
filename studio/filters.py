import django_filters

from .models import Job, Project


class ProjectFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lt")
    job_status = django_filters.ChoiceFilter(
        field_name="jobs__status", choices=Job.Status.choices, distinct=True,
        label="Has at least one job with this status",
    )

    class Meta:
        model = Project
        fields = ["name", "created_after", "created_before", "job_status"]


class JobFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Job.Status.choices)
    project = django_filters.NumberFilter(field_name="project_id")

    class Meta:
        model = Job
        fields = ["status", "project"]
