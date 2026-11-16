from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import JobFilter, ProjectFilter
from .models import Job, Project
from .permissions import IsOwner
from .serializers import (
    JobSerializer,
    ProjectSerializer,
    ProjectUploadSerializer,
    QuotaSerializer,
    StemSerializer,
)
from .services import can_create, create_project_with_job, quota_for


class QuotaExceeded(APIException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Monthly free-tier limit reached. Upgrade to Pro."
    default_code = "quota_exceeded"


class JobNotCompleted(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "job_not_completed"


@extend_schema_view(
    list=extend_schema(summary="List your projects (paginated, filterable)"),
    retrieve=extend_schema(summary="Get one of your projects"),
    partial_update=extend_schema(summary="Rename a project"),
    destroy=extend_schema(summary="Delete a project and its jobs"),
)
@extend_schema(tags=["projects"])
class ProjectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_class = ProjectFilter
    search_fields = ["name", "original_filename"]
    ordering_fields = ["created_at", "name", "id"]
    ordering = ["-created_at", "-id"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return Project.objects.none()
        # Owner scoping happens here: other users' rows simply do not exist
        # for this request, so their ids return 404.
        return (
            Project.objects.filter(owner=self.request.user)
            .prefetch_related(Prefetch("jobs", queryset=Job.objects.order_by("-created_at", "-id")))
        )

    @extend_schema(
        summary="Upload a song (creates a project and a queued job)",
        request={"multipart/form-data": ProjectUploadSerializer},
        responses={
            201: ProjectSerializer,
            400: OpenApiResponse(description="Validation error (file type, size, name)"),
            402: OpenApiResponse(description="Free-tier monthly limit reached"),
        },
    )
    def create(self, request, *args, **kwargs):
        upload = ProjectUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        if not can_create(request.user):
            raise QuotaExceeded()
        project = create_project_with_job(
            request.user, upload.validated_data["file"], upload.validated_data.get("name")
        )
        project = self.get_queryset().get(pk=project.pk)
        return Response(self.get_serializer(project).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Your usage this month vs. your plan limit", responses=QuotaSerializer)
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def quota(self, request):
        return Response(QuotaSerializer(quota_for(request.user)).data)


@extend_schema_view(
    list=extend_schema(summary="List your jobs (filter by status / project)"),
    retrieve=extend_schema(summary="Job status + progress"),
)
@extend_schema(tags=["jobs"])
class JobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    filterset_class = JobFilter
    ordering_fields = ["created_at", "updated_at", "status", "id"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return Job.objects.none()
        return Job.objects.filter(owner=self.request.user)

    @extend_schema(
        summary="List produced stems (409 until the job is completed)",
        responses={200: StemSerializer(many=True), 409: OpenApiResponse(description="Job not completed")},
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def stems(self, request, pk=None):
        job = self.get_object()
        if job.status != Job.Status.COMPLETED:
            raise JobNotCompleted(f"Job not completed (status={job.status})")
        return Response(StemSerializer(job.stems, many=True).data)
