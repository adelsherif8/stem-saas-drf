from rest_framework.routers import DefaultRouter

from .views import JobViewSet, ProjectViewSet

router = DefaultRouter(trailing_slash=False)
router.register("projects", ProjectViewSet, basename="project")
router.register("jobs", JobViewSet, basename="job")

urlpatterns = router.urls
