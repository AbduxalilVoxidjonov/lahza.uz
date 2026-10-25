"""Montaj renderi: `MontageTimeline` -> FFmpeg (ADR-0009/0011/0012/0013, docs/11 5, 10.2).

Ikki bosqich (uzun montaj va ko'p manbada bitta ulkan grafdan ishonchliroq):

1. **Element** - har `VideoItem` alohida ffmpeg chaqiruvida ish papkasidagi oraliq faylga
   (`seg_NNN.mkv`: chiqish o'lchami, fps, SAR=1, MJPEG intra + PCM stereo) render qilinadi:
   manba trim -> tezlik (setpts/atempo) -> fps -> reframe (crop / markaz / xira fon / reframe
   rejasi) -> harakat plaginlari (crop `t` ifodalari va `zoompan`, kadr doim manba ichida) ->
   freeze -> element rangi; audio: trim, tezlik, gain, fade, sukut (audio yo'q yoki mute).
2. **Yig'ish** - oraliq fayllar `xfade` (+ audio `acrossfade`) yoki concat (kesim) bilan
   ulanadi -> butun montaj rangi -> videodan keyingi oraliq (tpad) -> karta fonlari (drawbox)
   -> matn qatlami (bitta ASS: TextItem + subtitr) -> logotip -> audio: musiqa, ducking
   (sidechaincompress), loudnorm, fade -> enkoder (EncoderChoice, graph.py bilan bir xil).

Vaqt kadrlarga kvantlanadi: element boshi/oxiri `round(ms * fps / 1000)` - jami davomiylik
`report.tl.duration_ms` dan ko'pi bilan yarim kadr farq qiladi, audio va video uzunligi
bir xil (apad + atrim).

Xavfsizlik: foydalanuvchi yo'llari grafga kirmaydi (`-i` kirish; LUT/ASS/shriftlar ish papkasiga
nisbiy nom bilan), ffmpeg cwd = ish papkasi; har graf `fx.registry.check_graph` oq ro'yxatidan
o'tadi (GPL va fayl o'qiydigan filtrlar taqiqlangan).
"""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from lahza_engine.config import RenderConfig, Settings
from lahza_engine.fx.registry import FxError, FxManifest, check_graph, get_plugin, validate_params
from lahza_engine.media.tools import find_tool
from lahza_engine.montage.model import FxRef, MediaRef, MontageTimeline, VideoItem
from lahza_engine.montage.report import edl_path_for, write_edl
from lahza_engine.reframe.planner import crop_rect
from lahza_engine.render.capabilities import LibassMissing, has_filter
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.render.graph import (
    LOGO_WIDTH_PCT,
    RenderJob,
    build_graph,
    ffmpeg_major,
    logo_overlay_xy,
)
from lahza_engine.render.profiles import evaluate_timeline, profile_settings
from lahza_engine.stickers import overlay_stickers, sticker_inputs
from lahza_engine.subtitle.ass import build_montage_ass, build_srt
from lahza_engine.subtitle.fonts import default_fonts_dir, has_fonts
from lahza_engine.timeline import Timeline

log = logging.getLogger(__name__)

__all__ = ["MontageRenderResult", "render_montage", "render_montage_frame", "build_item_graph", "build_compose_graph", "AUTO_BLUR_RATIO"]

AUTO_BLUR_RATIO = 1.4
"""reframe=auto, detektorsiz: manba va chiqish nisbatlari shundan ko'p farq qilsa - xira fon."""
INTERMEDIATE_VIDEO = ("-c:v", "mjpeg", "-q:v", "2", "-pix_fmt", "yuvj420p")
INTERMEDIATE_AUDIO = ("-c:a", "pcm_s16le")
STAGE1_WEIGHT = 0.6
PREVIEW_SPAN_MS = 200
DUCK = "sidechaincompress=threshold=0.02:ratio=6:attack=20:release=350"
LOW_RES_RATIO = 0.6
"""Crop balandligi / zoom chiqish balandligining shu ulushidan kichik - sifat ogohlantirishi."""


@dataclass
class MontageRenderResult:
    video: Path
    edl: Path
    srt: Path | None = None
    warnings: list[str] = field(default_factory=list)


# --- Yordamchilar -------------------------------------------------------------------------------


def _fps_frac(fps: float) -> Fraction:
    return Fraction(fps).limit_denominator(1001)


def _fps_str(fps: float) -> str:
    f = _fps_frac(fps)
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def _frames(ms: float, fps: float) -> int:
    return round(ms * float(_fps_frac(fps)) / 1000)


def _f(x: float) -> str:
    """Ifoda uchun son (qisqa, nuqtali)."""
    return f"{x:.6f}".rstrip("0").rstrip(".") if x != int(x) else str(int(x))


def _hex(color: str | None, default: str = "000000") -> str:
    c = (color or "").lstrip("#")
    return c.upper() if len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c) else default


def _atempo(speed: float) -> list[str]:
    out, s = [], speed
    while s > 2.0:
        out.append("atempo=2")
        s /= 2.0
    while s < 0.5:
        out.append("atempo=0.5")
        s /= 0.5
    if abs(s - 1.0) > 1e-6:
        out.append(f"atempo={_f(round(s, 6))}")
    return out


@dataclass
class _Fx:
    ref: FxRef
    manifest: FxManifest
    params: dict
    a: float  # element boshidan, soniya (chiqish vaqti)
    b: float


def _resolve_fx(refs: list[FxRef], dur_s: float, warnings: list[str], where: str) -> list[_Fx]:
    out: list[_Fx] = []
    for ref in refs:
        try:
            m = get_plugin(ref.plugin)
            params = validate_params(m, ref.params)
        except (KeyError, FxError) as e:
            warnings.append(f"{where}: plagin o'tkazib yuborildi ({ref.plugin}): {e}")
            continue
        a = min(max(0.0, ref.at_ms / 1000), dur_s)
        b = dur_s if ref.dur_ms is None else min(dur_s, a + ref.dur_ms / 1000)
        out.append(_Fx(ref, m, params, a, b))
    return out


