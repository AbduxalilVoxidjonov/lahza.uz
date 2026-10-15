"""Bitta klip uchun FFmpeg render grafi (TZ 10-bo'lim, ADR-0009).

trim (aniq) -> layout (crop/split/xira fon) -> concat -> ASS subtitr -> logotip -> audio
loudnorm/fade -> enkoder.

* Dinamik kamera: `sendcmd` + `crop` filtri buyruqlari (x, y) - har bo'lak uchun alohida fayl.
* Barcha yordamchi fayllar (graph.txt, *.cmd, subs.ass) ish papkasida; ffmpeg shu papkada
  (cwd) ishga tushiriladi va fayllarga qisqa nom bilan murojaat qiladi - Windows yo'llaridagi
  ':' va '\\' ni filtergraph ichida ekranlash muammosi yo'q.
* Kirishda -ss bilan tez qidiruv; trim vaqtlari shu nuqtaga nisbatan.
* Logotip grafga fayl yo'li sifatida emas (`movie` filtri emas), qo'shimcha `-i` kirish (1:v)
  sifatida beriladi.
* libass yo'q yig'mada (`ass` filtri yo'q) render LibassMissing beradi yoki allow_no_subs=True
  bo'lsa subtitrsiz chiziladi (preview).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from lahza_engine.config import RenderConfig, SubtitleSafeZone
from lahza_engine.media.tools import find_tool, run
from lahza_engine.reframe.planner import CropKey, LayoutSegment, crop_rect
from lahza_engine.render.capabilities import LibassMissing, has_filter
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.timeline import Timeline
from lahza_engine.types import Layout

SPLIT_HALF_ASPECT = 1080 / 960
LOGO_WIDTH_PCT = 0.18
"""Logotip eni - chiqish kadri enining ulushi."""
LOGO_POSITIONS = ("top_left", "top_right", "bottom_left", "bottom_right")


@dataclass
class Piece:
    src_start_ms: int
    src_end_ms: int
    out_start_ms: int
    out_end_ms: int
    layout: LayoutSegment


@dataclass
class RenderJob:
    src: Path
    out: Path
    workdir: Path
    src_w: int
    src_h: int
    fps: float
    timeline: Timeline
    layouts: list[LayoutSegment]
    encoder: EncoderChoice
    cfg: RenderConfig = field(default_factory=RenderConfig)
    ass_text: str | None = None
    fonts_dir: Path | None = None
    logo: Path | None = None
    logo_position: str = "top_right"
    logo_opacity: float = 0.8
    safe_zone: SubtitleSafeZone = field(default_factory=SubtitleSafeZone)
    video_only: bool = False  # bitta kadrli preview: audio zanjiri qurilmaydi


def split_pieces(timeline: Timeline, layouts: list[LayoutSegment]) -> list[Piece]:
    pieces: list[Piece] = []
    for seg in timeline.segments:
        o0, o1 = seg.out_start_ms, seg.out_start_ms + seg.duration_ms
        for lay in layouts:
            a, b = max(o0, lay.start_ms), min(o1, lay.end_ms)
            if b - a < 1:
                continue
            pieces.append(
                Piece(
                    src_start_ms=seg.src_start_ms + (a - o0),
                    src_end_ms=seg.src_start_ms + (b - o0),
                    out_start_ms=a,
                    out_end_ms=b,
                    layout=lay,
                )
            )
    return pieces


def _keys_for_piece(keys: list[CropKey], piece: Piece) -> list[CropKey]:
    """Layout segmenti vaqtidagi kalitlarni bo'lak boshiga nisbatan qayta hisoblaydi."""
    offset = piece.out_start_ms - piece.layout.start_ms
    length = piece.out_end_ms - piece.out_start_ms
    if not keys:
        return [CropKey(0, 0.5, cut=True)]
    before = [k for k in keys if k.t_ms <= offset]
    first = before[-1] if before else keys[0]
    out = [CropKey(0, first.cx, first.cy, first.zoom, cut=True)]
    for k in keys:
        rel = k.t_ms - offset
        if 0 < rel < length:
            out.append(CropKey(rel, k.cx, k.cy, k.zoom, k.cut))
    return out


