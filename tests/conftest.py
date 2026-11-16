"""Shared fixtures.

Database: whatever DATABASE_URL points at (Postgres in docker-compose / CI);
without it, settings fall back to SQLite. pytest-django creates and destroys
a separate test database either way.
"""
import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User

PASSWORD = "Str0ng-pass-phrase"


@pytest.fixture(autouse=True)
def _test_settings(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed
    settings.FREE_TIER_MONTHLY_LIMIT = 3
    cache.clear()  # reset auth throttle counters between tests


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(email=None, tier=User.Tier.FREE, password=PASSWORD):
        counter["n"] += 1
        return User.objects.create_user(
            email=email or f"user{counter['n']}@example.com", password=password, tier=tier
        )

    return _make


def client_for(user) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


@pytest.fixture
def alice(make_user):
    return make_user("alice@example.com")


@pytest.fixture
def bob(make_user):
    return make_user("bob@example.com")


@pytest.fixture
def alice_api(alice):
    return client_for(alice)


@pytest.fixture
def bob_api(bob):
    return client_for(bob)


def audio(name="song.mp3", content=b"ID3fake-audio-bytes"):
    return SimpleUploadedFile(name, content, content_type="audio/mpeg")


@pytest.fixture
def upload(alice_api):
    """Upload a song as alice and return the response JSON."""

    def _upload(filename="song.mp3", client=None, **extra):
        resp = (client or alice_api).post(
            "/projects", {"file": audio(filename), **extra}, format="multipart"
        )
        assert resp.status_code == 201, resp.content
        return resp.json()

    return _upload