# --- Rang (color / lut backendlari) ----------------------------------------------------------


def color_filter(fx: _Fx, workdir: Path, lut_name: str) -> str:
    """Rang plagini -> filtr zanjiri (eq ishlatilmaydi - GPL). LUT ish papkasiga nusxalanadi."""
    if fx.manifest.backend == "lut":
        src = Path(str(fx.params.get("file") or "")).expanduser()
        if not src.is_file() or src.suffix.lower() != ".cube":
            raise FxError(f"LUT fayli topilmadi yoki .cube emas: {src.name or '-'}")
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, workdir / lut_name)
        return f"lut3d=file={lut_name}"
    k = float(fx.params.get("kuch", 1.0))
    p = fx.manifest.preset
    if p == "warm":
        return (f"colorbalance=rs={_f(.08 * k)}:bs={_f(-.08 * k)}:rm={_f(.05 * k)}"
                f":bm={_f(-.05 * k)}:rh={_f(.04 * k)}:bh={_f(-.04 * k)}")
    if p == "cool":
        return (f"colorbalance=rs={_f(-.07 * k)}:bs={_f(.08 * k)}:rm={_f(-.04 * k)}"
                f":bm={_f(.05 * k)}:rh={_f(-.03 * k)}:bh={_f(.04 * k)}")
    if p == "vivid":
        c = 0.04 * k
        return (f"hue=s={_f(1 + .35 * k)},"
                f"curves=master='0/0 0.25/{_f(.25 - c)} 0.75/{_f(.75 + c)} 1/1'")
    if p == "film":
        return (f"curves=master='0/{_f(.06 * k)} 0.5/0.5 1/{_f(1 - .05 * k)}',"
                f"colorbalance=rs={_f(-.03 * k)}:bs={_f(.04 * k)}:rh={_f(.04 * k)}:bh={_f(-.03 * k)},"
                f"hue=s={_f(1 - .15 * k)}")
    if p == "bw":
        c = 0.03 * k
        return f"hue=s={_f(1 - k)},curves=master='0/0 0.25/{_f(.25 - c)} 0.75/{_f(.75 + c)} 1/1'"
    raise FxError(f"noma'lum rang preseti: {p}")


# --- Harakat (motion-keys backendi) -------------------------------------------------------------


def _ease(name: str, p: str) -> str:
    if name == "ease-out":
        return f"(1-pow(1-{p},2))"
    if name == "expo-out":
        return f"(1-pow(2,-10*{p}))"
    return p


def _prog(t: str, a: float, b: float) -> str:
    return f"clip(({t}-{_f(a)})/{_f(max(b - a, 1e-3))},0,1)"


@dataclass
class _Camera:
    zoom: list[str] = field(default_factory=list)  # ko'paytuvchilar
    dx: list[str] = field(default_factory=list)  # -1..1 (zaxira ulushi)
    dy: list[str] = field(default_factory=list)
    crop_dx: list[str] = field(default_factory=list)  # manba zaxirasidagi pan (crop x)
    crop_dy: list[str] = field(default_factory=list)

    @property
    def needs_zoompan(self) -> bool:
        return bool(self.zoom or self.dx or self.dy)


def _camera(motions: list[_Fx], t: str, slack_x: bool, slack_y: bool) -> _Camera:
    cam = _Camera()
    for m in motions:
        p, a, b = m.params, m.a, m.b
        kind = m.manifest.preset
        if kind == "punch-in":
            z = float(p["zoom"])
            k = max(int(p["kirish_ms"]) / 1000, 1e-3)
            e = _ease(p["easing"], f"clip(({t}-{_f(a)})/{_f(k)},0,1)")
            cam.zoom.append(f"if(between({t},{_f(a)},{_f(b)}),1+{_f(z - 1)}*{e},1)")
        elif kind == "push-in":
            z = float(p["zoom"])
            cam.zoom.append(f"(1+{_f(z - 1)}*{_ease(p['easing'], _prog(t, a, b))})")
        elif kind == "zoom-out":
            z = float(p["zoom"])
            cam.zoom.append(f"({_f(z)}-{_f(z - 1)}*{_ease(p['easing'], _prog(t, a, b))})")
        elif kind == "pan":
            d = p["yonalish"]
            sign = -1 if d in ("chapga", "yuqoriga") else 1
            horiz = d in ("chapga", "onga")
            off = f"{_f(sign * float(p['kuch']))}*(2*{_ease(p['easing'], _prog(t, a, b))}-1)"
            if horiz and slack_x:
                cam.crop_dx.append(off)
            elif not horiz and slack_y:
                cam.crop_dy.append(off)
            else:
                cam.zoom.append(_f(float(p["zoom"])))
                (cam.dx if horiz else cam.dy).append(off)
        elif kind == "shake":
            s = float(p["kuch"])
            hz = float(p["chastota_hz"])
            cam.zoom.append(_f(1 + 0.06 * s))
            w = f"between({t},{_f(a)},{_f(b)})"
            cam.dx.append(f"{w}*0.8*(0.6*sin(2*PI*{_f(hz)}*{t})+0.4*sin(2*PI*{_f(hz * 1.7)}*{t}+1.3))")
            cam.dy.append(f"{w}*0.8*(0.6*sin(2*PI*{_f(hz * 0.9)}*{t}+2.1)+0.4*sin(2*PI*{_f(hz * 1.3)}*{t}))")
    return cam


