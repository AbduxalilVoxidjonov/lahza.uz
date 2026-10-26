"""Klip yoki montaj -> host-reja (`lahza.hostplan/1`, docs/04 "Adobe plaginlari").

Matematika render grafi (`render/graph.py`, `render/montage_render.py`) bilan bir xil kadr beradi:

* crop oynasi (x, y, w, h) manba pikselida, chiqish (sekvensiya) W x H:
  `scale = W / w`, `scale_pct = scale * 100`,
  `pos_x = W/2 + (sw/2 - (x + w/2)) * scale`, `pos_y = H/2 + (sh/2 - (y + h/2)) * scale`
  (anchor = manba markazi; Premiere "Motion" va AE "Transform" modeli).
* split: har yarim kadr o'z to'rtburchagi (crop_rect) markaziga joylanadi.
* fit_blur: bg = to'ldirish (max) + gaussian_blur, main = sig'dirish (min), ikkalasi markazda.

Render'dagi bitta farq: ffmpeg crop'ni W x H ga notekis (scale=W:H) cho'zadi, host esa bir xil
masshtab beradi - juft songa yaxlitlash tufayli vertikal farq <= 0.3% (1080x1920 da ~1-2 px manba).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from lahza_engine.config import Settings
from lahza_engine.core.export import build_layout_plan, load_keyframes, save_auto_keyframes, slug
from lahza_engine.hostplan.model import (
    CaptionLine,
    Captions,
    CaptionWord,
    HostEffect,
    HostLayer,
    HostMedia,
    HostPlan,
    HostTransition,
    Marker,
    MusicItem,
    Sequence,
    TextOverlay,
    TransformKey,
    VideoClipItem,
)
from lahza_engine.reframe.planner import CropKey, LayoutSegment, crop_rect, layouts_from_keyframes
from lahza_engine.render.graph import Piece, _keys_for_piece, split_pieces
from lahza_engine.subtitle.ass import _Lexicon, build_srt, caption_breaks, clean_words, map_words
from lahza_engine.subtitle.layout import chunk_words, hold_end, max_chars_per_line
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.text.orthography import Orthography, convert
from lahza_engine.text.translit import display_text
from lahza_engine.timeline import Timeline
from lahza_engine.types import Clip, Layout, Word

log = logging.getLogger(__name__)

ASPECT_SIZE: dict[str, tuple[int, int]] = {"9:16": (1080, 1920), "1:1": (1080, 1080),
                                           "16:9": (1920, 1080)}
BG_BLUR_AMOUNT = 60.0
"""Xira fon: render'da ffmpeg `gblur=sigma=30`. Premiere/AE "Blurriness" shkalasi sigma emas -
60 ko'rinishi yaqin (taxminiy, plagin sozlashi mumkin)."""
EMPHASIS_SCORE = 70.0
"""Signal bali shundan yuqori gaplar - emphasis marker (montage/analyze `strong_score` bilan bir xil)."""
CAPTION_HOLD_MS = 400
"""Qisqa pauzada subtitr miltillamasin - ASS bilan bir xil (subtitle/ass.py)."""


# --- Koordinata matematikasi -------------------------------------------------------------------


def crop_transform(
    x: float, y: float, w: float, h: float, src_w: int, src_h: int,
    rect: tuple[float, float, float, float],
) -> tuple[float, float, float]:
    """Manba crop oynasi -> (scale_pct, pos_x, pos_y): oyna `rect` (sekvensiya px) ni eni bo'yicha
    to'ldiradi, markazi rect markaziga tushadi."""
    rx, ry, rw, rh = rect
    scale = rw / w
    pos_x = rx + rw / 2 + (src_w / 2 - (x + w / 2)) * scale
    pos_y = ry + rh / 2 + (src_h / 2 - (y + h / 2)) * scale
    return scale * 100, pos_x, pos_y


def _r(v: float, nd: int = 3) -> float:
    return round(float(v), nd)


