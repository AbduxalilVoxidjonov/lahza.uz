"""Bitta klipni eksport qilish: reframe rejasi -> ASS -> render -> SRT/VTT, caption.txt, muqova
(TZ 10-bo'lim). Shu yerda muharrir uchun bitta kadrli preview ham (render_preview_frame).
"""

from __future__ import annotations

import logging
import re
import shutil
import sqlite3
import string
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from lahza_engine.config import Settings
from lahza_engine.db import store as db
from lahza_engine.media.tools import find_tool, run
from lahza_engine.reframe.planner import (
    Keyframe,
    LayoutSegment,
    Observation,
    key_at,
    keyframes_from_layouts,
    layouts_from_keyframes,
    plan,
)
from lahza_engine.render.capabilities import has_filter
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.render.graph import RenderJob, render, render_frame
from lahza_engine.render.limits import check_limits, source_quality_warning
from lahza_engine.render.profiles import evaluate_profile, profile_settings
from lahza_engine.subtitle.ass import build_ass, build_srt, build_vtt
from lahza_engine.subtitle.fonts import default_fonts_dir, has_fonts
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.text.translit import display_text
from lahza_engine.timeline import Timeline, clip_timeline
from lahza_engine.types import Clip, Layout, Word

log = logging.getLogger(__name__)

DEFAULT_FILENAME_TEMPLATE = "{shou}_{epizod}_{nn}_{sarlavha}"
FILENAME_FIELDS = frozenset({"shou", "epizod", "nn", "sarlavha"})
_UNSAFE_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


@dataclass
class ExportResult:
    video: Path
    srt: Path
    caption: Path
    cover: Path | None
    vtt: Path | None = None
    warnings: list[str] = field(default_factory=list)


def slug(text: str, max_len: int = 40) -> str:
    t = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    t = re.sub(r"[\s_-]+", "-", t)
    return t[:max_len].strip("-") or "klip"


def render_filename(template: str, show: str, episode: str, index: int, title: str) -> str:
    """Fayl nomi shabloni (kengaytmasiz): {shou}, {epizod}, {nn}, {sarlavha}; har biri slug."""
    tpl = template.strip() or DEFAULT_FILENAME_TEMPLATE
    try:
        used = {f for _, f, _, _ in string.Formatter().parse(tpl) if f is not None}
    except ValueError as e:
        raise ValueError("Fayl nomi shablonida qavslar noto'g'ri") from e
    unknown = used - FILENAME_FIELDS
    if unknown:
        raise ValueError(
            f"Fayl nomi shablonida noma'lum maydon: {{{sorted(unknown)[0]}}}. "
            "Ruxsat etilgan: {shou}, {epizod}, {nn}, {sarlavha}"
        )
    name = tpl.format(shou=slug(show), epizod=slug(episode), nn=f"{index:02d}",
                      sarlavha=slug(clip_title_or_default(title)))
    name = _UNSAFE_FS.sub("-", name).strip(" .-")
    return name[:120] or "klip"


def clip_title_or_default(title: str) -> str:
    return title or "klip"


# --- Kalit kadrlar (reframe_keyframes) ------------------------------------------------------


def load_keyframes(conn: sqlite3.Connection, clip_id: str, source: str) -> list[Keyframe]:
    rows = conn.execute(
        "SELECT t_ms, layout, cx, cy, zoom, lane FROM reframe_keyframes "
        "WHERE clip_id = ? AND source = ? ORDER BY lane, t_ms",
        (clip_id, source),
    ).fetchall()
    return [Keyframe(int(r[0]), Layout(r[1]), r[2], r[3], float(r[4] or 1.0), r[5] or "a")
            for r in rows]


def save_auto_keyframes(conn: sqlite3.Connection, clip_id: str, layouts: list[LayoutSegment]) -> bool:
    """Avtomatik rejani source='avto' qatorlar sifatida yozadi (UI ko'rsatishi uchun).
    Qo'lda yozuv bo'lsa tegmaydi va False qaytaradi."""
    with conn:
        has_manual = conn.execute(
            "SELECT 1 FROM reframe_keyframes WHERE clip_id = ? AND source = 'qolda' LIMIT 1",
            (clip_id,),
        ).fetchone()
        if has_manual:
            return False
        conn.execute("DELETE FROM reframe_keyframes WHERE clip_id = ? AND source = 'avto'",
                     (clip_id,))
        conn.executemany(
            "INSERT INTO reframe_keyframes (clip_id, t_ms, layout, cx, cy, zoom, lane, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'avto')",
            [(clip_id, k.t_ms, k.layout.value, k.cx, k.cy, k.zoom, k.lane)
             for k in keyframes_from_layouts(layouts)],
        )
    return True