def _zoompan(cam: _Camera, W: int, H: int, fps: str) -> str:
    z = "*".join(cam.zoom) or "1"
    dx = "+".join(cam.dx) or "0"
    dy = "+".join(cam.dy) or "0"
    return (f"zoompan=z='max(1,{z})':x='(iw-iw/zoom)/2*(1+clip({dx},-1,1))'"
            f":y='(ih-ih/zoom)/2*(1+clip({dy},-1,1))':d=1:s={W}x{H}:fps={fps}")


# --- Reframe ---------------------------------------------------------------------------------


def reframe_mode(item: VideoItem, media: MediaRef, W: int, H: int, detector=None) -> str:
    """"crop" | "fit_blur" | "plan" (detektor bo'yicha mavjud reframe rejasi)."""
    if item.crop is not None or item.reframe == "center":
        return "crop"
    if item.reframe == "fit_blur":
        return "fit_blur"
    src_ar = media.width / max(1, media.height)
    out_ar = W / H
    if detector is not None and src_ar > out_ar * 1.05:
        return "plan"
    if item.reframe == "focus":
        return "crop"
    ratio = max(src_ar / out_ar, out_ar / src_ar)
    return "fit_blur" if ratio > AUTO_BLUR_RATIO else "crop"


def _fit_blur(inp: str, out: str, W: int, H: int, tag: str) -> list[str]:
    return [
        f"[{inp}]split=2[bg{tag}][fg{tag}]",
        f"[bg{tag}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"gblur=sigma=30[bgb{tag}]",
        f"[fg{tag}]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2"
        f":flags=lanczos[fgs{tag}]",
        f"[bgb{tag}][fgs{tag}]overlay=(W-w)/2:(H-h)/2[{out}]",
    ]


@dataclass
class ItemGraph:
    chains: list[str]
    files: dict[str, str]
    seek_ms: int
    span_ms: int
    warnings: list[str] = field(default_factory=list)
    luts: list[str] = field(default_factory=list)