def _clamp_crossings(k0: CropKey, k1: CropKey, src_w: int, src_h: int, w: int, h: int
                     ) -> list[float]:
    """k0->k1 chiziqli harakatda crop kadr chetiga tegadigan (clamp boshlanadi/tugaydi) ulushlar.
    Shu nuqtalarda qo'shimcha kalit qo'yilsa, host chiziqli interpolyatsiyasi render (har kadrda
    crop_rect + clamp) bilan bir xil yo'l chizadi."""
    out: list[float] = []
    for c0, c1, size, win in ((k0.cx, k1.cx, src_w, w), (k0.cy, k1.cy, src_h, h)):
        a, b = c0 * size - win / 2, c1 * size - win / 2
        if a == b:
            continue
        for edge in (0.0, float(size - win)):
            r = (edge - a) / (b - a)
            if 0.0 < r < 1.0:
                out.append(r)
    return sorted(set(out))


def crop_keys_to_transform(
    keys: list[CropKey], src_w: int, src_h: int, aspect: float,
    rect: tuple[float, float, float, float],
) -> list[TransformKey]:
    """Bo'lak kalitlari (t_ms bo'lak boshidan) -> TransformKey. Crop o'lchami bo'lakda doimiy
    (birinchi kalit zoom'i - render/graph `_cmd_file` kabi). cut=True kalitdan oldingisi "hold"."""
    if not keys:
        keys = [CropKey(0, 0.5, cut=True)]
    zoom = keys[0].zoom
    _, _, w, h = crop_rect(keys[0].cx, src_w, src_h, aspect, zoom, keys[0].cy)
    dense: list[CropKey] = [keys[0]]
    for k0, k1 in zip(keys, keys[1:], strict=False):
        if not k1.cut and k1.t_ms > k0.t_ms:
            for r in _clamp_crossings(k0, k1, src_w, src_h, w, h):
                dense.append(CropKey(round(k0.t_ms + (k1.t_ms - k0.t_ms) * r),
                                     k0.cx + (k1.cx - k0.cx) * r, k0.cy + (k1.cy - k0.cy) * r, zoom))
        dense.append(k1)
    out: list[TransformKey] = []
    for i, k in enumerate(dense):
        x, y, cw, ch = crop_rect(k.cx, src_w, src_h, aspect, zoom, k.cy)
        s, px, py = crop_transform(x, y, cw, ch, src_w, src_h, rect)
        nxt = dense[i + 1] if i + 1 < len(dense) else None
        interp = "hold" if nxt is not None and nxt.cut else "linear"
        tk = TransformKey(t=_r(k.t_ms / 1000), scale_pct=_r(s, 4), pos_x=_r(px), pos_y=_r(py),
                          interp=interp)
        if out and abs(out[-1].t - tk.t) < 1e-9:
            out[-1] = tk  # bir paytdagi ikki kalit - keyingisi ustun
        else:
            out.append(tk)
    return out


def fit_blur_layers(src_w: int, src_h: int, W: int, H: int) -> list[HostLayer]:
    fill = max(W / src_w, H / src_h) * 100
    fit = min(W / src_w, H / src_h) * 100
    return [
        HostLayer(role="bg", keys=[TransformKey(t=0.0, scale_pct=_r(fill, 4), pos_x=W / 2, pos_y=H / 2)],
                  effects=[HostEffect(kind="gaussian_blur", amount=BG_BLUR_AMOUNT)]),
        HostLayer(role="main", keys=[TransformKey(t=0.0, scale_pct=_r(fit, 4), pos_x=W / 2, pos_y=H / 2)]),
    ]


def layers_for_piece(piece: Piece, src_w: int, src_h: int, W: int, H: int) -> list[HostLayer]:
    """Render bo'lagi (layout segmenti x timeline segmenti) -> host qatlamlari."""
    lay = piece.layout.layout
    if lay in (Layout.FOCUS, Layout.MANUAL):
        keys = _keys_for_piece(piece.layout.keys, piece)
        return [HostLayer(role="main", keys=crop_keys_to_transform(keys, src_w, src_h, W / H,
                                                                   (0, 0, W, H)))]
    if lay is Layout.SPLIT:
        half = H // 2
        ka = _keys_for_piece(piece.layout.keys, piece)
        kb = _keys_for_piece(piece.layout.keys_b or piece.layout.keys, piece)
        top = (0, 0, W, half)
        bottom = (0, half, W, H - half)
        return [
            HostLayer(role="top", keys=crop_keys_to_transform(ka, src_w, src_h, W / half, top),
                      crop_rect=top),
            HostLayer(role="bottom", keys=crop_keys_to_transform(kb, src_w, src_h, W / (H - half),
                                                                 bottom),
                      crop_rect=bottom),
        ]
    return fit_blur_layers(src_w, src_h, W, H)


