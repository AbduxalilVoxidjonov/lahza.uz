"""Shared platform contract, policy boundaries and actual rendered overlay placement."""
import json

import pytest
from _api_helpers import make_client
from pydantic import ValidationError

from lahza_engine.config import Settings, SubtitleSafeZone
from lahza_engine.montage.model import Captions, Format, MontageTimeline, StickerItem, TextItem
from lahza_engine.render.limits import check_limits
from lahza_engine.render.montage_render import _ass_doc, _overlay_chain, render_montage
from lahza_engine.render.profiles import (
    evaluate_profile,
    evaluate_timeline,
    export_profiles,
    profile_settings,
)
from lahza_engine.types import Word


def timeline(platform="custom", duration=180_000, **kwargs):
    return MontageTimeline(target_platform=platform,
                           text=[TextItem(id="card", start_ms=0, end_ms=duration, text="Test", kind="card")],
                           **kwargs)


def test_legacy_json_and_defaults():
    old = {"schema": "lahza.timeline/1", "format": {"aspect": "1:1", "w": 720, "h": 720, "fps": 25}}
    tl = MontageTimeline.model_validate(old)
    assert tl.target_platform == "custom"
    assert tl.format == Format(aspect="1:1", w=720, h=720, fps=25)
    assert MontageTimeline.model_validate(tl.to_json()) == tl
    assert MontageTimeline(target_platform="youtube_video").format == Format.for_aspect("16:9")
    assert MontageTimeline(target_platform="instagram_reels").format == Format()
    with pytest.raises(ValidationError):
        MontageTimeline(target_platform="unknown")


@pytest.mark.parametrize("duration,blocked", [(179_999, False), (180_000, False), (180_001, True)])
def test_shorts_duration_boundary(duration, blocked):
    result = evaluate_timeline(timeline("youtube_shorts", duration), Settings())
    assert bool(result.errors) is blocked


def test_hard_restrictions_vs_recommendations():
    assert check_limits(60_000, 1080, 1920) == []
    assert any("24 fps" in w for w in check_limits(60_000, 1080, 1920, fps=24))
    assert evaluate_profile("youtube_shorts", 180_000, 1920, 1080).errors
    square = evaluate_profile("youtube_shorts", 180_000, 1080, 1080, fps=24)
    assert not square.errors and square.warnings
    ig = evaluate_profile("instagram_reels", 1_200_001, 540, 960, fps=24)
    assert not ig.errors and len(ig.warnings) == 3
    assert "not an upload maximum" in ig.warnings[-1]
    yt = evaluate_profile("youtube_video", 180_000, 1080, 1920)
    assert not yt.errors and any("classify" in w for w in yt.warnings)
    assert not any("classify" in w for w in evaluate_profile("youtube_video", 180_001, 1080, 1920).warnings)
    assert evaluate_profile("custom", 9_999_999, 540, 960, fps=24).model_dump() == {"errors": [], "warnings": []}
    with pytest.raises(ValueError, match="Unknown target platform"):
        check_limits(1000, 1080, 1920, platform="unknown")
    assert "uzun" in check_limits(2000, 10, 10, platform="old", limits={"old": {"max_duration_s": 1}})[0]


def test_safe_zone_used_in_actual_ass_and_logo_without_settings_mutation():
    settings = Settings(safe_zone=SubtitleSafeZone(top_pct=.2, bottom_pct=.2, side_pct=.2))
    before = settings.model_dump()
    captions = Captions(enabled=True, words=[Word(text="Salom", start_ms=0, end_ms=1000, conf=1)])
    ig = timeline("instagram_reels", captions=captions)
    yt = timeline("youtube_video", format=ig.format, captions=captions)
    ig_ass, yt_ass = _ass_doc(ig, settings), _ass_doc(yt, settings)
    # Actual ASS styles carry the per-profile pixel margins on the same 1080x1920 canvas.
    assert ",64,64,672,1" in ig_ass
    assert ",54,54,96,1" in yt_ass
    assert "Dialogue:" in ig_ass and "Salom" in ig_ass
    assert _ass_doc(ig, settings, offset_ms=100) != _ass_doc(yt, settings, offset_ms=100)
    ig_logo, _ = _overlay_chain(ig, settings, "v", ass=False, fonts=False, logo_idx=1, at_ms=None)
    yt_logo, _ = _overlay_chain(yt, settings, "v", ass=False, fonts=False, logo_idx=1, at_ms=100)
    assert ig_logo != yt_logo
    assert settings.model_dump() == before
    assert profile_settings(settings, "custom").safe_zone == settings.safe_zone
    assert profile_settings(settings, "instagram_reels").safe_zone.bottom_pct == .35


def test_sticker_rotation_bounds_warn_without_moving():
    # At zero degrees this fits; rotation in pixel space crosses the right margin.
    sticker = StickerItem(id="label", path="missing.png", start_ms=0, end_ms=1000,
                          x=.82, y=.4, width=.1, height=.2, rotation=0)
    tl = timeline("instagram_reels", stickers=[sticker])
    assert not evaluate_timeline(tl, Settings()).warnings
    tl.stickers[0].rotation = 90
    before = tl.to_json()
    result = evaluate_timeline(tl, Settings())
    assert any("label" in w and "rotated bounds" in w for w in result.warnings)
    assert not result.errors
    assert tl.to_json() == before