def build_item_graph(
    tl: MontageTimeline,
    item: VideoItem,
    workdir: Path,
    settings: Settings,
    *,
    n_frames: int | None,
    local_ms: float = 0.0,
    detector=None,
    with_audio: bool = True,
    vout: str = "v",
    aout: str = "a",
) -> ItemGraph:
    """Bitta element zanjiri (kirish 0 - manba fayl).

    n_frames: chiqish kadrlari soni (render); None - bitta kadrli preview (`local_ms` - element
    ichidagi chiqish vaqti; freeze `local_ms` ni o'zi hisobga oladi).
    """
    fmt = tl.format
    W, H, fps = fmt.w, fmt.h, _fps_str(fmt.fps)
    media = tl.media[item.media]
    dur_s = item.out_duration_ms / 1000
    warnings: list[str] = []
    fxs = _resolve_fx(item.fx, dur_s, warnings, item.id)
    motions = [x for x in fxs if x.manifest.kind == "motion"]
    freezes = [x for x in fxs if x.manifest.backend == "speed"]
    colors = [x for x in fxs if x.manifest.kind == "color"]
    fades = [x for x in fxs if x.manifest.backend == "audio-graph"]
    for fz in freezes:
        fz.b = min(dur_s, fz.a + int(fz.ref.dur_ms or fz.params["dur_ms"]) / 1000)

    # Preview: freeze ichida bo'lsa - to'xtatilgan kadr vaqti.
    t0 = local_ms / 1000
    if n_frames is None:
        for fz in freezes:
            if fz.a <= t0 < fz.b:
                t0 = fz.a
    src_a = item.src_in_ms + t0 * 1000 * item.speed
    src_b = item.src_out_ms
    if n_frames is None:
        src_b = min(src_b, src_a + max(PREVIEW_SPAN_MS, 2 * 1000 / fmt.fps) * item.speed)
        src_a = min(src_a, max(item.src_in_ms, src_b - 1000 / max(media.fps, 1)))
    seek = max(0, int(src_a) - 1000)
    # Boshlanish pastga yaxlitlanadi: `:.3f` yuqoriga yaxlitlasa (1.0007 -> 1.001) aynan shu paytdagi
    # kadr trim'dan tushib qoladi va oxirgi kadr preview'i bo'sh chiqadi (ffmpeg "Nothing was written").
    s, e = math.floor(src_a - seek) / 1000, (src_b - seek) / 1000
    t_var = f"(t+{_f(t0)})" if t0 else "t"
    zt_var = f"(it+{_f(t0)})" if t0 else "it"
    speed_pts = "PTS-STARTPTS" if item.speed == 1 else f"(PTS-STARTPTS)/{_f(item.speed)}"
    chains: list[str] = []
    files: dict[str, str] = {}

    mode = reframe_mode(item, media, W, H, detector)
    cur = "vb"
    if mode == "plan":
        from lahza_engine.core.export import build_layout_plan
        from lahza_engine.types import Clip

        clip = Clip(id=item.id, media_id=media.id, start_ms=int(src_a), end_ms=int(src_b),
                    start_sentence_id=0, end_sentence_id=0)
        tlx = Timeline(int(src_a), int(src_b))
        layouts = build_layout_plan(Path(media.path), clip, tlx, detector, settings, media.width,
                                    media.height, detect_scenes=n_frames is not None)
        job = RenderJob(src=Path(media.path), out=workdir / "unused.mp4", workdir=workdir,
                        src_w=media.width, src_h=media.height, fps=media.fps or 25.0,
                        timeline=tlx, layouts=layouts,
                        encoder=EncoderChoice("mjpeg", (), False),
                        cfg=RenderConfig(width=W, height=H), video_only=True)
        g, gfiles, gseek = build_graph(job)
        seek = round(gseek * 1000)
        files.update(gfiles)
        chains.extend(g.replace("[vout]", "[vplan]").split(";\n"))
        chains.append(f"[vplan]setpts={speed_pts},fps={fps},setsar=1[{cur}]")
        slack_x = slack_y = False
    else:
        chains.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts={speed_pts},fps={fps}[vt0]")
        if mode == "fit_blur":
            chains.extend(_fit_blur("vt0", cur, W, H, "0"))
            slack_x = slack_y = False
        else:
            cx, cy, zoom = (item.crop.cx, item.crop.cy, item.crop.zoom) if item.crop else (.5, .5, 1.)
            x, y, cw, ch = crop_rect(cx, media.width, media.height, W / H, zoom, cy)
            slack_x = media.width - cw >= 0.08 * cw
            slack_y = media.height - ch >= 0.08 * ch
            cam = _camera(motions, t_var, slack_x, slack_y)  # crop ifodalari: `t`
            zcam = _camera(motions, zt_var, slack_x, slack_y)  # zoompan ifodalari: `it`
            xe = (f"'clip({x}+{_f((media.width - cw) / 2)}*({'+'.join(cam.crop_dx)}),0,{media.width - cw})'"
                  if cam.crop_dx else str(x))
            ye = (f"'clip({y}+{_f((media.height - ch) / 2)}*({'+'.join(cam.crop_dy)}),0,{media.height - ch})'"
                  if cam.crop_dy else str(y))
            zmax = 1.0 + sum(float(m.params.get("zoom", 1.0)) - 1 for m in motions
                             if m.manifest.preset in ("punch-in", "push-in", "zoom-out"))
            if ch / max(zmax, 1.0) < H * LOW_RES_RATIO:
                warnings.append(
                    f"{item.id}: manba o'lchami past ({media.width}x{media.height}) - kesim/zoom "
                    "kadrni yumshoqroq qiladi")
            base = f"[vt0]crop={cw}:{ch}:{xe}:{ye}"
            if zcam.needs_zoompan:
                chains.append(base + "," + _zoompan(zcam, W, H, fps) + f",setsar=1[{cur}]")
            else:
                chains.append(base + f",scale={W}:{H}:flags=lanczos,setsar=1[{cur}]")
            motions = []  # crop rejimida harakat shu yerda qo'llandi
    if motions:
        cam = _camera(motions, zt_var, False, False)
        chains.append(f"[{cur}]{_zoompan(cam, W, H, fps)},setsar=1[vm]")
        cur = "vm"

    # Freeze: [a, b) oralig'ida a-kadr ushlab turiladi (element davomiyligi o'zgarmaydi, ovoz davom etadi).
    if n_frames is not None:
        for k, fz in enumerate(freezes):
            fa = min(_frames(fz.a * 1000, fmt.fps), n_frames - 1)
            fd = min(_frames((fz.b - fz.a) * 1000, fmt.fps), n_frames - fa)
            if fd <= 0:
                continue
            has_a, has_c = fa > 0, fa + fd < n_frames
            n_out = 1 + has_a + has_c
            chains.append(f"[{cur}]split={n_out}" + "".join(
                f"[fz{k}{x}]" for x, on in (("a", has_a), ("b", True), ("c", has_c)) if on))
            parts = []
            if has_a:
                chains.append(f"[fz{k}a]trim=end_frame={fa},setpts=PTS-STARTPTS[fp{k}a]")
                parts.append(f"[fp{k}a]")
            chains.append(f"[fz{k}b]trim=start_frame={fa}:end_frame={fa + 1},setpts=PTS-STARTPTS,"
                          f"zoompan=z=1:d={fd}:s={W}x{H}:fps={fps}[fp{k}b]")
            parts.append(f"[fp{k}b]")
            if has_c:
                chains.append(f"[fz{k}c]trim=start_frame={fa + fd},setpts=PTS-STARTPTS[fp{k}c]")
                parts.append(f"[fp{k}c]")
            chains.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0,fps={fps}[vf{k}]")
            cur = f"vf{k}"

    luts: list[str] = []
    for k, c in enumerate(colors):
        name = f"lut_item_{item.id}_{k}.cube".replace("/", "_")
        try:
            filt = color_filter(c, workdir, name)
        except FxError as err:
            warnings.append(f"{item.id}: {err}")
            continue
        if c.manifest.backend == "lut":
            luts.append(name)
        chains.append(f"[{cur}]{filt}[vc{k}]")
        cur = f"vc{k}"

    tail = f"[{cur}]setsar=1,format=yuv420p"
    if n_frames is not None:
        tail += f",tpad=stop_mode=clone:stop={n_frames},trim=end_frame={n_frames},setpts=PTS-STARTPTS"
    chains.append(tail + f"[{vout}]")

    if with_audio and n_frames is not None:
        hz = fmt.audio_hz
        samples = round(n_frames * hz / float(_fps_frac(fmt.fps)))
        if media.has_audio and not item.mute:
            vol = item.volume_db + tl.audio.source_gain_db
            ac = [f"[0:a]atrim=start={s:.3f}:end={e:.3f}", "asetpts=PTS-STARTPTS",
                  *_atempo(item.speed), f"aresample={hz}",
                  "aformat=sample_fmts=fltp:channel_layouts=stereo"]
            if abs(vol) > 1e-6:
                ac.append(f"volume={_f(round(vol, 3))}dB")
            total_s = n_frames / float(_fps_frac(fmt.fps))
            for fd_ in fades:
                fin, fout = fd_.params["in_ms"] / 1000, fd_.params["out_ms"] / 1000
                if fin > 0:
                    ac.append(f"afade=t=in:st={_f(fd_.a)}:d={_f(fin)}")
                if fout > 0:
                    ac.append(f"afade=t=out:st={_f(max(0.0, min(fd_.b, total_s) - fout))}:d={_f(fout)}")
            ac += [f"apad=whole_len={samples}", f"atrim=end_sample={samples}"]
            chains.append(",".join(ac) + f"[{aout}]")
        else:
            chains.append(f"anullsrc=r={hz}:cl=stereo,atrim=end_sample={samples}[{aout}]")

    span = int(src_b - seek) + 500
    return ItemGraph(chains, files, seek, span, warnings, luts)