# --- Subtitr ---------------------------------------------------------------------------------


def caption_lines(words_out: list[Word], style: StyleTemplate, settings: Settings, W: int,
                  breaks_ms: list[int] | None = None) -> list[CaptionLine]:
    """Chiqish vaqtidagi so'zlar (to'ldiruvchilar olib tashlangan) -> ekrandagi bo'laklar
    (subtitle/layout qoidalari, style.max_words/max_lines). Matn - imlo + so'kinish maskasi.
    breaks_ms: bo'laklar kesib o'tmaydigan chegaralar (hook prefiksi oxiri, `caption_breaks`)."""
    breaks = breaks_ms or []
    lex = _Lexicon(style)
    usable = W - 2 * int(W * settings.safe_zone.side_pct)
    chunks = chunk_words(words_out, max_words=style.max_words, max_lines=style.max_lines,
                         max_chars=max_chars_per_line(style.font_size, usable), breaks_ms=breaks)
    out: list[CaptionLine] = []
    for ci, ch in enumerate(chunks):
        end = hold_end(chunks, ci, CAPTION_HOLD_MS, breaks)
        text = "\n".join(" ".join(lex.plain(w, style) for w in line) for line in ch.lines)
        speakers = {w.speaker for w in ch.words}
        out.append(CaptionLine(
            t0=_r(ch.start_ms / 1000), t1=_r(max(end, ch.end_ms) / 1000), text=text,
            words=[CaptionWord(text=lex.plain(w, style), t0=_r(w.start_ms / 1000),
                               t1=_r(w.end_ms / 1000)) for w in ch.words],
            speaker=next(iter(speakers)) if len(speakers) == 1 else None,
        ))
    return out