# --- Avtomatik reframe -------------------------------------------------------------------------


def _speech_at(words: list[Word], t_src: int) -> tuple[str | None, bool]:
    """(shu paytdagi spiker, ustma-ust gapirish bormi)."""
    speakers = {w.speaker for w in words if w.speaker and w.start_ms <= t_src < w.end_ms}
    if len(speakers) == 1:
        return next(iter(speakers)), False
    return None, len(speakers) >= 2


def observations_for_clip(
    src: Path, clip: Clip, timeline: Timeline, detector, settings: Settings, src_w: int, src_h: int,
    scene_cuts: list[int] | None = None, words: list[Word] | None = None,
) -> list[Observation]:
    """Yuz aniqlash (5 fps) -> klip vaqtidagi kuzatuvlar. ASD modeli R0'da qo'shiladi; hozircha
    bitta yuz bo'lsa u, bir nechta bo'lsa eng kattasi faol hisoblanadi.

    scene_cuts (manba vaqtida) va matn orqali o'chirilgan joylar -> shot_cut (kamera yo'li qayta
    boshlanadi). words (spiker belgili) -> spiker almashinuvi va ustma-ust gapirish (split).
    """
    from lahza_engine.media.frames import iter_frames
    from lahza_engine.reframe.faces import FaceTracker

    tracker = FaceTracker()
    obs: list[Observation] = []
    cuts = sorted(scene_cuts or [])
    bounds = timeline.boundaries_out()
    spk_words = [w for w in (words or []) if w.speaker]
    prev_src: int | None = None
    prev_out: int | None = None
    for t_src, frame in iter_frames(src, clip.start_ms, clip.end_ms, settings.reframe.analysis_fps,
                                    src_w=src_w, src_h=src_h):
        t_out = timeline.to_out(t_src)
        if t_out is None:
            continue
        shot_cut = prev_src is not None and (
            any(prev_src < c <= t_src for c in cuts)
            or any(prev_out is not None and prev_out < b <= t_out for b in bounds)
        )
        prev_src, prev_out = t_src, t_out
        boxes = detector.detect(frame)
        tracker.update(t_out, boxes)
        active = None
        if boxes:
            active = max(range(len(boxes)), key=lambda i: boxes[i].w * boxes[i].h)
        speaker, overlap = _speech_at(spk_words, t_src) if spk_words else (None, False)
        obs.append(Observation(t_out, boxes, active, shot_cut=shot_cut, overlap_speech=overlap,
                               speaker=speaker))
    return _with_hook_prefix(obs, timeline)


def _with_hook_prefix(obs: list[Observation], timeline: Timeline) -> list[Observation]:
    """Hook prefiksi (PRO-3): hook oralig'idagi kuzatuvlar chiqish boshiga nusxalanadi; asosiy
    qism boshlanishi - kamera kesimi (tasvir keskin almashadi)."""
    if not timeline.prefix_ms or not obs:
        return obs
    pre: list[Observation] = []
    for o in obs:
        t_src = timeline.to_src(o.t_ms)
        t_pre = timeline.prefix_to_out(t_src)
        if t_pre is not None and t_pre < timeline.prefix_ms:
            pre.append(replace(o, t_ms=t_pre, shot_cut=not pre or o.shot_cut))
    body = list(obs)
    body[0] = replace(body[0], shot_cut=True)
    return pre + body


def build_layout_plan(
    src: Path, clip: Clip, timeline: Timeline, detector, settings: Settings, src_w: int, src_h: int,
    manual_layout: Layout | None = None, words: list[Word] | None = None,
    detect_scenes: bool = True,
) -> list[LayoutSegment]:
    if manual_layout is Layout.FIT_BLUR or detector is None:
        return [LayoutSegment(0, timeline.duration_ms, Layout.FIT_BLUR)]
    cuts: list[int] = []
    if detect_scenes:
        from lahza_engine.media.scenes import detect_scene_cuts

        try:
            cuts = detect_scene_cuts(src, clip.start_ms, clip.end_ms)
        except Exception as e:  # noqa: BLE001 - kesim topilmasa ham reframe ishlaydi
            log.warning("sahna kesimlarini aniqlab bo'lmadi: %s", type(e).__name__)
    obs = observations_for_clip(src, clip, timeline, detector, settings, src_w, src_h,
                                scene_cuts=cuts, words=words)
    return plan(obs, timeline.duration_ms, settings.reframe)