# --- Yig'ish grafi ------------------------------------------------------------------------------


@dataclass
class _Seg:
    item: VideoItem
    start_f: int  # video trek ichida (intro siljishisiz)
    end_f: int
    n_frames: int  # oraliq faylda (keyingi kesim ustma-ustligi olib tashlangan)
    xfade: str | None  # oldingi element bilan o'tish (None - kesim/concat)
    overlap_f: int


def plan_segments(tl: MontageTimeline) -> list[_Seg]:
    fps = tl.format.fps
    starts = tl.item_starts()
    segs: list[_Seg] = []
    for i, (it, st) in enumerate(zip(tl.video, starts, strict=True)):
        a, b = _frames(st, fps), _frames(st + it.out_duration_ms, fps)
        b = max(b, a + 1)
        xf, ov = None, 0
        if i > 0:
            ov = max(0, segs[-1].end_f - a)
            if it.transition_in is not None and ov > 0:
                try:
                    m = get_plugin(it.transition_in.plugin)
                    xf = None if m.preset == "cut" else m.preset
                except KeyError:
                    xf = "fade"
            if xf is None:
                ov = 0
        segs.append(_Seg(it, a, b, b - a, xf, ov))
    # Kesim: oldingi element keyingisining boshida tugaydi (model ustma-ust hisoblagan bo'lsa ham).
    for i in range(1, len(segs)):
        if segs[i].xfade is None:
            prev = segs[i - 1]
            prev.n_frames = max(1, segs[i].start_f - prev.start_f)
            prev.end_f = prev.start_f + prev.n_frames
        else:
            ov = min(segs[i].overlap_f, segs[i - 1].n_frames - 1, segs[i].n_frames - 1)
            segs[i].overlap_f = max(1, ov)
    return segs


def _text_needed(tl: MontageTimeline) -> bool:
    return bool(tl.text) or (tl.captions.enabled and bool(tl.captions.words))


def _ass_doc(tl: MontageTimeline, settings: Settings, offset_ms: int = 0) -> str:
    settings = profile_settings(settings, tl.target_platform)
    words = tl.captions.words if tl.captions.enabled else []
    return build_montage_ass(tl.text, words, tl.captions.style, settings.safe_zone, tl.format.w,
                             tl.format.h, offset_ms=offset_ms)


def _cards_drawbox(tl: MontageTimeline, at_ms: int | None = None) -> list[str]:
    out = []
    for c in tl.text:
        if c.kind != "card" or not c.background:
            continue
        col = f"0x{_hex(c.background, '111111')}@1"
        if at_ms is None:
            en = f":enable='gte(t,{_f(c.start_ms / 1000)})*lt(t,{_f(c.end_ms / 1000)})'"
        elif c.start_ms <= at_ms < c.end_ms:
            en = ""
        else:
            continue
        out.append(f"drawbox=x=0:y=0:w=iw:h=ih:color={col}:t=fill{en}")
    return out


def _overlay_chain(tl: MontageTimeline, settings: Settings, cur: str, *, ass: bool,
                   fonts: bool, logo_idx: int | None, at_ms: int | None,
                   sticker_indices: list[int] | None = None) -> tuple[list[str], str]:
    settings = profile_settings(settings, tl.target_platform)
    W, H = tl.format.w, tl.format.h
    chains: list[str] = []
    filters = _cards_drawbox(tl, at_ms)
    if ass:
        filters.append("ass=text.ass" + (":fontsdir=fonts" if fonts else ""))
    if filters:
        chains.append(f"[{cur}]" + ",".join(filters) + "[vtx]")
        cur = "vtx"
    if logo_idx is not None:
        lx, ly = logo_overlay_xy(tl.brand.logo_position, settings.safe_zone, W, H)
        lw = int(W * LOGO_WIDTH_PCT) // 2 * 2
        op = max(0.0, min(1.0, tl.brand.logo_opacity))
        chains.append(f"[{logo_idx}:v]scale={lw}:-1,format=rgba,colorchannelmixer=aa={op:.3f}[logo]")
        chains.append(f"[{cur}][logo]overlay=x={lx}:y={ly}:eof_action=repeat:format=auto[vlg]")
        cur = "vlg"
    if sticker_indices:
        overlays, cur = overlay_stickers(tl, cur, sticker_indices, at_ms)
        chains.extend(overlays)
    return chains, cur


