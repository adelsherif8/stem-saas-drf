import pytest

from accounts.models import User

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def register(api, email="new@example.com", password=PASSWORD):
    return api.post("/auth/register", {"email": email, "password": password}, format="json")


def login(api, email="new@example.com", password=PASSWORD):
    return api.post("/auth/login", {"email": email, "password": password}, format="json")


def test_register_returns_user_without_password(api):
    resp = register(api)
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"id", "email", "tier", "created_at"}
    assert body["email"] == "new@example.com"
    assert body["tier"] == "free"
    user = User.objects.get(email="new@example.com")
    assert user.check_password(PASSWORD)
    assert user.password != PASSWORD  # stored hashed


def test_register_normalises_email_case(api):
    assert register(api, email="Mixed.Case@Example.COM").status_code == 201
    assert User.objects.filter(email="mixed.case@example.com").exists()


def test_register_duplicate_email_is_case_insensitive(api):
    assert register(api, email="dup@example.com").status_code == 201
    resp = register(api, email="DUP@example.com")
    assert resp.status_code == 400
    assert resp.json()["email"] == ["Email already registered"]


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"email": "not-an-email", "password": PASSWORD}, "email"),
        ({"password": PASSWORD}, "email"),
        ({"email": "x@example.com"}, "password"),
    ],
)
def test_register_field_validation(api, payload, field):
    resp = api.post("/auth/register", payload, format="json")
    assert resp.status_code == 400
    assert field in resp.json()


@pytest.mark.parametrize("weak", ["short1", "12345678901", "password123"])
def test_register_rejects_weak_passwords(api, weak):
    resp = register(api, password=weak)
    assert resp.status_code == 400
    assert "non_field_errors" in resp.json() or "password" in resp.json()
    assert not User.objects.filter(email="new@example.com").exists()


def test_login_returns_access_and_refresh(api):
    register(api)
    resp = login(api)
    assert resp.status_code == 200
    assert {"access", "refresh"} <= set(resp.json())


def test_login_wrong_password_is_401(api):
    register(api)
    assert login(api, password="wrong-password-123").status_code == 401


def test_login_unknown_user_is_401(api):
    assert login(api, email="ghost@example.com").status_code == 401


def test_me_with_token(api):
    register(api)
    access = login(api).json()["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp = api.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"


def test_me_requires_auth(api):
    assert api.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(api):
    api.credentials(HTTP_AUTHORIZATION="Bearer not.a.jwt")
    assert api.get("/auth/me").status_code == 401


def test_refresh_issues_new_access_token(api):
    register(api)
    tokens = login(api).json()
    resp = api.post("/auth/refresh", {"refresh": tokens["refresh"]}, format="json")
    assert resp.status_code == 200
    new_access = resp.json()["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
    assert api.get("/auth/me").status_code == 200


def test_access_token_cannot_be_used_as_refresh(api):
    register(api)
    tokens = login(api).json()
    resp = api.post("/auth/refresh", {"refresh": tokens["access"]}, format="json")
    assert resp.status_code == 401


def test_inactive_user_cannot_log_in(api):
    register(api)
    User.objects.filter(email="new@example.com").update(is_active=False)
    assert login(api).status_code == 401