def resolve_layouts(
    conn: sqlite3.Connection, src: Path, clip: Clip, timeline: Timeline, detector,
    settings: Settings, src_w: int, src_h: int, words: list[Word] | None = None,
    layouts: list[LayoutSegment] | None = None, use_auto_cache: bool = False,
) -> tuple[list[LayoutSegment], str]:
    """Layout manbai ustuvorligi: qo'lda kalit kadrlar > berilgan `layouts` > (preview'da)
    saqlangan avto qatorlar > yangi avtomatik reja (jadvalga 'avto' sifatida yoziladi)."""
    dur = timeline.duration_ms
    cut_thr = settings.reframe.cut_threshold
    manual = load_keyframes(conn, clip.id, "qolda")
    if manual:
        return layouts_from_keyframes(manual, dur, cut_thr), "qolda"
    if layouts is not None:
        return layouts, "berilgan"
    if use_auto_cache:
        auto = load_keyframes(conn, clip.id, "avto")
        if auto:
            return layouts_from_keyframes(auto, dur, cut_thr), "avto"
    planned = build_layout_plan(src, clip, timeline, detector, settings, src_w, src_h, words=words)
    save_auto_keyframes(conn, clip.id, planned)
    return planned, "avto"


# --- Eksport -----------------------------------------------------------------------------------


def _clip_words(conn: sqlite3.Connection, media_id: str, clip: Clip) -> list[Word]:
    tr = db.load_transcript(conn, media_id)
    return [w for w in tr.words if w.end_ms > clip.start_ms and w.start_ms < clip.end_ms]


def _logo(style: StyleTemplate, warnings: list[str]) -> Path | None:
    if not style.logo_path:
        return None
    p = Path(style.logo_path).expanduser()
    if not p.is_file():
        warnings.append(f"Logotip fayli topilmadi ({p.name}) - logotipsiz eksport qilindi")
        return None
    return p


def _fonts(fonts_dir: Path | None) -> Path | None:
    if fonts_dir is not None:
        return fonts_dir
    d = default_fonts_dir()
    return d if has_fonts(d) else None


def export_clip(
    conn: sqlite3.Connection,
    media_id: str,
    clip: Clip,
    out_dir: Path,
    workdir: Path,
    settings: Settings,
    encoder: EncoderChoice,
    style: StyleTemplate,
    detector=None,
    fonts_dir: Path | None = None,
    show_name: str = "lahza",
    episode: str = "ep",
    index: int = 1,
    layouts: list[LayoutSegment] | None = None,
    filename_template: str = DEFAULT_FILENAME_TEMPLATE,
    allow_no_subs: bool = False,
    platform: str = "instagram_reels",
) -> ExportResult:
    """Klipni eksport qiladi. libass yo'q bo'lsa LibassMissing (allow_no_subs=True - subtitrsiz,
    ogohlantirish bilan). Qo'lda kalit kadrlar (reframe_keyframes, source='qolda') ustun."""
    settings = profile_settings(settings, platform)
    media = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    if media is None:
        raise KeyError(media_id)
    src = Path(media["path"])
    W, H = settings.render.width, settings.render.height
    tl = clip_timeline(clip)
    evaluation = evaluate_profile(platform, tl.duration_ms, W, H, settings=settings)
    if evaluation.errors:
        raise ValueError("; ".join(evaluation.errors))
    words = _clip_words(conn, media_id, clip)
    base = render_filename(filename_template, show_name, episode, index, clip.title)
    ass_text = build_ass(words, tl, style, settings.safe_zone, W, H)
    layouts, _source = resolve_layouts(conn, src, clip, tl, detector, settings, media["width"],
                                       media["height"], words=words, layouts=layouts)

    # Shared profile restrictions were checked above; recommendations only warn here.
    warnings = check_limits(tl.duration_ms, W, H, platform=platform)
    uses_crop = any(seg.layout is not Layout.FIT_BLUR for seg in layouts)
    q = source_quality_warning(media["width"], media["height"], W, uses_crop)
    if q:
        warnings.append(q)
    ffmpeg = str(find_tool("ffmpeg"))
    if allow_no_subs and not has_filter(ffmpeg, "ass"):
        warnings.append("Subtitr videoga chizilmadi: FFmpeg libass'siz. SRT/VTT fayllari tayyor.")

    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / f"{base}.mp4"
    render(RenderJob(src=src, out=video, workdir=workdir, src_w=media["width"], src_h=media["height"],
                     fps=media["fps"], timeline=tl, layouts=layouts, encoder=encoder,
                     cfg=settings.render, ass_text=ass_text, fonts_dir=_fonts(fonts_dir),
                     logo=_logo(style, warnings), logo_position=style.logo_position,
                     logo_opacity=style.logo_opacity, safe_zone=settings.safe_zone),
           allow_no_subs=allow_no_subs)
    for w in check_limits(tl.duration_ms, W, H, file_bytes=video.stat().st_size, platform=platform):
        if w not in warnings:
            warnings.append(w)

    srt = out_dir / f"{base}.srt"
    srt.write_text(build_srt(words, tl, style=style), encoding="utf-8")
    vtt = out_dir / f"{base}.vtt"
    vtt.write_text(build_vtt(words, tl, style=style), encoding="utf-8")
    caption = out_dir / f"{base}_caption.txt"
    title = display_text(clip.title, style.orthography, style.script)
    body = display_text(clip.caption, style.orthography, style.script)
    caption.write_text("\n\n".join(x for x in (title, body, " ".join(clip.hashtags)) if x) + "\n",
                       encoding="utf-8")
    cover: Path | None = out_dir / f"{base}_cover.jpg"
    r = run([ffmpeg, "-y", "-v", "error", "-ss", f"{tl.duration_ms / 2000:.3f}", "-i", video,
             "-frames:v", "1", "-q:v", "2", cover])
    with conn:
        conn.execute("UPDATE clips SET status = 'eksport_qilingan' WHERE id = ?", (clip.id,))
    if r.returncode != 0:
        cover = None
    shutil.rmtree(workdir, ignore_errors=True)
    return ExportResult(video, srt, caption, cover, vtt=vtt, warnings=warnings)


