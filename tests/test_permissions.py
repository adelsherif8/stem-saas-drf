"""Owner-only access: the DRF version of the FastAPI isolation tests."""
import pytest
from rest_framework.test import APIRequestFactory

from studio.models import Job, Project
from studio.permissions import IsOwner

from .conftest import audio

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/projects"),
        ("post", "/projects"),
        ("get", "/projects/1"),
        ("patch", "/projects/1"),
        ("delete", "/projects/1"),
        ("get", "/projects/quota"),
        ("get", "/jobs"),
        ("get", "/jobs/1"),
        ("get", "/jobs/1/stems"),
    ],
)
def test_anonymous_requests_are_401(api, method, url):
    assert getattr(api, method)(url).status_code == 401


def test_list_only_shows_own_projects(alice_api, bob_api, upload):
    upload("alice.mp3")
    upload("bob.mp3", client=bob_api)
    names = [p["name"] for p in alice_api.get("/projects").json()["results"]]
    assert names == ["alice.mp3"]


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_users_project_is_404(bob_api, upload, method):
    pid = upload()["id"]  # alice's
    resp = getattr(bob_api, method)(f"/projects/{pid}", {"name": "mine now"}, format="json")
    assert resp.status_code == 404
    project = Project.objects.get(pk=pid)
    assert project.name == "song.mp3"  # untouched


def test_other_users_project_looks_like_missing(bob_api, upload):
    pid = upload()["id"]
    assert bob_api.get(f"/projects/{pid}").json() == bob_api.get("/projects/999999").json()


def test_other_users_jobs_are_invisible(alice_api, bob_api, upload):
    job_id = upload()["latest_job"]["id"]
    assert bob_api.get(f"/jobs/{job_id}").status_code == 404
    assert bob_api.get(f"/jobs/{job_id}/stems").status_code == 404
    assert bob_api.get("/jobs").json()["count"] == 0
    assert alice_api.get("/jobs").json()["count"] == 1


def test_quota_is_per_user(alice_api, bob_api, upload):
    for i in range(3):
        upload(f"s{i}.mp3")
    # alice is at her limit; bob is not affected
    assert alice_api.post("/projects", {"file": audio()}, format="multipart").status_code == 402
    assert bob_api.post("/projects", {"file": audio()}, format="multipart").status_code == 201


def test_is_owner_object_permission(alice, bob):
    project = Project.objects.create(owner=alice, name="x", original_filename="x.mp3")
    request = APIRequestFactory().get("/")
    perm = IsOwner()
    request.user = alice
    assert perm.has_object_permission(request, None, project)
    request.user = bob
    assert not perm.has_object_permission(request, None, project)


def test_upload_ignores_owner_in_payload(alice, bob, bob_api):
    resp = bob_api.post("/projects", {"file": audio(), "owner": alice.id}, format="multipart")
    assert resp.status_code == 201
    assert Project.objects.get(pk=resp.json()["id"]).owner == bob
    assert Job.objects.get(project_id=resp.json()["id"]).owner == bob
