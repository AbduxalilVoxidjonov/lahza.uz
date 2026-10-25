"""Local-only, bounded sticker inspection and shared export/preview overlays."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import uuid
from pathlib import Path

from lahza_engine.media.tools import find_tool

MAX_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_777_216
MAX_FRAMES = 600
MAX_DECODED_PIXELS = 128_000_000
ASSETS = Path(__file__).parent / "assets"


class StickerError(RuntimeError):
    """An unsupported, missing, corrupt or oversized local sticker."""


def _probe(path: Path, *args: str) -> dict:
    try:
        result = subprocess.run(
            [str(find_tool("ffprobe")), "-v", "error", "-max_alloc", "134217728",
             "-protocol_whitelist", "file,pipe", *args, "-of", "json", str(path)],
            capture_output=True, text=True, timeout=20, check=True,
        )
        if result.stderr.strip():
            raise StickerError("Sticker decode failed: " + result.stderr[-300:])
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise StickerError(f"Sticker decode/probe failed: {path.name}") from exc


def inspect_sticker(path: str) -> dict:
    """Probe dimensions first, then actually decode a bounded number of frames."""
    if not path.strip() or "://" in path or path.startswith(("\\\\", "//")):
        raise StickerError("Sticker must be a local file, not a URL or network path")
    try:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise StickerError(f"Sticker file not found: {p.name}")
        if p.stat().st_size > MAX_BYTES:
            raise StickerError("Sticker exceeds 16 MiB")
        with p.open("rb") as source:
            signature = source.read(12)
    except (OSError, ValueError, RuntimeError) as exc:
        if isinstance(exc, StickerError):
            raise
        raise StickerError("Cannot read sticker file") from exc
    if not (signature.startswith(b"\x89PNG\r\n\x1a\n")
            or signature.startswith((b"GIF87a", b"GIF89a"))
            or (signature[:4] == b"RIFF" and signature[8:12] == b"WEBP")):
        raise StickerError("Sticker must be a PNG, static WebP or GIF file")
    streams = _probe(p, "-show_streams").get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") not in {"png", "webp", "gif"}:
        raise StickerError("Sticker must decode as PNG, static WebP or GIF")
    s = streams[0]
    w, h = int(s.get("width", 0)), int(s.get("height", 0))
    if not (0 < w <= MAX_DIMENSION and 0 < h <= MAX_DIMENSION) or w * h > MAX_PIXELS:
        raise StickerError("Sticker dimensions exceed 4096 px / 16 megapixels")
    limit = min(MAX_FRAMES, MAX_DECODED_PIXELS // (w * h))
    decoded = _probe(p, "-threads", "1", "-read_intervals", f"%+#{limit + 1}",
                     "-count_frames", "-show_streams").get("streams", [])
    count = int(decoded[0].get("nb_read_frames", 0)) if decoded else 0
    if not count or count > limit:
        raise StickerError("Sticker exceeds decoded frame/pixel limit or has no decodable frames")
    fmt = s["codec_name"].upper()
    if fmt != "GIF" and count != 1:
        raise StickerError("Only GIF animation is supported")
    return {"path": str(p), "width": w, "height": h, "animated": count > 1, "format": fmt}


def _persistent_asset(source: Path, cache: Path) -> Path:
    """A frozen engine's _MEIPASS disappears on exit; never save it in a timeline."""
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    folder = cache / digest
    folder.mkdir(parents=True, exist_ok=True)
    if not folder.resolve().is_relative_to(cache.resolve()):
        raise StickerError("Unsafe sticker cache directory")
    dest = folder / source.name
    if dest.is_symlink():
        raise StickerError("Unsafe sticker cache file")
    if not dest.is_file() or hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
        temporary = folder / ("." + uuid.uuid4().hex)
        try:
            temporary.write_bytes(data)
            temporary.replace(dest)
        finally:
            temporary.unlink(missing_ok=True)
    return dest.resolve()


def list_stickers(persistent_dir: Path | None = None) -> dict:
    def path(sid: str) -> Path:
        source = ASSETS / f"{sid}.png"
        return _persistent_asset(source, persistent_dir) if persistent_dir is not None else source

    return {"items": [dict(id=sid, name=name, **inspect_sticker(str(path(sid))))
                      for sid, name in (("spark", "Spark"), ("heart", "Heart"), ("arrow", "Arrow"))]}


def sticker_inputs(tl, inputs: list[str]) -> list[int]:
    """Validate every asset, including inactive ones; input order matches stable layer order."""
    if len(tl.stickers) > 32:
        raise StickerError("At most 32 stickers are allowed")
    indices = []
    for sticker in sorted(tl.stickers, key=lambda s: s.layer):
        info = inspect_sticker(sticker.path)
        indices.append(sum(x == "-i" for x in inputs))
        if info["format"] == "GIF":
            inputs.extend(["-stream_loop", "-1", "-ignore_loop", "1"])
        else:
            inputs.extend(["-loop", "1", "-framerate", str(tl.format.fps)])
        inputs.extend(["-protocol_whitelist", "file,pipe", "-i", info["path"]])
    return indices


def overlay_stickers(tl, cur: str, indices: list[int], at_ms: int | None = None):
    """GIF clock starts at sticker start; half-open gating and animation match in preview."""
    chains = []
    for n, (s, idx) in enumerate(zip(sorted(tl.stickers, key=lambda s: s.layer), indices, strict=True)):
        dur = (s.end_ms - s.start_ms) / 1000
        start = s.start_ms / 1000
        bw, bh = max(1, round(s.width * tl.format.w)), max(1, round(s.height * tl.format.h))
        filters = [f"fps={tl.format.fps}", "format=rgba",
                   f"scale={bw}:{bh}:force_original_aspect_ratio=decrease", "setsar=1"]
        if s.animation == "pop":
            # Grow from 65% to 100% over the first 180 ms, keeping the center fixed.
            k = "(0.65+0.35*min(t/0.18,1))"
            filters.append(f"scale=w='max(1,iw*{k})':h='max(1,ih*{k})':eval=frame")
        if s.rotation:
            angle = s.rotation * 3.141592653589793 / 180
            filters.append(f"rotate={angle}:ow=rotw({angle}):oh=roth({angle}):c=none")
        filters.append(f"colorchannelmixer=aa={s.opacity}")
        if s.animation == "fade":
            ramp = min(.2, dur / 2)
            filters.extend([f"fade=t=in:st=0:d={ramp}:alpha=1",
                            f"fade=t=out:st={dur-ramp}:d={ramp}:alpha=1"])
        if at_ms is None:
            filters.extend([f"trim=duration={dur}", f"setpts=PTS-STARTPTS+{start}/TB"])
            enable = f"gte(t,{start})*lt(t,{s.end_ms / 1000})"
        else:
            # Consume the same decoded GIF/animation frames from time zero as export does.
            elapsed = max(0, at_ms / 1000 - start) if s.start_ms <= at_ms < s.end_ms else 0
            elapsed = math.floor(elapsed * tl.format.fps + 1e-8) / tl.format.fps
            filters.extend([f"trim=start={elapsed}", "setpts=PTS-STARTPTS"])
            enable = "1" if s.start_ms <= at_ms < s.end_ms else "0"
        chains.append(f"[{idx}:v]" + ",".join(filters) + f"[stk{n}]")
        chains.append(f"[{cur}][stk{n}]overlay=x='{s.x * tl.format.w}-overlay_w/2':"
                      f"y='{s.y * tl.format.h}-overlay_h/2':enable='{enable}':"
                      f"eof_action=pass:repeatlast=0:format=auto[vs{n}]")
        cur = f"vs{n}"
    return chains, cur