PREVIEW_SPAN_MS = 100


def render_preview_frame(
    conn: sqlite3.Connection,
    media_id: str,
    clip: Clip,
    t_out_ms: int,
    style: StyleTemplate,
    settings: Settings,
    out_jpg: Path,
    detector=None,
) -> Path:
    """Muharrir uchun bitta 1080x1920 JPG kadr: layout + subtitr (+ logotip).

    Kirishda -ss bilan tez qidiruv, faqat 1 kadr dekodlanadi. libass yo'q bo'lsa subtitrsiz
    (xato bermaydi). Layout: qo'lda kalit kadrlar > saqlangan avto reja > yangi reja.
    """
    media = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    if media is None:
        raise KeyError(media_id)
    src = Path(media["path"])
    W, H = settings.render.width, settings.render.height
    tl = clip_timeline(clip)
    t_out = max(0, min(tl.duration_ms - 1, int(t_out_ms)))
    words = _clip_words(conn, media_id, clip)
    layouts, _ = resolve_layouts(conn, src, clip, tl, detector, settings, media["width"],
                                 media["height"], words=words, use_auto_cache=True)
    seg = next((s for s in layouts if s.start_ms <= t_out < s.end_ms), layouts[-1])
    rel = t_out - seg.start_ms
    one = LayoutSegment(0, PREVIEW_SPAN_MS, seg.layout,
                        keys=[key_at(seg.keys, rel)] if seg.keys else [],
                        keys_b=[key_at(seg.keys_b, rel)] if seg.keys_b else [])
    src_t = tl.to_src(t_out)
    media_dur = int(media["duration_ms"] or 0)
    if media_dur and src_t + PREVIEW_SPAN_MS > media_dur:
        src_t = max(0, media_dur - PREVIEW_SPAN_MS)
    ass_text = build_ass(words, tl, style, settings.safe_zone, W, H, offset_ms=t_out)
    warnings: list[str] = []
    out_jpg = Path(out_jpg)
    with tempfile.TemporaryDirectory(prefix="lahza-preview-") as tmp:
        job = RenderJob(
            src=src, out=out_jpg, workdir=Path(tmp), src_w=media["width"], src_h=media["height"],
            fps=media["fps"] or 25.0, timeline=Timeline(src_t, src_t + PREVIEW_SPAN_MS),
            layouts=[one], encoder=EncoderChoice("mjpeg", (), False), cfg=settings.render,
            ass_text=ass_text, fonts_dir=_fonts(None), logo=_logo(style, warnings),
            logo_position=style.logo_position, logo_opacity=style.logo_opacity,
            safe_zone=settings.safe_zone,
        )
        render_frame(job)
    return out_jpg