def densify(keys: list[CropKey], step_ms: int) -> list[CropKey]:
    """Kesim bo'lmagan qo'shni kalitlar orasini chiziqli interpolyatsiya (kadr qadamida)."""
    if len(keys) < 2:
        return keys
    out = [keys[0]]
    for prev, nxt in zip(keys, keys[1:], strict=False):
        if not nxt.cut and nxt.t_ms - prev.t_ms > step_ms:
            t = prev.t_ms + step_ms
            while t < nxt.t_ms:
                r = (t - prev.t_ms) / (nxt.t_ms - prev.t_ms)
                out.append(CropKey(t, prev.cx + (nxt.cx - prev.cx) * r,
                                   prev.cy + (nxt.cy - prev.cy) * r, prev.zoom))
                t += step_ms
        out.append(nxt)
    return out


def _cmd_file(target: str, keys: list[CropKey], src_w: int, src_h: int, aspect: float) -> str:
    """Bo'lak ichida crop o'lchami doimiy (birinchi kalit zoom'i), faqat x/y o'zgaradi."""
    lines = []
    last: tuple[int, int] | None = None
    zoom = keys[0].zoom if keys else 1.0
    for k in keys:
        x, y, _, _ = crop_rect(k.cx, src_w, src_h, aspect, zoom, k.cy)
        if (x, y) == last:
            continue
        lines.append(f"{k.t_ms / 1000:.3f} {target} x {x}, {target} y {y};")
        last = (x, y)
    return "\n".join(lines) + "\n"


def logo_overlay_xy(position: str, zone: SubtitleSafeZone, out_w: int, out_h: int) -> tuple[str, str]:
    """overlay filtri uchun x/y ifodalari - Instagram interfeysi zonasidan tashqarida."""
    if position not in LOGO_POSITIONS:
        raise ValueError(f"noma'lum logotip joyi: {position}")
    mx = int(out_w * zone.side_pct)
    top = int(out_h * zone.top_pct)
    bottom = int(out_h * zone.bottom_pct)
    x = str(mx) if position.endswith("left") else f"W-w-{mx}"
    y = str(top) if position.startswith("top") else f"H-h-{bottom}"
    return x, y