def build_compose_graph(
    tl: MontageTimeline,
    segs: list[_Seg],
    settings: Settings,
    *,
    ass: bool,
    fonts: bool,
    color: str | None,
    music_inputs: list[int],
    logo_idx: int | None,
    sticker_indices: list[int] | None = None,
) -> str:
    """Oraliq fayllar (kirish 0..n-1) -> yakuniy [vout]/[aout]."""
    fmt = tl.format
    W, H, fps = fmt.w, fmt.h, _fps_str(fmt.fps)
    fr = float(_fps_frac(fmt.fps))
    hz = fmt.audio_hz
    total_ms = tl.duration_ms
    total_f = max(1, _frames(total_ms, fmt.fps))
    total_samples = round(total_f * hz / fr)
    chains: list[str] = []

    if segs:
        runs: list[list[int]] = []
        for i, sg in enumerate(segs):
            if i == 0 or sg.xfade is not None:
                runs.append([i])
            else:
                runs[-1].append(i)
        run_lbl: list[tuple[str, str]] = []
        for r, run in enumerate(runs):
            if len(run) == 1:
                i = run[0]
                chains.append(f"[{i}:v]fps={fps},setsar=1,format=yuv420p[rv{r}]")
                chains.append(f"[{i}:a]anull[ra{r}]")
            else:
                ins = "".join(f"[{i}:v][{i}:a]" for i in run)
                chains.append(f"{ins}concat=n={len(run)}:v=1:a=1[rvc{r}][ra{r}]")
                chains.append(f"[rvc{r}]fps={fps},setsar=1,format=yuv420p[rv{r}]")
            run_lbl.append((f"rv{r}", f"ra{r}"))
        accv, acca = run_lbl[0]
        for r in range(1, len(runs)):
            sg = segs[runs[r][0]]
            d = sg.overlap_f / fr
            off = sg.start_f / fr
            chains.append(f"[{accv}][{run_lbl[r][0]}]xfade=transition={sg.xfade}:duration={d:.6f}"
                          f":offset={off:.6f}[xv{r}]")
            chains.append(f"[{acca}][{run_lbl[r][1]}]acrossfade=d={d:.6f}:c1=tri:c2=tri[xa{r}]")
            accv, acca = f"xv{r}", f"xa{r}"
        video_f = segs[-1].end_f
        cur = accv
        if color:
            chains.append(f"[{cur}]{color}[vcol]")
            cur = "vcol"
        # Videodan keyingi oraliq (masalan, outro karta) - qora; karta foni keyin chiziladi.
        tail_f = max(0, total_f - video_f) + 2
        chains.append(f"[{cur}]tpad=stop={tail_f}:color=black,trim=end_frame={total_f},"
                      "setpts=PTS-STARTPTS[vp]")
        cur = "vp"
        chains.append(f"[{acca}]apad=whole_len={total_samples},"
                      f"atrim=end_sample={total_samples}[src]")
    else:
        chains.append(f"color=c=black:s={W}x{H}:r={fps}:d={total_f / fr:.6f},format=yuv420p[vp]")
        chains.append(f"anullsrc=r={hz}:cl=stereo,atrim=end_sample={total_samples}[src]")
        cur = "vp"

    ov, cur = _overlay_chain(tl, settings, cur, ass=ass, fonts=fonts, logo_idx=logo_idx, at_ms=None,
                             sticker_indices=sticker_indices)
    chains += ov
    chains.append(f"[{cur}]format=yuv420p[vout]")

    # --- audio: musiqa + ducking + loudnorm + fade ---
    ducked, plain = [], []
    for j, (mu, idx) in enumerate(zip(tl.music, music_inputs, strict=True)):
        end = mu.end_ms if mu.end_ms is not None else total_ms
        dur = max(0, min(end, total_ms) - mu.start_ms)
        if dur <= 0:
            continue
        ds = dur / 1000
        ch = [f"[{idx}:a]atrim=end={ds:.3f}", "asetpts=PTS-STARTPTS", f"aresample={hz}",
              "aformat=sample_fmts=fltp:channel_layouts=stereo", f"volume={_f(mu.gain_db)}dB"]
        if mu.fade_in_ms > 0:
            ch.append(f"afade=t=in:d={_f(min(mu.fade_in_ms / 1000, ds))}")
        if mu.fade_out_ms > 0:
            fo = min(mu.fade_out_ms / 1000, ds)
            ch.append(f"afade=t=out:st={_f(max(0.0, ds - fo))}:d={_f(fo)}")
        if mu.start_ms > 0:
            ch.append(f"adelay=delays={mu.start_ms}:all=1")
        ch += [f"apad=whole_len={total_samples}", f"atrim=end_sample={total_samples}"]
        chains.append(",".join(ch) + f"[mu{j}]")
        (ducked if mu.duck else plain).append(f"[mu{j}]")
    mix = ["[src]"]
    if ducked:
        chains.append("[src]asplit=2[srcm][srcsc]")
        mix = ["[srcm]"]
        if len(ducked) > 1:
            chains.append("".join(ducked) + f"amix=inputs={len(ducked)}:normalize=0:duration=first[mud]")
            dk = "[mud]"
        else:
            dk = ducked[0]
        chains.append(f"{dk}[srcsc]{DUCK}[muk]")
        mix.append("[muk]")
    mix += plain
    afx: list[str] = []
    if len(mix) > 1:
        chains.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first[amx]")
        cur_a = "amx"
    else:
        cur_a = "src"
    if tl.audio.loudnorm_lufs is not None:
        afx.append(f"loudnorm=I={tl.audio.loudnorm_lufs:g}:TP=-1.5:LRA=11")
    afx.append(f"aresample={hz}")
    fade = tl.audio.fade_ms / 1000
    total_s = total_samples / hz
    if fade > 0:
        afx.append(f"afade=t=in:d={fade:.3f}")
        afx.append(f"afade=t=out:st={max(0.0, total_s - fade):.3f}:d={fade:.3f}")
    afx += [f"apad=whole_len={total_samples}", f"atrim=end_sample={total_samples}"]
    chains.append(f"[{cur_a}]" + ",".join(afx) + "[aout]")
    return ";\n".join(chains)


# --- Ishga tushirish ----------------------------------------------------------------------------


def _graph_opt(ffmpeg: str) -> list[str]:
    return ["-/filter_complex", "graph.txt"] if ffmpeg_major(ffmpeg) >= 7 else [
        "-filter_complex_script", "graph.txt"]


def _write_graph(cwd: Path, graph: str, files: dict[str, str]) -> None:
    check_graph(graph)
    cwd.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (cwd / name).write_text(text, encoding="utf-8")
    (cwd / "graph.txt").write_text(graph, encoding="utf-8")


