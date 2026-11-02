"""Shared export presets, verified restrictions, and non-blocking Lahza guides.

Safe zones are normalized margins, not guarantees about platform UI placement.
The Pydantic response models are the public /v1/export-profiles OpenAPI contract.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from lahza_engine.config import Settings, SubtitleSafeZone

if TYPE_CHECKING:
    from lahza_engine.montage.model import MontageTimeline

Platform = Literal["instagram_reels", "youtube_shorts", "youtube_video", "custom"]


class RecommendedFormat(BaseModel):
    aspect: Literal["9:16", "16:9"]
    w: int
    h: int
    fps: float = 30.0
    audio_hz: int = 48_000


class Restrictions(BaseModel):
    max_duration_s: float | None = None
    square_or_vertical: bool = False


class Recommendations(BaseModel):
    max_duration_s: float | None = None
    encoding: str | None = None
    fps_note: str = "30 fps is a Lahza preset, not a platform minimum."


class ProfileSource(BaseModel):
    url: str
    verification_status: Literal["verified", "unavailable"]
    note: str


class ExportProfile(BaseModel):
    id: Platform
    name: str
    recommended_format: RecommendedFormat | None
    safe_zone: SubtitleSafeZone
    safe_zone_note: str
    restrictions: Restrictions = Field(default_factory=Restrictions)
    recommendations: Recommendations = Field(default_factory=Recommendations)
    sources: list[ProfileSource] = Field(default_factory=list)
    verified_at: str = "2026-10-24"


class ExportProfilesResponse(BaseModel):
    profiles: list[ExportProfile]


YT_SHORTS = "https://support.google.com/youtube/answer/15424877"
YT_ENCODING = "https://support.google.com/youtube/answer/1722171"


def export_profiles(settings: Settings | None = None) -> ExportProfilesResponse:
    vertical = RecommendedFormat(aspect="9:16", w=1080, h=1920)
    youtube_sources = [ProfileSource(url=YT_ENCODING, verification_status="verified",
                                    note="MP4/H.264/AAC recommended; retain source FPS. 16:9 is standard, not required."),
                       ProfileSource(url="https://support.google.com/youtube/answer/71673",
                                     verification_status="verified",
                                     note="Upload advisory: 256 GB or 12 hours, whichever is less; unverified accounts have a 15 minute limit.")]
    youtube_rec = Recommendations(encoding="MP4 / H.264 / AAC",
                                 fps_note="Preserve source FPS when possible; 30 fps is the Lahza default, not a requirement.")
    return ExportProfilesResponse(profiles=[
        ExportProfile(id="instagram_reels", name="Instagram Reels", recommended_format=vertical,
                      safe_zone=SubtitleSafeZone(),
                      safe_zone_note="Conservative Lahza guides based on Reels ads guidance; not universal organic Reels rules. 1080x1920 is a Lahza preset.",
                      recommendations=Recommendations(max_duration_s=180, encoding="MP4 / H.264 / AAC"),
                      sources=[ProfileSource(url="https://www.facebook.com/business/ads/facebook-instagram-reels-ads",
                                             verification_status="verified",
                                             note="Official Reels ads guidance: 9:16, audio and safe zones. Numeric margins are Lahza guides, not universal organic rules."),
                               ProfileSource(url="https://help.instagram.com/1038071743007909",
                                             verification_status="unavailable", note="429/login; no hard FPS, resolution or file size limit asserted."),
                               ProfileSource(url="https://help.instagram.com/2720958398006062",
                                             verification_status="unavailable", note="429/login; 180 seconds is a conservative Lahza recommendation, not an upload maximum.")]),
        ExportProfile(id="youtube_shorts", name="YouTube Shorts", recommended_format=vertical,
                      safe_zone=SubtitleSafeZone(top_pct=.10, bottom_pct=.25, side_pct=.10),
                      safe_zone_note="Conservative Lahza app guide, explicitly not an official YouTube safe zone.",
                      restrictions=Restrictions(max_duration_s=180, square_or_vertical=True),
                      recommendations=youtube_rec,
                      sources=[ProfileSource(url=YT_SHORTS, verification_status="verified",
                                             note="Shorts classification requires square or vertical video up to three minutes."), *youtube_sources]),
        ExportProfile(id="youtube_video", name="YouTube Video",
                      recommended_format=RecommendedFormat(aspect="16:9", w=1920, h=1080),
                      safe_zone=SubtitleSafeZone(top_pct=.05, bottom_pct=.05, side_pct=.05),
                      safe_zone_note="Lahza 5% title/logo guide; not an official YouTube restriction.",
                      recommendations=youtube_rec, sources=youtube_sources),
        ExportProfile(id="custom", name="Custom", recommended_format=None,
                      safe_zone=(settings or Settings()).safe_zone.model_copy(),
                      safe_zone_note="Current user settings; preserves existing custom exports.")])


def get_profile(platform: str, settings: Settings | None = None) -> ExportProfile:
    for profile in export_profiles(settings).profiles:
        if profile.id == platform:
            return profile
    raise ValueError(f"Unknown target platform: {platform}")


def profile_settings(settings: Settings, platform: str) -> Settings:
    """Copy settings without mutating the application-wide settings object."""
    return settings.model_copy(update={"safe_zone": get_profile(platform, settings).safe_zone})


class ProfileEvaluation(BaseModel):
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def evaluate_profile(platform: str, duration_ms: int, width: int, height: int,
                     fps: float | None = None, settings: Settings | None = None) -> ProfileEvaluation:
    p = get_profile(platform, settings)
    result = ProfileEvaluation()
    if p.restrictions.max_duration_s is not None and duration_ms > p.restrictions.max_duration_s * 1000:
        result.errors.append(f"{p.name}: duration {duration_ms / 1000:g}s exceeds 180s; shorten explicitly or choose YouTube Video/custom. Nothing was trimmed.")
    if p.restrictions.square_or_vertical and width > height:
        result.errors.append(f"{p.name}: square or vertical video required; got {width}x{height}. Choose a square/vertical format or another profile.")
    if p.recommended_format:
        f = p.recommended_format
        if (width, height) != (f.w, f.h):
            result.warnings.append(f"{p.name}: Lahza recommends {f.w}x{f.h}; got {width}x{height}.")
        if fps is not None and fps != f.fps:
            result.warnings.append(f"{p.name}: {fps:g} fps differs from the Lahza {f.fps:g} fps preset. {p.recommendations.fps_note}")
    if p.recommendations.max_duration_s is not None and duration_ms > p.recommendations.max_duration_s * 1000:
        result.warnings.append(f"{p.name}: duration exceeds the conservative Lahza 180s recommendation, not an upload maximum.")
    if platform == "youtube_video" and duration_ms <= 180_000 and width <= height:
        result.warnings.append("YouTube may classify square or vertical videos up to 180s as Shorts despite the YouTube Video profile; use a wider format such as 16:9 for long-form classification.")
    return result


def evaluate_timeline(tl: MontageTimeline, settings: Settings) -> ProfileEvaluation:
    result = evaluate_profile(tl.target_platform, tl.duration_ms, tl.format.w, tl.format.h,
                              tl.format.fps, settings)
    safe = get_profile(tl.target_platform, settings).safe_zone
    W, H = tl.format.w, tl.format.h
    for sticker in tl.stickers:
        angle = math.radians(sticker.rotation)
        # Rotation occurs in pixel space, so account for non-square canvas dimensions.
        w, h = sticker.width * W, sticker.height * H
        rx = (abs(w * math.cos(angle)) + abs(h * math.sin(angle))) / 2 / W
        ry = (abs(w * math.sin(angle)) + abs(h * math.cos(angle))) / 2 / H
        if (sticker.x - rx < safe.side_pct or sticker.x + rx > 1 - safe.side_pct
                or sticker.y - ry < safe.top_pct or sticker.y + ry > 1 - safe.bottom_pct):
            result.warnings.append(f"Sticker '{sticker.id}' extends outside the Lahza safe guide (approximate rotated bounds); position unchanged.")
    return result