def build_graph(job: RenderJob) -> tuple[str, dict[str, str], float]:
    """(filtergraph matni, {fayl_nomi: matn}, input -ss soniyalarda)."""
    pieces = split_pieces(job.timeline, job.layouts)
    if not pieces:
        raise ValueError("render uchun bo'lak yo'q")
    seek_ms = max(0, min(p.src_start_ms for p in pieces) - 1000)
    W, H = job.cfg.width, job.cfg.height
    step_ms = max(10, int(1000 / job.fps)) if job.fps > 0 else 33
    files: dict[str, str] = {}
    chains: list[str] = []
    concat_in = []

    for i, p in enumerate(pieces):
        s = (p.src_start_ms - seek_ms) / 1000
        e = (p.src_end_ms - seek_ms) / 1000
        v = f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS"
        a = f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]"
        lay = p.layout.layout
        if lay in (Layout.FOCUS, Layout.MANUAL):
            keys = densify(_keys_for_piece(p.layout.keys, p), step_ms)
            x, y, w, h = crop_rect(keys[0].cx, job.src_w, job.src_h, W / H, keys[0].zoom,
                                   keys[0].cy)
            files[f"p{i}.cmd"] = _cmd_file(f"crop@c{i}", keys, job.src_w, job.src_h, W / H)
            v += (
                f",sendcmd=f=p{i}.cmd,crop@c{i}=w={w}:h={h}:x={x}:y={y}"
                f",scale={W}:{H}:flags=lanczos,setsar=1,format=yuv420p[v{i}]"
            )
            chains.append(v)
        elif lay is Layout.SPLIT:
            half = H // 2
            ka = densify(_keys_for_piece(p.layout.keys, p), step_ms)
            kb = densify(_keys_for_piece(p.layout.keys_b or p.layout.keys, p), step_ms)
            xa, ya, wa, ha = crop_rect(ka[0].cx, job.src_w, job.src_h, SPLIT_HALF_ASPECT,
                                       ka[0].zoom, ka[0].cy)
            xb, yb, wb, hb = crop_rect(kb[0].cx, job.src_w, job.src_h, SPLIT_HALF_ASPECT,
                                       kb[0].zoom, kb[0].cy)
            files[f"p{i}a.cmd"] = _cmd_file(f"crop@a{i}", ka, job.src_w, job.src_h, SPLIT_HALF_ASPECT)
            files[f"p{i}b.cmd"] = _cmd_file(f"crop@b{i}", kb, job.src_w, job.src_h, SPLIT_HALF_ASPECT)
            chains.append(v + f",split=2[sa{i}][sb{i}]")
            chains.append(
                f"[sa{i}]sendcmd=f=p{i}a.cmd,crop@a{i}=w={wa}:h={ha}:x={xa}:y={ya},"
                f"scale={W}:{half}:flags=lanczos[ta{i}]"
            )
            chains.append(
                f"[sb{i}]sendcmd=f=p{i}b.cmd,crop@b{i}=w={wb}:h={hb}:x={xb}:y={yb},"
                f"scale={W}:{H - half}:flags=lanczos[tb{i}]"
            )
            chains.append(f"[ta{i}][tb{i}]vstack=inputs=2,setsar=1,format=yuv420p[v{i}]")
        else:  # FIT_BLUR
            chains.append(v + f",split=2[bg{i}][fg{i}]")
            chains.append(
                f"[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"gblur=sigma=30[bgb{i}]"
            )
            chains.append(f"[fg{i}]scale={W}:-2:flags=lanczos[fgs{i}]")
            chains.append(
                f"[bgb{i}][fgs{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v{i}]"
            )
        if job.video_only:
            concat_in.append(f"[v{i}]")
        else:
            chains.append(a)
            concat_in.append(f"[v{i}][a{i}]")

    n = len(pieces)
    if job.video_only:
        chains.append("".join(concat_in) + f"concat=n={n}:v=1:a=0[vc]")
    else:
        chains.append("".join(concat_in) + f"concat=n={n}:v=1:a=1[vc][ac]")
    vlast = "vc"
    if job.ass_text is not None:
        files["subs.ass"] = job.ass_text
        fonts = ":fontsdir=fonts" if job.fonts_dir else ""
        chains.append(f"[vc]ass=subs.ass{fonts}[vs]")
        vlast = "vs"
    if job.logo is not None:
        lx, ly = logo_overlay_xy(job.logo_position, job.safe_zone, W, H)
        lw = int(W * LOGO_WIDTH_PCT) // 2 * 2
        op = max(0.0, min(1.0, job.logo_opacity))
        chains.append(f"[1:v]scale={lw}:-1,format=rgba,colorchannelmixer=aa={op:.3f}[logo]")
        chains.append(f"[{vlast}][logo]overlay=x={lx}:y={ly}:eof_action=repeat:format=auto[vl]")
        vlast = "vl"
    chains.append(f"[{vlast}]null[vout]" if job.video_only
                  else f"[{vlast}]format=yuv420p[vout]")

    if not job.video_only:
        dur = job.timeline.duration_ms / 1000
        fade = job.cfg.fade_ms / 1000
        afx = ""
        if job.cfg.loudnorm_target_lufs is not None:
            # Bir o'tishli EBU R128 (TZ 10-bo'lim). TP/LRA - keng tarqalgan ijtimoiy tarmoq qiymatlari.
            afx += f"loudnorm=I={job.cfg.loudnorm_target_lufs:g}:TP=-1.5:LRA=11,"
        afx += f"afade=t=in:d={fade:.3f},afade=t=out:st={max(0.0, dur - fade):.3f}:d={fade:.3f}"
        afx += f",aresample={job.cfg.audio_rate}"
        chains.append(f"[ac]{afx}[aout]")
    return ";\n".join(chains), files, seek_ms / 1000


def ffmpeg_major(ffmpeg: str) -> int:
    r = run([ffmpeg, "-hide_banner", "-version"])
    m = re.search(r"ffmpeg version n?(\d+)", r.stdout)
    return int(m.group(1)) if m else 0


