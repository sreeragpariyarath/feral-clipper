"""Phase 5: campaigns reach the job, posts track views and payout, the posting kit is ready to paste."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.models import Clip
from backend.services import kit

VOD = "https://www.twitch.tv/videos/2934513082"


def _campaign(client, **over):
    body = {"name": "AsianJeff", "streamer": "asianjeff", "payout_per_1k": 0.5,
            "caption": "Clipped from @AsianJeff", "hashtags": "#asianjeff #clipping", "brief": "No spoilers."}
    body.update(over)
    r = client.post("/api/v1/campaigns", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_campaign_is_frozen_into_the_job(client, tmp_path):
    logo = tmp_path / "logo.png"
    from PIL import Image
    Image.new("RGBA", (40, 20), (255, 0, 0, 255)).save(logo)
    camp = _campaign(client, logo_path=str(logo), logo_width=300, logo_y=40)
    r = client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": camp["id"]})
    assert r.status_code == 202, r.text
    c = r.json()["params"]["campaign"]
    assert c["overlay"] == {"file": str(logo), "w": 300, "y": 40, "x": "center"}
    assert c["caption"] == "Clipped from @AsianJeff #asianjeff #clipping" and c["brief"] == "No spoilers."


def test_campaign_logo_off_and_bad_logo(client):
    off = _campaign(client, logo_path="missing.png", logo_on=False)
    r = client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": off["id"]})
    assert r.status_code == 202 and r.json()["params"]["campaign"]["overlay"] is None
    bad = _campaign(client, logo_path="missing.png")
    r = client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": bad["id"]})
    assert r.status_code == 400 and "logo not found" in r.json()["detail"]
    ended = _campaign(client, active=False)
    assert client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": ended["id"]}).status_code == 400
    assert client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": 999}).status_code == 404


def _clip(session, vod_dir, stream="twitchvod-v2934513082", no="901"):
    folder = vod_dir / stream / "clips" / no
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "judge.json").write_text(json.dumps({"title": "Boxed an alligator in GTA V", "hook_text": "WE JUST BOXED AN ALLIGATOR",
                                                   "category": "funny"}))
    c = Clip(stream_id=stream, clip_no=no, status="ready", title="Boxed an alligator in GTA V", has_video=True)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def test_posts_payout_follows_the_stream_campaign(client, session, vod_dir):
    camp = _campaign(client)
    client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": camp["id"]})
    clip = _clip(session, vod_dir)
    r = client.post("/api/v1/posts", json={"clip_id": clip.id, "platform": "youtube", "url": "https://youtu.be/x"})
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["campaign_name"] == "AsianJeff" and post["payout_usd"] == 0.0
    r = client.patch(f"/api/v1/posts/{post['id']}", json={"views": 7198})
    assert r.json()["payout_usd"] == 3.6 and r.json()["views_at"]
    assert len(client.get(f"/api/v1/posts?clip_id={clip.id}").json()) == 1
    assert client.delete(f"/api/v1/posts/{post['id']}").status_code == 204
    assert client.post("/api/v1/posts", json={"clip_id": 999, "platform": "youtube"}).status_code == 404
    assert client.post("/api/v1/posts", json={"clip_id": clip.id, "platform": "myspace"}).status_code == 422


def test_posting_kit(client, session, vod_dir):
    camp = _campaign(client)
    client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": camp["id"]})
    clip = _clip(session, vod_dir, no="902")
    k = client.get(f"/api/v1/clips/{clip.id}/kit").json()
    yt = next(p for p in k["platforms"] if p["platform"] == "youtube")
    assert yt["title"] == "Boxed an alligator in GTA 6"                       # never the wrong game
    assert "Clipped from @AsianJeff #asianjeff #clipping" in yt["caption"]     # required text word for word
    assert yt["hashtags"][:2] == ["asianjeff", "clipping"] and "Funny" in yt["hashtags"]
    assert k["campaign_name"] == "AsianJeff" and len(k["best_times_local"]) == 3


def test_best_times_skip_slots_that_are_too_close():
    et = ZoneInfo("America/New_York")
    times = kit.best_times(datetime(2026, 11, 26, 11, 50, tzinfo=et))
    assert [t.hour for t in times] == [16, 19, 12]      # 12:00 is 10 minutes away: skipped
    assert times[2].day == 27


def test_new_columns_are_added_to_an_old_database(session):
    from sqlalchemy import inspect
    from backend.db import engine
    cols = {c["name"] for c in inspect(engine).get_columns("campaign")}
    assert {"logo_on", "logo_width", "logo_y", "hashtags"} <= cols


def test_deleted_campaign_is_skipped(client, session, vod_dir):
    camp = _campaign(client)
    client.post("/api/v1/jobs", json={"kind": "monitor", "url": VOD, "campaign_id": camp["id"]})
    client.delete(f"/api/v1/campaigns/{camp['id']}")
    clip = _clip(session, vod_dir, no="903")
    r = client.post("/api/v1/posts", json={"clip_id": clip.id, "platform": "tiktok"})
    assert r.status_code == 201 and r.json()["campaign_id"] is None and r.json()["payout_usd"] is None