def write_caption_files(out_dir: Path, base: str, srt_text: str, lines: list[CaptionLine],
                        style: StyleTemplate) -> tuple[Path, Path]:
    """SRT va so'zlar JSON. style.uppercase SRT'ga shu yerda qo'llanadi (Premiere captions uslubini
    API orqali o'rnatib bo'lmaydi); `lines`/so'zlar JSON asl registrda - uslubni plagin qo'llaydi.
    SRT'da faqat raqam, vaqt va matn bor - butun matnni upper() qilish xavfsiz."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if style.uppercase:
        srt_text = srt_text.upper()
    srt = out_dir / f"{base}.srt"
    srt.write_text(srt_text, encoding="utf-8")
    words = out_dir / f"{base}_words.json"
    doc = {
        "schema": "lahza.words/1",
        "orthography": style.orthography.value,
        "words": [w.model_dump(mode="json") for ln in lines for w in ln.words],
        "lines": [ln.model_dump(mode="json") for ln in lines],
        "style": style.model_dump(mode="json"),
    }
    words.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return srt, words


# --- Klip ------------------------------------------------------------------------------------


def _clip_layouts(conn: sqlite3.Connection, src: Path, clip: Clip, tl: Timeline, detector,
                  settings: Settings, src_w: int, src_h: int, words: list[Word]
                  ) -> list[LayoutSegment]:
    """Ustuvorlik: qo'lda kalit kadrlar > saqlangan avto reja > (detektor bo'lsa) yangi reja.
    Detektorsiz xira fon - bazaga yozilmaydi (keyin detektor bilan preview to'g'ri rejalashtirsin)."""
    dur, thr = tl.duration_ms, settings.reframe.cut_threshold
    for source in ("qolda", "avto"):
        kfs = load_keyframes(conn, clip.id, source)
        if kfs:
            return layouts_from_keyframes(kfs, dur, thr)
    if detector is None:
        return [LayoutSegment(0, dur, Layout.FIT_BLUR)]
    planned = build_layout_plan(src, clip, tl, detector, settings, src_w, src_h, words=words)
    save_auto_keyframes(conn, clip.id, planned)
    return planned


def _cached_signals(conn: sqlite3.Connection, media_id: str):
    """Highlight signallari keshi (signals bosqichi natijasi). Yo'q bo'lsa None - qayta hisoblanmaydi."""
    try:
        row = conn.execute("SELECT status, result_path FROM stage_runs WHERE media_id = ? AND stage = ?",
                           (media_id, "signals")).fetchone()
    except sqlite3.Error:
        return None
    if not row or row["status"] != "done" or not row["result_path"]:
        return None
    p = Path(row["result_path"])
    if not p.is_file():
        return None
    try:
        from lahza_engine.highlight.signals import SentenceSignals

        data = json.loads(p.read_text(encoding="utf-8"))
        return {d["sentence_id"]: SentenceSignals(**d) for d in data.get("sentences", [])}
    except (ValueError, TypeError, KeyError) as e:
        log.warning("signallar keshini o'qib bo'lmadi: %s", type(e).__name__)
        return None


def _clip_markers(conn: sqlite3.Connection, media_id: str, clip: Clip, tl: Timeline,
                  orthography: Orthography) -> list[Marker]:
    from lahza_engine.db import store as db

    sentences = [s for s in db.load_transcript(conn, media_id).sentences
                 if s.end_ms > clip.start_ms and s.start_ms < clip.end_ms]
    markers: list[Marker] = []
    hook = next((s for s in sentences if s.id == clip.hook_sentence_id), None)
    if hook is not None:
        t = tl.to_out(max(hook.start_ms, clip.start_ms))
        if t is not None:
            markers.append(Marker(t=_r(t / 1000), name="Hook", kind="hook",
                                  comment=convert(hook.text, orthography)[:200]))
    sig = _cached_signals(conn, media_id)
    if sig:
        for s in sentences:
            x = sig.get(s.id)
            if x is None or s.id == clip.hook_sentence_id or float(x.score()) < EMPHASIS_SCORE:
                continue
            t = tl.to_out(max(s.start_ms, clip.start_ms))
            if t is not None:
                markers.append(Marker(t=_r(t / 1000), name="Urg'u", kind="emphasis",
                                      comment=convert(s.text, orthography)[:200]))
    return sorted(markers, key=lambda m: m.t)


def plan_from_clip(
    conn: sqlite3.Connection,
    media_id: str,
    clip: Clip,
    settings: Settings,
    style: StyleTemplate,
    orthography: Orthography | None,
    aspect: str,
    out_dir: Path,
    detector=None,
) -> HostPlan:
    """Klip -> host-reja. out_dir'ga `<slug>.srt` va `<slug>_words.json` yoziladi."""
    from lahza_engine.db import store as db

    if aspect not in ASPECT_SIZE:
        raise ValueError(f"noma'lum nisbat: {aspect}")
    media = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    if media is None:
        raise KeyError(media_id)
    if orthography is not None:
        style = style.model_copy(update={"orthography": orthography})
    W, H = ASPECT_SIZE[aspect]
    sw, sh = int(media["width"]), int(media["height"])
    fps = float(media["fps"] or 30.0)
    src = Path(media["path"])
    tl = Timeline(clip.start_ms, clip.end_ms, clip.cuts)
    words = [w for w in db.load_transcript(conn, media_id).words
             if w.end_ms > clip.start_ms and w.start_ms < clip.end_ms]
    layouts = _clip_layouts(conn, src, clip, tl, detector, settings, sw, sh, words)

    hook_t: float | None = None
    markers = _clip_markers(conn, media_id, clip, tl, style.orthography)
    for m in markers:
        if m.kind == "hook":
            hook_t = m.t
    video: list[VideoClipItem] = []
    for i, p in enumerate(split_pieces(tl, layouts)):
        rec_in, rec_out = p.out_start_ms / 1000, p.out_end_ms / 1000
        label = "hook" if hook_t is not None and rec_in <= hook_t < rec_out else "asosiy"
        video.append(VideoClipItem(
            id=f"v{i + 1}", media=media_id, src_in=_r(p.src_start_ms / 1000),
            src_out=_r(p.src_end_ms / 1000), rec_in=_r(rec_in), rec_out=_r(rec_out),
            layers=layers_for_piece(p, sw, sh, W, H),
            transition_in=HostTransition(kind="cut") if i > 0 else None, label=label,
        ))

    words_out = map_words(clean_words(words, style), tl)
    lines = caption_lines(words_out, style, settings, W, breaks_ms=caption_breaks(tl))
    base = slug(clip.title or "klip")
    srt, words_json = write_caption_files(out_dir, base, build_srt(words, tl, style=style), lines,
                                          style)
    not_translated: list[str] = []
    if style.logo_path:
        not_translated.append("Logotip host-rejaga kirmaydi - uni sekvensiyaga qo'lda qo'ying.")
    if settings.render.loudnorm_target_lufs is not None:
        not_translated.append(
            f"Ovoz balandligini normallash ({settings.render.loudnorm_target_lufs:g} LUFS) - "
            "eksport sozlamalarida yoki Essential Sound'da qo'lda.")
    if style.keywords:
        not_translated.append("Kalit so'zlarni ajratib ko'rsatish (keywords) - plagin uslubida, "
                              "Premiere SRT subtitrida ko'rinmaydi.")

    return HostPlan(
        source="clip", source_id=clip.id,
        sequence=Sequence(name=clip.title or "Lahza klip", width=W, height=H, fps=fps,
                          duration_s=_r(tl.duration_ms / 1000)),
        media=[HostMedia(id=media_id, path=str(src.resolve()), width=sw, height=sh, fps=fps,
                         duration_s=_r((media["duration_ms"] or 0) / 1000),
                         has_audio=bool(media["audio_channels"]))],
        video=video,
        captions=Captions(srt_path=str(srt.resolve()), words_path=str(words_json.resolve()),
                          lines=lines, style=style.model_dump(mode="json")),
        markers=markers,
        not_translated=not_translated,
    )


