import pytest

pytestmark = pytest.mark.django_db


def test_openapi_schema_lists_ported_endpoints(api):
    resp = api.get("/schema", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for p in ["/auth/register", "/auth/login", "/auth/refresh", "/auth/me",
              "/projects", "/projects/{id}", "/projects/quota",
              "/jobs", "/jobs/{id}", "/jobs/{id}/stems"]:
        assert p in paths, p
    assert "bearer" in str(resp.json()["components"]["securitySchemes"]).lower()


def test_swagger_ui_served(api):
    assert api.get("/docs").status_code == 200


def test_health(api):
    assert api.get("/health").json() == {"status": "ok", "db": "ok"}


def test_auth_endpoints_are_throttled(api, settings):
    from rest_framework.settings import api_settings
    from rest_framework.throttling import ScopedRateThrottle

    old = ScopedRateThrottle.THROTTLE_RATES
    ScopedRateThrottle.THROTTLE_RATES = {**api_settings.DEFAULT_THROTTLE_RATES, "auth": "3/min"}
    try:
        codes = [api.post("/auth/login", {"email": "x@example.com", "password": "nope-nope-1"},
                          format="json").status_code for _ in range(4)]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = old
    assert codes == [401, 401, 401, 429]
