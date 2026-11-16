import pytest

from studio.models import Job

pytestmark = pytest.mark.django_db

STEMS = [{"name": n, "path": f"/stems/{n}.wav"} for n in ["vocals", "drums", "bass", "other"]]


def test_get_job(alice_api, upload):
    job = upload()["latest_job"]
    resp = alice_api.get(f"/jobs/{job['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert set(resp.json()) == {"id", "project_id", "status", "progress", "error",
                                "created_at", "updated_at"}


def test_stems_409_until_completed(alice_api, upload):
    job_id = upload()["latest_job"]["id"]
    resp = alice_api.get(f"/jobs/{job_id}/stems")
    assert resp.status_code == 409
    assert "status=queued" in resp.json()["detail"]


def test_stems_after_completion(alice_api, upload):
    job_id = upload()["latest_job"]["id"]
    Job.objects.filter(pk=job_id).update(status=Job.Status.COMPLETED, progress=100, stems=STEMS)
    resp = alice_api.get(f"/jobs/{job_id}/stems")
    assert resp.status_code == 200
    assert [s["name"] for s in resp.json()] == ["vocals", "drums", "bass", "other"]


def test_jobs_are_read_only(alice_api, upload):
    job_id = upload()["latest_job"]["id"]
    assert alice_api.patch(f"/jobs/{job_id}", {"status": "completed"}, format="json").status_code == 405
    assert alice_api.delete(f"/jobs/{job_id}").status_code == 405
    assert alice_api.post("/jobs", {}, format="json").status_code == 405


def test_filter_jobs_by_status_and_project(alice_api, upload):
    a = upload("a.mp3")
    b = upload("b.mp3")
    Job.objects.filter(pk=a["latest_job"]["id"]).update(status=Job.Status.FAILED, error="boom")
    failed = alice_api.get("/jobs", {"status": "failed"}).json()
    assert [j["id"] for j in failed["results"]] == [a["latest_job"]["id"]]
    assert failed["results"][0]["error"] == "boom"
    by_project = alice_api.get("/jobs", {"project": b["id"]}).json()
    assert [j["project_id"] for j in by_project["results"]] == [b["id"]]
