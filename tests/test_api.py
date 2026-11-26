"""HTTP layer: status codes come from the service errors; shapes match the schemas."""
VOD = "https://www.twitch.tv/videos/2934513082"


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_job_lifecycle(client):
    r = client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "top": 5})
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["status"] == "queued" and len(job["steps"]) == 8
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["log"] == []
    assert client.post(f"/api/v1/jobs/{job['id']}/retry").status_code == 409
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/v1/jobs/{job['id']}/retry").json()["status"] == "queued"


def test_bad_inputs(client):
    assert client.post("/api/v1/jobs", json={"kind": "monitor", "url": "https://x.com"}).status_code == 400
    assert client.post("/api/v1/jobs", json={"kind": "monitor"}).status_code == 422
    assert client.post("/api/v1/jobs", json={"kind": "nope", "url": VOD}).status_code == 422
    assert client.get("/api/v1/jobs/999").status_code == 404
    assert client.get("/api/v1/clips/999").status_code == 404
    assert client.get("/api/v1/streams/none").status_code == 404


def test_campaign_crud(client):
    r = client.post("/api/v1/campaigns", json={"name": "Test", "payout_per_1k": 0.5,
                                               "ends_at": "2026-12-31T23:59:00"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    from datetime import datetime
    assert datetime.fromisoformat(r.json()["ends_at"]).tzinfo is not None     # naive input stored as local time
    assert client.put(f"/api/v1/campaigns/{cid}", json={"name": "Renamed"}).json()["name"] == "Renamed"
    assert client.delete(f"/api/v1/campaigns/{cid}").status_code == 204
    assert client.delete(f"/api/v1/campaigns/{cid}").status_code == 404


def test_compat_routes_still_work(client):
    r = client.post("/api/jobs", json={"url": VOD, "mode": "download"})
    assert r.status_code == 202 and r.json()["state"] == "running"
    assert client.get(f"/api/jobs/{r.json()['id']}").status_code == 200
    assert client.get("/api/sessions").status_code == 200
    assert client.get("/media/../x/clip.mp4").status_code in (400, 404)


def test_clip_details(client, session, vod_dir):
    import json
    from backend.models import Clip
    folder = vod_dir / "s2" / "clips" / "903"
    folder.mkdir(parents=True)
    (folder / "judge.json").write_text(json.dumps({"title": "T", "usage": {"in": 1}}))
    (folder / "transcript.json").write_text(json.dumps({"words": [{"w": "hi", "s": 0, "e": 0.5}]}))
    c = Clip(stream_id="s2", clip_no="903", status="ready")
    session.add(c); session.commit(); session.refresh(c)
    d = client.get(f"/api/v1/clips/{c.id}/details").json()
    assert d["judge"] == {"title": "T"} and d["words"][0]["w"] == "hi" and d["score"] is None
