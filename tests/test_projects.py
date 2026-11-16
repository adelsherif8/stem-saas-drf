import datetime as dt

import pytest
from django.utils import timezone

from accounts.models import User
from studio.models import Job, Project

from .conftest import audio, client_for

pytestmark = pytest.mark.django_db


def test_upload_creates_project_and_queued_job(alice, upload):
    body = upload("track.wav")
    assert body["name"] == "track.wav"
    assert body["original_filename"] == "track.wav"
    assert body["latest_job"]["status"] == "queued"
    assert body["latest_job"]["progress"] == 0
    project = Project.objects.get(pk=body["id"])
    assert project.owner == alice
    assert project.original_file.name.endswith("track.wav")
    assert Job.objects.filter(project=project, owner=alice).count() == 1


def test_upload_with_custom_name(upload):
    assert upload("a.mp3", name="My demo")["name"] == "My demo"


@pytest.mark.parametrize("filename", ["notes.txt", "song", "evil.mp3.exe"])
def test_upload_rejects_unsupported_extension(alice_api, filename):
    resp = alice_api.post("/projects", {"file": audio(filename)}, format="multipart")
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["file"][0]
    assert Project.objects.count() == 0


def test_upload_rejects_empty_file(alice_api):
    resp = alice_api.post("/projects", {"file": audio("a.mp3", b"")}, format="multipart")
    assert resp.status_code == 400
    assert "file" in resp.json()


def test_upload_rejects_oversized_file(alice_api, settings):
    settings.MAX_UPLOAD_MB = 0
    resp = alice_api.post("/projects", {"file": audio("a.mp3")}, format="multipart")
    assert resp.status_code == 400
    assert "too large" in resp.json()["file"][0]


def test_upload_requires_file(alice_api):
    resp = alice_api.post("/projects", {}, format="multipart")
    assert resp.status_code == 400
    assert "file" in resp.json()


def test_retrieve_project(alice_api, upload):
    pid = upload()["id"]
    resp = alice_api.get(f"/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


def test_rename_project(alice_api, upload):
    pid = upload()["id"]
    resp = alice_api.patch(f"/projects/{pid}", {"name": "  Renamed  "}, format="json")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert Project.objects.get(pk=pid).name == "Renamed"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 256])
def test_rename_validation(alice_api, upload, bad):
    pid = upload()["id"]
    resp = alice_api.patch(f"/projects/{pid}", {"name": bad}, format="json")
    assert resp.status_code == 400
    assert "name" in resp.json()


def test_read_only_fields_are_ignored_on_patch(alice_api, upload):
    body = upload("orig.mp3")
    resp = alice_api.patch(
        f"/projects/{body['id']}", {"original_filename": "hacked.mp3"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["original_filename"] == "orig.mp3"


def test_put_is_not_allowed(alice_api, upload):
    pid = upload()["id"]
    assert alice_api.put(f"/projects/{pid}", {"name": "x"}, format="json").status_code == 405


def test_delete_project_cascades_jobs(alice_api, upload):
    pid = upload()["id"]
    assert alice_api.delete(f"/projects/{pid}").status_code == 204
    assert not Project.objects.filter(pk=pid).exists()
    assert not Job.objects.filter(project_id=pid).exists()
    assert alice_api.get(f"/projects/{pid}").status_code == 404


# --- quota (ported from billing.py) -----------------------------------------

def test_quota_endpoint(alice_api, upload):
    upload()
    resp = alice_api.get("/projects/quota")
    assert resp.status_code == 200
    assert resp.json() == {"tier": "free", "used_this_month": 1, "limit": 3, "remaining": 2}


def test_free_tier_limit_returns_402(alice_api, upload):
    for i in range(3):
        upload(f"s{i}.mp3")
    resp = alice_api.post("/projects", {"file": audio("s4.mp3")}, format="multipart")
    assert resp.status_code == 402
    assert Project.objects.count() == 3


def test_last_months_projects_do_not_count(alice, alice_api, upload):
    for i in range(3):
        upload(f"s{i}.mp3")
    last_month = timezone.now().replace(day=1) - dt.timedelta(days=1)
    Project.objects.update(created_at=last_month)
    upload("fresh.mp3")  # would be 402 if old rows counted


def test_pro_tier_is_unlimited(make_user, upload):
    pro = make_user("pro@example.com", tier=User.Tier.PRO)
    client = client_for(pro)
    for i in range(5):
        upload(f"s{i}.mp3", client=client)
    assert client.get("/projects/quota").json() == {
        "tier": "pro", "used_this_month": 5, "limit": None, "remaining": None
    }


# --- pagination, filtering, search, ordering --------------------------------

@pytest.fixture
def many_projects(alice):
    projects = [Project(owner=alice, name=f"Song {i:02d}", original_filename=f"s{i}.mp3")
                for i in range(25)]
    Project.objects.bulk_create(projects)
    return Project.objects.filter(owner=alice)


def test_list_is_paginated(alice_api, many_projects):
    resp = alice_api.get("/projects")
    body = resp.json()
    assert resp.status_code == 200
    assert body["count"] == 25
    assert len(body["results"]) == 20
    assert body["next"] is not None and body["previous"] is None
    page2 = alice_api.get("/projects", {"page": 2}).json()
    assert len(page2["results"]) == 5 and page2["next"] is None


def test_page_size_param_is_capped(alice_api, many_projects):
    assert len(alice_api.get("/projects", {"page_size": 7}).json()["results"]) == 7
    assert len(alice_api.get("/projects", {"page_size": 1000}).json()["results"]) == 25


def test_out_of_range_page_is_404(alice_api, many_projects):
    assert alice_api.get("/projects", {"page": 99}).status_code == 404


def test_filter_by_name(alice_api, many_projects):
    body = alice_api.get("/projects", {"name": "song 1"}).json()
    assert body["count"] == 10  # Song 10..19
    assert all("Song 1" in p["name"] for p in body["results"])


def test_search(alice_api, many_projects):
    body = alice_api.get("/projects", {"search": "s7.mp3"}).json()
    assert [p["original_filename"] for p in body["results"]] == ["s7.mp3"]


def test_ordering(alice_api, many_projects):
    names = [p["name"] for p in alice_api.get("/projects", {"ordering": "name"}).json()["results"]]
    assert names == sorted(names)
    names_desc = [p["name"] for p in alice_api.get("/projects", {"ordering": "-name"}).json()["results"]]
    assert names_desc[0] == "Song 24"


def test_filter_by_created_range(alice_api, many_projects):
    old = many_projects.order_by("id")[:5]
    Project.objects.filter(pk__in=[p.pk for p in old]).update(
        created_at=timezone.now() - dt.timedelta(days=10)
    )
    cutoff = (timezone.now() - dt.timedelta(days=1)).isoformat()
    assert alice_api.get("/projects", {"created_after": cutoff}).json()["count"] == 20
    assert alice_api.get("/projects", {"created_before": cutoff}).json()["count"] == 5


def test_filter_by_job_status(alice_api, upload):
    a = upload("a.mp3")["id"]
    upload("b.mp3")
    Job.objects.filter(project_id=a).update(status=Job.Status.COMPLETED)
    body = alice_api.get("/projects", {"job_status": "completed"}).json()
    assert [p["id"] for p in body["results"]] == [a]


def test_invalid_filter_value_is_400(alice_api):
    resp = alice_api.get("/projects", {"job_status": "exploded"})
    assert resp.status_code == 400
    assert "job_status" in resp.json()
