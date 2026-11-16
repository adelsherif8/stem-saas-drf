from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health(_request):
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
    except Exception:  # pragma: no cover - only hit when the DB is down
        db = "error"
    return JsonResponse({"status": "ok" if db == "ok" else "degraded", "db": db},
                        status=200 if db == "ok" else 503)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("accounts.urls")),
    path("", include("studio.urls")),
    path("health", health, name="health"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