def test_profiles_and_check_api(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)
    with client:
        response = client.get("/v1/export-profiles")
        assert response.status_code == 200
        profiles = response.json()["profiles"]
        assert [p["id"] for p in profiles] == ["instagram_reels", "youtube_shorts", "youtube_video", "custom"]
        assert all(p["verified_at"] == "2026-10-24" for p in profiles)
        assert profiles[2]["recommended_format"] == {"aspect": "16:9", "w": 1920, "h": 1080, "fps": 30., "audio_hz": 48000}
        assert profiles[3]["recommended_format"] is None
        state.settings.safe_zone.bottom_pct = .12
        assert client.get("/v1/export-profiles").json()["profiles"][3]["safe_zone"]["bottom_pct"] == .12
        checked = client.post("/v1/export-profiles:check", json={"timeline": timeline("youtube_shorts", 180_001).to_json()})
        assert checked.status_code == 200
        assert checked.json()["errors"] and not checked.json()["warnings"]
        overlay = timeline("instagram_reels", 180_001, stickers=[StickerItem(
            id="outside", path="x.png", start_ms=0, end_ms=1000, x=.99, y=.99)])
        warning_only = client.post("/v1/export-profiles:check", json={"timeline": overlay.to_json()})
        assert warning_only.status_code == 200
        assert not warning_only.json()["errors"]
        assert any("outside" in w for w in warning_only.json()["warnings"])
        bad = {"timeline": {"target_platform": "unknown"}}
        assert client.post("/v1/export-profiles:check", json=bad).status_code == 422
        assert client.post("/v1/episodes/missing/clips/missing:export",
                           json={"out_dir": str(tmp_path), "platform": "unknown"}).status_code == 422
        schema = client.get("/openapi.json").json()
        assert schema["paths"]["/v1/export-profiles"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("ExportProfilesResponse")
        assert client.get("/v1/export-profiles", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_api_rejects_before_render_queue(tmp_path, monkeypatch):
    from lahza_engine.montage.model import MediaRef, VideoItem

    client, state = make_client(tmp_path, monkeypatch)
    media = MediaRef(id="m", path="missing.mp4", duration_ms=180001, width=1920, height=1080, fps=30)
    tl = MontageTimeline(target_platform="youtube_shorts", media={"m": media},
                         video=[VideoItem(id="v", media="m", src_in_ms=0, src_out_ms=180001)])
    state.lib_write("INSERT INTO montages(id, name, status, timeline_json, template_id, sources_json) VALUES (?, ?, ?, ?, ?, ?)",
                    ("profile", "Profile", "ready", json.dumps(tl.to_json()), "test", "[]"))
    monkeypatch.setattr(state.jobs, "submit", lambda *a, **kw: pytest.fail("render must not queue"))
    with client:
        res = client.post("/v1/montages/profile:render", json={"out_dir": str(tmp_path)})
        assert res.status_code == 400 and "180s" in res.json()["detail"]
        assert not state.lib("SELECT id FROM montage_exports WHERE montage_id='profile'")
        bad = tl.to_json() | {"target_platform": "unknown"}
        assert client.put("/v1/montages/profile/timeline", json=bad).status_code == 422


def test_direct_render_rejects_before_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr("lahza_engine.render.montage_render.find_tool", lambda *a: pytest.fail("no ffmpeg"))
    with pytest.raises(ValueError, match="180s"):
        render_montage(timeline("youtube_shorts", 180001), tmp_path / "out.mp4", tmp_path, None, Settings())


def test_profile_source_claims():
    profiles = export_profiles().profiles
    assert profiles[0].restrictions.max_duration_s is None
    assert profiles[0].recommendations.max_duration_s == 180
    assert profiles[1].restrictions.square_or_vertical
    assert "not an official" in profiles[1].safe_zone_note
    assert "not universal organic" in profiles[0].safe_zone_note


def test_core_clip_unknown_platform_fails_before_database_access(tmp_path):
    from lahza_engine.core.export import export_clip

    with pytest.raises(ValueError, match="Unknown target platform"):
        export_clip(None, "m", None, tmp_path, tmp_path, Settings(), None, None, platform="unknown")


def test_planner_applies_platform_defaults_and_preserves_custom():
    from test_montage_plan import plan, scene_sources

    from lahza_engine.templates.model import Template

    template = Template(id="test", name={"uz": "Test"}, selection="scenes", aspect="1:1", fps=25)
    custom = plan(template, scene_sources())
    assert custom.target_platform == "custom" and custom.format == Format.for_aspect("1:1", fps=25)
    youtube = plan(template, scene_sources(), target_platform="youtube_video")
    assert youtube.target_platform == "youtube_video"
    assert youtube.format == Format.for_aspect("16:9", fps=30)
    explicit = plan(template, scene_sources(), target_platform="youtube_shorts", aspect="1:1")
    assert explicit.format.aspect == "1:1"