def _run_ffmpeg(cmd: list[str], cwd: Path, total_s: float, on_tick: Callable[[float], None] | None,
                cancel: threading.Event | None) -> None:
    from lahza_engine.core.runner import Cancelled

    if cancel is not None and cancel.is_set():
        raise Cancelled()
    logf = cwd / "ffmpeg.log"
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    with open(logf, "w", encoding="utf-8") as err:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=err, text=True,
                             encoding="utf-8", errors="replace", **kwargs)
        killed = threading.Event()

        def watch() -> None:
            while p.poll() is None:
                if cancel is not None and cancel.wait(0.2):
                    killed.set()
                    p.kill()
                    return
                if cancel is None:
                    return

        w = threading.Thread(target=watch, daemon=True)
        w.start()
        try:
            assert p.stdout is not None
            for line in p.stdout:
                if on_tick and line.startswith("out_time_us=") and total_s > 0:
                    try:
                        us = int(line.split("=", 1)[1])
                    except ValueError:
                        continue
                    on_tick(min(1.0, max(0.0, us / 1e6 / total_s)))
            rc = p.wait()
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    if killed.is_set() or (cancel is not None and cancel.is_set()):
        raise Cancelled()
    if rc != 0:
        tail = logf.read_text(encoding="utf-8", errors="replace").strip()[-800:]
        raise RuntimeError(f"montaj render xatosi (ffmpeg {rc}): {tail}")


def _copy_fonts(cwd: Path) -> bool:
    d = default_fonts_dir()
    if not has_fonts(d):
        return False
    link = cwd / "fonts"
    if not link.exists():
        shutil.copytree(d, link)
    return True


def _logo(tl: MontageTimeline, warnings: list[str]) -> Path | None:
    if not tl.brand.logo_path:
        return None
    p = Path(tl.brand.logo_path).expanduser()
    if not p.is_file():
        warnings.append(f"Logotip fayli topilmadi ({p.name}) - logotipsiz render qilindi")
        return None
    return p


def _global_color(tl: MontageTimeline, workdir: Path, warnings: list[str]) -> str | None:
    if tl.color is None:
        return None
    fx = _resolve_fx([tl.color], 0.0, warnings, "rang")
    if not fx:
        return None
    if fx[0].manifest.kind != "color":
        warnings.append(f"rang: {tl.color.plugin} rang plagini emas - o'tkazib yuborildi")
        return None
    return color_filter(fx[0], workdir, "lut0.cube")