# --- Montaj ----------------------------------------------------------------------------------

TRANSITION_MAP: dict[str, str] = {
    "dissolve": "cross_dissolve", "fade": "cross_dissolve", "fadeblack": "dip_to_black",
    "fadewhite": "dip_to_white", "zoomin": "zoom", "cut": "cut",
}


def map_transition(preset: str) -> tuple[str, bool]:
    """xfade preset -> (host o'tishi, aniq mos keldimi)."""
    if preset in TRANSITION_MAP:
        return TRANSITION_MAP[preset], True
    if preset.startswith("wipe"):
        return "wipe", True
    if preset.startswith("slide"):
        return "push", True
    return "cross_dissolve", False


def _ease(name: str, p: float) -> float:
    if name == "ease-out":
        return 1 - (1 - p) ** 2
    if name == "expo-out":
        return 1 - 2 ** (-10 * p)
    return p


def _prog(t: float, a: float, b: float) -> float:
    return min(1.0, max(0.0, (t - a) / max(b - a, 1e-3)))


class _Motion:
    """montage_render `_camera` ning Python ko'rinishi (bitta vaqt uchun son)."""

    def __init__(self, preset: str, params: dict, a: float, b: float) -> None:
        self.preset, self.p, self.a, self.b = preset, params, a, b

    def times(self) -> list[float]:
        ts = [self.a, self.b]
        if self.preset == "punch-in":
            k = max(int(self.p["kirish_ms"]) / 1000, 1e-3)
            end = min(self.b, self.a + k)
            ts.append(end)
            span = (self.a, end)
        else:
            span = (self.a, self.b)
        if self.p.get("easing", "linear") != "linear":
            ts += [span[0] + (span[1] - span[0]) * f for f in (0.25, 0.5, 0.75)]
        if self.preset == "punch-in":
            ts.append(self.b + 1e-3)  # b dan keyin zoom keskin 1 ga qaytadi (render bilan bir xil)
        return ts