def _prepare_workdir(job: RenderJob, graph: str, files: dict[str, str]) -> None:
    job.workdir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (job.workdir / name).write_text(text, encoding="utf-8")
    (job.workdir / "graph.txt").write_text(graph, encoding="utf-8")
    if job.fonts_dir is not None and job.ass_text is not None:
        link = job.workdir / "fonts"
        if not link.exists():
            import shutil

            shutil.copytree(job.fonts_dir, link)


def _inputs(job: RenderJob, ffmpeg: str, seek_s: float, span_s: float | None) -> list[str]:
    args = ["-ss", f"{seek_s:.3f}"]
    if span_s is not None:
        args += ["-t", f"{span_s:.3f}"]
    args += ["-i", str(job.src.resolve())]
    if job.logo is not None:
        args += ["-i", str(Path(job.logo).resolve())]
    graph_opt = ["-/filter_complex", "graph.txt"] if ffmpeg_major(ffmpeg) >= 7 else [
        "-filter_complex_script", "graph.txt"]
    return args + graph_opt


def build_command(job: RenderJob, ffmpeg: str) -> list[str]:
    graph, files, seek_s = build_graph(job)
    _prepare_workdir(job, graph, files)
    span_s = (max(p.src_end_ms for p in split_pieces(job.timeline, job.layouts)) / 1000) - seek_s + 0.5
    return [
        ffmpeg, "-y", "-hide_banner", "-v", "error", "-stats",
        *_inputs(job, ffmpeg, seek_s, span_s),
        "-map", "[vout]", "-map", "[aout]",
        *job.encoder.args,
        "-c:a", "aac", "-b:a", f"{job.cfg.audio_bitrate_kbps}k", "-ac", "2",
        "-movflags", "+faststart",
        str(job.out.resolve()),
    ]


def build_frame_command(job: RenderJob, ffmpeg: str) -> list[str]:
    """Bitta JPG kadr (job.out) - preview uchun; job.video_only bo'lishi kerak."""
    graph, files, seek_s = build_graph(job)
    _prepare_workdir(job, graph, files)
    return [
        ffmpeg, "-y", "-hide_banner", "-v", "error",
        *_inputs(job, ffmpeg, seek_s, None),
        "-map", "[vout]", "-frames:v", "1", "-q:v", "3", "-update", "1",
        str(job.out.resolve()),
    ]


def _resolve_subs(job: RenderJob, ffmpeg: str, allow_no_subs: bool) -> RenderJob:
    if job.ass_text is None or has_filter(ffmpeg, "ass"):
        return job
    if not allow_no_subs:
        raise LibassMissing()
    return replace(job, ass_text=None)


def _run(cmd: list[str], job: RenderJob, timeout_s: float | None) -> None:
    import subprocess

    job.out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, cwd=job.workdir, capture_output=True, text=True, timeout=timeout_s,
                       check=False)
    if r.returncode != 0:
        (job.workdir / "ffmpeg.log").write_text(r.stderr, encoding="utf-8")
        raise RuntimeError(f"render xatosi (ffmpeg {r.returncode}): {r.stderr.strip()[-800:]}")


def render(job: RenderJob, timeout_s: float | None = None, allow_no_subs: bool = False) -> Path:
    """Klipni render qiladi. libass yo'q bo'lsa: LibassMissing yoki (allow_no_subs) subtitrsiz."""
    ffmpeg = str(find_tool("ffmpeg"))
    job = _resolve_subs(job, ffmpeg, allow_no_subs)
    _run(build_command(job, ffmpeg), job, timeout_s)
    return job.out


def render_frame(job: RenderJob, timeout_s: float | None = 60) -> Path:
    """Bitta kadr (preview). libass yo'q bo'lsa subtitrsiz - xato bermaydi."""
    ffmpeg = str(find_tool("ffmpeg"))
    job = _resolve_subs(replace(job, video_only=True), ffmpeg, allow_no_subs=True)
    _run(build_frame_command(job, ffmpeg), job, timeout_s)
    return job.out