def render_montage(
    tl: MontageTimeline,
    out: Path,
    workdir: Path,
    encoder: EncoderChoice,
    settings: Settings,
    *,
    detector=None,
    allow_no_subs: bool = False,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> MontageRenderResult:
    """Montajni render qiladi: video + `<nom>_edl.json` (+ SRT, subtitr bo'lsa).

    libass yo'q va matn/subtitr bor: allow_no_subs=False -> LibassMissing; True -> matnsiz,
    ogohlantirish bilan. Bekor qilish: `cancel` o'rnatilsa ffmpeg o'ldiriladi, `Cancelled`.
    """
    evaluation = evaluate_timeline(tl, settings)
    if evaluation.errors:
        raise ValueError("; ".join(evaluation.errors))
    settings = profile_settings(settings, tl.target_platform)
    ffmpeg = str(find_tool("ffmpeg"))
    out = Path(out)
    workdir = Path(workdir)
    warnings: list[str] = list(evaluation.warnings)
    use_ass = _text_needed(tl)
    if use_ass and not has_filter(ffmpeg, "ass"):
        if not allow_no_subs:
            raise LibassMissing()
        use_ass = False
        warnings.append("Matn va subtitr videoga chizilmadi: FFmpeg libass'siz."
                        + (" SRT fayli tayyor." if tl.captions.enabled and tl.captions.words else ""))
    # Reject invalid stickers before any expensive segment rendering.
    sticker_args: list[str] = []
    relative_sticker_indices = sticker_inputs(tl, sticker_args)
    workdir.mkdir(parents=True, exist_ok=True)
    fmt = tl.format
    fr = float(_fps_frac(fmt.fps))
    segs = plan_segments(tl)
    total_frames = sum(s.n_frames for s in segs) or 1
    done_frames = 0

    def tick(base: float, span: float) -> Callable[[float], None]:
        def f(x: float) -> None:
            if on_progress:
                on_progress(min(1.0, base + span * x))
        return f

    # 1-bosqich: elementlar.
    seg_files: list[Path] = []
    for i, sg in enumerate(segs):
        cwd = workdir / f"item_{i:03d}"
        ig = build_item_graph(tl, sg.item, cwd, settings, n_frames=sg.n_frames, detector=detector)
        warnings += ig.warnings
        _write_graph(cwd, ";\n".join(ig.chains), ig.files)
        dst = workdir / f"seg_{i:03d}.mkv"
        media = tl.media[sg.item.media]
        cmd = [ffmpeg, "-y", "-hide_banner", "-v", "error", "-nostats", "-progress", "pipe:1",
               "-ss", f"{ig.seek_ms / 1000:.3f}", "-t", f"{ig.span_ms / 1000:.3f}",
               "-i", str(Path(media.path).resolve()), *_graph_opt(ffmpeg),
               "-map", "[v]", "-map", "[a]", *INTERMEDIATE_VIDEO, *INTERMEDIATE_AUDIO,
               "-ar", str(fmt.audio_hz), str(dst.resolve())]
        base = STAGE1_WEIGHT * done_frames / total_frames
        _run_ffmpeg(cmd, cwd, sg.n_frames / fr, tick(base, STAGE1_WEIGHT * sg.n_frames / total_frames),
                    cancel)
        done_frames += sg.n_frames
        seg_files.append(dst)

    # 2-bosqich: yig'ish.
    color = _global_color(tl, workdir, warnings)
    inputs: list[str] = []
    for f in seg_files:
        inputs += ["-i", str(f.resolve())]
    music_idx: list[int] = []
    for mu in tl.music:
        music_idx.append(len(inputs) // 2)
        m = tl.media[mu.media]
        if mu.src_in_ms > 0:
            inputs += ["-ss", f"{mu.src_in_ms / 1000:.3f}"]
        inputs += ["-i", str(Path(m.path).resolve())]
    logo = _logo(tl, warnings)
    logo_idx = None
    if logo is not None:
        logo_idx = sum(1 for x in inputs if x == "-i")
        inputs += ["-i", str(logo.resolve())]
    input_count = sum(x == "-i" for x in inputs)
    sticker_indices = [input_count + i for i in relative_sticker_indices]
    inputs.extend(sticker_args)
    files: dict[str, str] = {}
    fonts = False
    if use_ass:
        files["text.ass"] = _ass_doc(tl, settings)
        fonts = _copy_fonts(workdir)
    graph = build_compose_graph(tl, segs, settings, ass=use_ass, fonts=fonts, color=color,
                                music_inputs=music_idx, logo_idx=logo_idx,
                                sticker_indices=sticker_indices)
    _write_graph(workdir, graph, files)
    out.parent.mkdir(parents=True, exist_ok=True)
    total_s = tl.duration_ms / 1000
    cmd = [ffmpeg, "-y", "-hide_banner", "-v", "error", "-nostats", "-progress", "pipe:1",
           *inputs, *_graph_opt(ffmpeg), "-map", "[vout]", "-map", "[aout]", *encoder.args,
           "-r", _fps_str(fmt.fps),
           "-c:a", "aac", "-b:a", f"{settings.render.audio_bitrate_kbps}k", "-ac", "2",
           "-ar", str(fmt.audio_hz), "-movflags", "+faststart", str(out.resolve())]
    _run_ffmpeg(cmd, workdir, total_s, tick(STAGE1_WEIGHT, 1 - STAGE1_WEIGHT), cancel)

    srt: Path | None = None
    if tl.captions.enabled and tl.captions.words:
        end = max(w.end_ms for w in tl.captions.words) + 1000
        srt = out.with_suffix(".srt")
        srt.write_text(build_srt(tl.captions.words, Timeline(0, end), style=tl.captions.style),
                       encoding="utf-8")
    edl = write_edl(tl, edl_path_for(out), extra={
        "video": out.name, "encoder": encoder.name, "warnings": warnings,
        "text_drawn": use_ass, "srt": srt.name if srt else None})
    if on_progress:
        on_progress(1.0)
    shutil.rmtree(workdir, ignore_errors=True)
    return MontageRenderResult(out, edl, srt, warnings)


def _item_at(tl: MontageTimeline, rel_ms: int) -> tuple[int, int] | None:
    """(element indeksi, element ichidagi vaqt) - o'tish o'rtasidan keyin keyingi element."""
    starts = tl.item_starts()
    found: list[int] = [i for i, (it, st) in enumerate(zip(tl.video, starts, strict=True))
                        if st <= rel_ms < st + it.out_duration_ms]
    if not found:
        return None
    i = found[-1]
    if len(found) > 1:
        prev = found[-2]
        ov_end = starts[prev] + tl.video[prev].out_duration_ms
        if rel_ms < (starts[i] + ov_end) / 2:
            i = prev
    return i, rel_ms - starts[i]


def render_montage_frame(
    tl: MontageTimeline, t_ms: int, out_jpg: Path, settings: Settings, *, detector=None,
) -> Path:
    """Montajning t_ms paytidagi bitta JPG kadri (element zanjiri + rang + karta + matn + logo).

    libass yo'q bo'lsa matn/subtitrsiz - xato bermaydi.
    """
    ffmpeg = str(find_tool("ffmpeg"))
    fmt = tl.format
    W, H, fps = fmt.w, fmt.h, _fps_str(fmt.fps)
    total = max(1, tl.duration_ms)
    t = max(0, min(total - 1, int(t_ms)))
    out_jpg = Path(out_jpg)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lahza-mpreview-") as tmp:
        cwd = Path(tmp)
        hit = _item_at(tl, t) if tl.video else None
        inputs: list[str] = []
        files: dict[str, str] = {}
        if hit is not None:
            idx, local = hit
            item = tl.video[idx]
            ig = build_item_graph(tl, item, cwd, settings, n_frames=None, local_ms=local,
                                  detector=detector, with_audio=False, vout="vb0")
            chains = list(ig.chains)
            files.update(ig.files)
            inputs += ["-ss", f"{ig.seek_ms / 1000:.3f}", "-t", f"{ig.span_ms / 1000:.3f}",
                       "-i", str(Path(tl.media[item.media].path).resolve())]
            cur = "vb0"
            try:
                color = _global_color(tl, cwd, warnings)
            except FxError as e:
                log.warning("preview rang: %s", e)
                color = None
            if color:
                chains.append(f"[{cur}]{color}[vcol]")
                cur = "vcol"
        else:
            chains = [f"color=c=black:s={W}x{H}:r={fps}:d=0.2,format=yuv420p[vb0]"]
            cur = "vb0"
        use_ass = _text_needed(tl) and has_filter(ffmpeg, "ass")
        fonts = False
        if use_ass:
            files["text.ass"] = _ass_doc(tl, settings, offset_ms=t)
            fonts = _copy_fonts(cwd)
        logo = _logo(tl, warnings)
        logo_idx = None
        if logo is not None:
            logo_idx = sum(1 for x in inputs if x == "-i")
            inputs += ["-i", str(logo.resolve())]
        sticker_indices = sticker_inputs(tl, inputs)
        ov, cur = _overlay_chain(tl, settings, cur, ass=use_ass, fonts=fonts, logo_idx=logo_idx,
                                 at_ms=t, sticker_indices=sticker_indices)
        chains += ov
        chains.append(f"[{cur}]format=yuv420p[vout]")
        _write_graph(cwd, ";\n".join(chains), files)
        cmd = [ffmpeg, "-y", "-hide_banner", "-v", "error", *inputs, *_graph_opt(ffmpeg),
               "-map", "[vout]", "-frames:v", "1", "-q:v", "3", "-update", "1",
               str(out_jpg.resolve())]
        _run_ffmpeg(cmd, cwd, 0, None, None)
    return out_jpg