def _camera_at(motions: list[_Motion], t: float, slack_x: bool, slack_y: bool
               ) -> tuple[float, float, float, float, float]:
    """(zoom, dx, dy, crop_dx, crop_dy) - montage_render `_camera` + `_zoompan` bilan bir xil."""
    z, dx, dy, cdx, cdy = 1.0, 0.0, 0.0, 0.0, 0.0
    for m in motions:
        p, a, b = m.p, m.a, m.b
        if m.preset == "punch-in":
            k = max(int(p["kirish_ms"]) / 1000, 1e-3)
            if a <= t <= b:
                z *= 1 + (float(p["zoom"]) - 1) * _ease(p["easing"], min(1.0, max(0.0, (t - a) / k)))
        elif m.preset == "push-in":
            z *= 1 + (float(p["zoom"]) - 1) * _ease(p["easing"], _prog(t, a, b))
        elif m.preset == "zoom-out":
            zz = float(p["zoom"])
            z *= zz - (zz - 1) * _ease(p["easing"], _prog(t, a, b))
        elif m.preset == "pan":
            d = p["yonalish"]
            sign = -1 if d in ("chapga", "yuqoriga") else 1
            horiz = d in ("chapga", "onga")
            off = sign * float(p["kuch"]) * (2 * _ease(p["easing"], _prog(t, a, b)) - 1)
            if horiz and slack_x:
                cdx += off
            elif not horiz and slack_y:
                cdy += off
            else:
                z *= float(p["zoom"])
                if horiz:
                    dx += off
                else:
                    dy += off
    return max(1.0, z), max(-1.0, min(1.0, dx)), max(-1.0, min(1.0, dy)), cdx, cdy


def _key_times(motions: list[_Motion], dur_s: float) -> list[float]:
    ts = {0.0, dur_s}
    for m in motions:
        ts.update(x for x in m.times() if 0.0 <= x <= dur_s)
    return sorted(round(x, 3) for x in ts)


def _montage_layers(item, media, W: int, H: int, motions: list[_Motion], dur_s: float) -> list[HostLayer]:
    from lahza_engine.render.montage_render import reframe_mode

    sw, sh = media.width, media.height
    mode = reframe_mode(item, media, W, H, None)
    times = _key_times(motions, dur_s) if motions else [0.0]
    if mode == "fit_blur":
        layers = fit_blur_layers(sw, sh, W, H)
        if not motions:
            return layers
        # zoompan butun kompozitsiyaga: ko'rish oynasi v (W/z x H/z), nuqta P -> (P - v) * z.
        for layer in layers:
            base = layer.keys[0]
            keys = []
            for t in times:
                z, dx, dy, _, _ = _camera_at(motions, t, False, False)
                vx = (W - W / z) / 2 * (1 + dx)
                vy = (H - H / z) / 2 * (1 + dy)
                keys.append(TransformKey(t=t, scale_pct=_r(base.scale_pct * z, 4),
                                         pos_x=_r((base.pos_x - vx) * z), pos_y=_r((base.pos_y - vy) * z)))
            layer.keys = keys
        return layers
    cx, cy, zoom = (item.crop.cx, item.crop.cy, item.crop.zoom) if item.crop else (.5, .5, 1.)
    x0, y0, cw, ch = crop_rect(cx, sw, sh, W / H, zoom, cy)
    slack_x = sw - cw >= 0.08 * cw
    slack_y = sh - ch >= 0.08 * ch
    keys = []
    for t in times:
        z, dx, dy, cdx, cdy = _camera_at(motions, t, slack_x, slack_y)
        x = min(max(x0 + (sw - cw) / 2 * cdx, 0), sw - cw) if cdx else x0
        y = min(max(y0 + (sh - ch) / 2 * cdy, 0), sh - ch) if cdy else y0
        # zoompan crop natijasida (cw x ch) ko'rish oynasi: o'lcham cw/z, siljish (cw - cw/z)/2*(1+dx)
        vw, vh = cw / z, ch / z
        vx = x + (cw - vw) / 2 * (1 + dx)
        vy = y + (ch - vh) / 2 * (1 + dy)
        s, px, py = crop_transform(vx, vy, vw, vh, sw, sh, (0, 0, W, H))
        keys.append(TransformKey(t=t, scale_pct=_r(s, 4), pos_x=_r(px), pos_y=_r(py)))
    return [HostLayer(role="main", keys=keys)]


def _color_effect(preset: str, backend: str, params: dict) -> HostEffect | None:
    if backend == "lut":
        f = str(params.get("file") or "")
        return HostEffect(kind="lut", lut_path=str(Path(f).expanduser())) if f else None
    if preset in ("warm", "cool", "bw", "vivid", "film"):
        return HostEffect(kind="lumetri_preset", preset=preset)
    return None


def plan_from_montage(tl, montage_id: str, name: str, out_dir: Path, settings: Settings) -> HostPlan:
    """Montaj timeline'i (`lahza.timeline/1`) -> host-reja. Xaritalanmagan narsa - not_translated."""
    from lahza_engine.fx.registry import FxError, get_plugin, validate_params
    from lahza_engine.montage.model import MontageTimeline

    assert isinstance(tl, MontageTimeline)
    fmt = tl.format
    W, H = fmt.w, fmt.h
    notes: list[str] = []

    def note(msg: str) -> None:
        if msg not in notes:
            notes.append(msg)

    if tl.stickers:
        note("Stiker qatlamlari Adobe host-rejasiga o'tkazilmagan; lokal MP4 renderda saqlanadi.")

    def plugin(pid: str, params: dict | None, where: str):
        try:
            m = get_plugin(pid)
            return m, validate_params(m, params or {})
        except (KeyError, FxError) as e:
            note(f"{where}: plagin '{pid}' tanilmadi ({e}) - o'tkazib yuborildi.")
            return None, None

    global_effects: list[HostEffect] = []
    if tl.color is not None:
        m, params = plugin(tl.color.plugin, tl.color.params, "Rang")
        if m is not None:
            eff = _color_effect(m.preset, m.backend, params)
            if eff is None:
                note(f"Rang: '{m.id}' host effektiga o'tmaydi.")
            else:
                global_effects.append(eff)

    starts = tl.item_starts()
    video: list[VideoClipItem] = []
    markers: list[Marker] = []
    for i, it in enumerate(tl.video):
        media = tl.media[it.media]
        dur_s = it.out_duration_ms / 1000
        where = f"{it.id}"
        motions: list[_Motion] = []
        effects = list(global_effects)
        for ref in it.fx:
            m, params = plugin(ref.plugin, ref.params, where)
            if m is None:
                continue
            a = min(max(0.0, ref.at_ms / 1000), dur_s)
            b = dur_s if ref.dur_ms is None else min(dur_s, a + ref.dur_ms / 1000)
            if m.kind == "motion":
                if m.preset == "shake":
                    note(f"{where}: silkinish (shake) harakati host'ga o'tmaydi - kerak bo'lsa "
                         "Premiere/AE'da qo'lda (Wiggle) qo'shing.")
                else:
                    motions.append(_Motion(m.preset, params, a, b))
            elif m.kind == "color":
                eff = _color_effect(m.preset, m.backend, params)
                if eff is None:
                    note(f"{where}: rang plagini '{m.id}' host effektiga o'tmaydi.")
                else:
                    effects.append(eff)
                    if a > 0 or b < dur_s:
                        note(f"{where}: rang effekti butun element bo'ylab qo'yildi "
                             "(Lahza'da faqat bir qismida edi).")
            elif m.backend == "speed":
                note(f"{where}: kadrni to'xtatish (freeze) host'ga o'tmaydi - Premiere'da "
                     "Frame Hold, AE'da Time Remap bilan qo'lda.")
            elif m.backend == "audio-graph":
                note(f"{where}: ovozning silliq kirishi/chiqishi host'ga o'tmaydi - audio "
                     "o'tishlari (Constant Power) bilan qo'lda.")
            else:
                note(f"{where}: plagin '{m.id}' host'ga o'tmaydi.")
        layers = _montage_layers(it, media, W, H, motions, dur_s)
        for layer in layers:
            layer.effects = layer.effects + [e.model_copy() for e in effects]
        trans = None
        if i > 0 and it.transition_in is not None:
            m, _ = plugin(it.transition_in.plugin, it.transition_in.params, where)
            dur = min(it.transition_in.dur_ms, it.out_duration_ms, tl.video[i - 1].out_duration_ms)
            if m is not None:
                kind, exact = map_transition(m.preset)
                if not exact:
                    note(f"{where}: '{m.id}' o'tishi host'da yo'q - eritish (Cross Dissolve) "
                         "bilan almashtirildi.")
                trans = HostTransition(kind=kind, dur_s=_r(dur / 1000) if kind != "cut" else 0.0,
                                       lahza_plugin=m.id)
            else:
                trans = HostTransition(kind="cross_dissolve", dur_s=_r(dur / 1000),
                                       lahza_plugin=it.transition_in.plugin)
        elif i > 0:
            trans = HostTransition(kind="cut")
        rec_in = starts[i] / 1000
        video.append(VideoClipItem(
            id=it.id, media=it.media, src_in=_r(it.src_in_ms / 1000), src_out=_r(it.src_out_ms / 1000),
            rec_in=_r(rec_in), rec_out=_r(rec_in + dur_s), speed=it.speed,
            volume_db=_r(it.volume_db + tl.audio.source_gain_db, 2), mute=it.mute, layers=layers,
            transition_in=trans, label=it.role,
        ))
        if it.role == "hook":
            markers.append(Marker(t=_r(rec_in), name="Hook", kind="hook", comment=it.reason[:200]))

    total_s = tl.duration_ms / 1000
    music = [MusicItem(media=mu.media, src_in=_r(mu.src_in_ms / 1000), rec_in=_r(mu.start_ms / 1000),
                       rec_out=_r((mu.end_ms if mu.end_ms is not None else tl.duration_ms) / 1000),
                       volume_db=mu.gain_db, duck=mu.duck, fade_in_s=_r(mu.fade_in_ms / 1000),
                       fade_out_s=_r(mu.fade_out_ms / 1000)) for mu in tl.music]

    style = tl.captions.style
    text: list[TextOverlay] = []
    animated = False
    for t in tl.text:
        text.append(TextOverlay(id=t.id, rec_in=_r(t.start_ms / 1000), rec_out=_r(t.end_ms / 1000),
                                text=display_text(t.text, style.orthography, style.script), kind=t.kind,
                                background=t.background, position=t.position))
        animated = animated or t.animation != "none"
    if animated:
        note("Matn animatsiyalari (fade/pop/slide_up) host'ga o'tmaydi - matn qatlamlari "
             "animatsiyasiz qo'yildi.")

    captions = Captions(style=style.model_dump(mode="json"))
    if tl.captions.enabled and tl.captions.words:
        words = sorted(tl.captions.words, key=lambda w: w.start_ms)
        end = max(w.end_ms for w in words) + 1
        ctl = Timeline(0, end)
        lines = caption_lines(map_words(clean_words(words, style), ctl), style, settings, W)
        srt, wj = write_caption_files(out_dir, slug(name or "montaj"),
                                      build_srt(words, ctl, style=style), lines, style)
        captions = Captions(srt_path=str(srt.resolve()), words_path=str(wj.resolve()), lines=lines,
                            style=style.model_dump(mode="json"))
    elif tl.captions.enabled:
        note("Subtitr yoqilgan, lekin montajda so'zlar yo'q - subtitr yaratilmadi.")

    if tl.brand.logo_path:
        note("Logotip host-rejaga kirmaydi - uni sekvensiyaga qo'lda qo'ying.")
    if tl.audio.loudnorm_lufs is not None:
        note(f"Ovoz balandligini normallash ({tl.audio.loudnorm_lufs:g} LUFS) - eksport "
             "sozlamalarida qo'lda.")

    return HostPlan(
        source="montage", source_id=montage_id,
        sequence=Sequence(name=name or "Lahza montaj", width=W, height=H, fps=fmt.fps,
                          audio_hz=fmt.audio_hz, duration_s=_r(total_s)),
        media=[HostMedia(id=m.id, path=str(Path(m.path).resolve()), width=m.width, height=m.height,
                         fps=m.fps, duration_s=_r(m.duration_ms / 1000), has_audio=m.has_audio)
               for m in tl.media.values()],
        video=video, music=music, captions=captions, text=text,
        markers=sorted(markers, key=lambda m: m.t), not_translated=notes,
    )


__all__: list[str] = ["plan_from_clip", "plan_from_montage", "crop_transform", "crop_keys_to_transform",
                      "fit_blur_layers", "layers_for_piece", "map_transition"]
