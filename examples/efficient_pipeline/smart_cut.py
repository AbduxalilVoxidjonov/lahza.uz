"""Conservative H.264 fast-copy admission, not a universal smart GOP renderer.

Only ONE contiguous span, zero-origin MP4/MOV AVC (avcC), NO B frames, monotonic
PTS=DTS, unchanged geometry/FPS/SAR, packet-boundary endpoints and observed IDR
NAL units at BOTH boundaries are admitted. K/key_frame alone is NOT proof.
The end may instead be the verified end of the final packet at media EOF.
Audio is ALWAYS decoded/re-encoded to AAC, never claimed sample-exact AAC copy.

Unproven/open GOP, HEVC CRA, B frames, multiple kept spans or any picture edit
deterministically use single_pass.run_export(). No intermediate media. A hybrid
GOP renderer would need codec-parameter/extradata reconciliation, reordered DTS,
edge GOP encoding and audio continuity; it is deliberately not pretended here.

Indexing reads at most max_packets+1 metadata records. IDR evidence reads just
one compressed packet at each boundary. Cache indexes by file fingerprint in a
real application, and revalidate that fingerprint before executing any plan.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

try:  # Supports both namespace-package import and direct script invocation.
    from .single_pass import (
        DEFAULT_OPTIONS,
        ExportConfig,
        ExportOptions,
        ExportResult,
        Segment,
        execute_command,
        probe_media,
        publish_output,
        run_export,
        tool_path,
        validate_config,
    )
except ImportError:
    from single_pass import (
        DEFAULT_OPTIONS,
        ExportConfig,
        ExportOptions,
        ExportResult,
        Segment,
        execute_command,
        probe_media,
        publish_output,
        run_export,
        tool_path,
        validate_config,
    )


@dataclass(frozen=True)
class Packet:
    pts: Fraction
    dts: Fraction
    duration: Fraction
    key: bool


@dataclass(frozen=True)
class KeyframeIndex:
    packets: tuple[Packet, ...]
    keyframes: tuple[Fraction, ...]
    nal_length_size: int


@dataclass(frozen=True)
class SpanReport:
    requested_ms: tuple[int, int]
    admitted_ms: tuple[float, float]
    error_ms: tuple[float, float]


@dataclass(frozen=True)
class CopyPlan:
    mode: str  # copy_video_encode_audio | reencode
    reasons: tuple[str, ...]
    spans: tuple[SpanReport, ...]
    start_s: Fraction | None = None
    end_s: Fraction | None = None
    audio_present: bool = False


def _probe_json(path: Path, options: ExportOptions, args: list[str]) -> dict:
    result = subprocess.run(
        [tool_path(options.ffprobe), "-v", "error", *args, "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=options.probe_timeout_s,
        check=True,
        shell=False,
    )
    return json.loads(result.stdout)


def _hex_dump(value: str) -> bytes:
    chunks = []
    for line in value.splitlines():
        if ":" in line:
            # ffprobe's fixed-width hex area is separated from ASCII by 2 spaces.
            area = line.split(":", 1)[1].strip().split("  ", 1)[0]
            chunks.append(bytes.fromhex(area))
    return b"".join(chunks)


def _is_idr(data: bytes, length_size: int) -> bool:
    cursor = 0
    idr = False
    while cursor < len(data):
        if cursor + length_size > len(data):
            return False
        size = int.from_bytes(data[cursor : cursor + length_size], "big")
        cursor += length_size
        if size < 1 or cursor + size > len(data):
            return False
        kind = data[cursor] & 31
        if 1 <= kind <= 4:  # non-IDR VCL, including partitioned slices
            return False
        idr |= kind == 5
        cursor += size
    return idr


def build_keyframe_index(
    source: Path,
    options: ExportOptions = DEFAULT_OPTIONS,
    *,
    max_packets: int = 100000,
) -> KeyframeIndex:
    if type(max_packets) is not int or not 1 <= max_packets <= 100000:
        raise ValueError("max_packets must be in 1..100000")
    source = Path(source).resolve(strict=True)
    info = _probe_json(
        source,
        options,
        [
            "-select_streams",
            "v:0",
            "-show_streams",
            "-show_data",
            "-show_entries",
            "stream=codec_name,has_b_frames,is_avc,extradata",
        ],
    )
    stream = info["streams"][0]
    if stream.get("codec_name") != "h264" or stream.get("has_b_frames", 1) != 0:
        raise ValueError("Only H.264 without B frames is automatically admitted")
    avcc = _hex_dump(stream.get("extradata", ""))
    if stream.get("is_avc") != "true" or len(avcc) < 7 or avcc[0] != 1:
        raise ValueError("AVC avcC configuration required")
    # Exact integer stream ticks avoid 30fps/NTSC decimal rounding ambiguities.
    ticks = _probe_json(
        source,
        options,
        [
            "-select_streams",
            "v:0",
            "-read_intervals",
            f"%+#{max_packets + 1}",
            "-show_streams",
            "-show_packets",
            "-show_entries",
            "stream=time_base:packet=pts,dts,duration,flags",
        ],
    )
    time_base = Fraction(ticks["streams"][0]["time_base"])
    packets = []
    for row in ticks.get("packets", []):
        packet = Packet(
            int(row["pts"]) * time_base,
            int(row["dts"]) * time_base,
            int(row["duration"]) * time_base,
            "K" in row["flags"],
        )
        if (
            packet.pts != packet.dts
            or packet.duration <= 0
            or "D" in row["flags"]
            or (packets and packet.pts != packets[-1].pts + packets[-1].duration)
        ):
            raise ValueError("Reordered, discarded, discontinuous or unknown video packets")
        packets.append(packet)
    if not packets or len(packets) > max_packets or packets[0].pts != 0:
        raise ValueError("Bounded complete zero-origin packet index required")
    return KeyframeIndex(tuple(packets), tuple(p.pts for p in packets if p.key), (avcc[4] & 3) + 1)


def _boundary_is_idr(
    source: Path, timestamp: Fraction, index: KeyframeIndex, options: ExportOptions
) -> bool:
    # Seeking can land on an earlier sync point. Require the returned packet
    # timestamp to match our boundary, as well as K AND actual IDR NAL evidence.
    data = _probe_json(
        source,
        options,
        [
            "-select_streams",
            "v:0",
            "-read_intervals",
            f"{float(timestamp):.9f}%+#1",
            "-show_streams",
            "-show_packets",
            "-show_data",
            "-show_entries",
            "stream=time_base:packet=pts,dts,flags,data",
        ],
    )
    packets = data.get("packets", [])
    if len(packets) != 1:
        return False
    packet = packets[0]
    scale = Fraction(data["streams"][0]["time_base"])
    return (
        int(packet["pts"]) * scale == timestamp
        and int(packet["dts"]) * scale == timestamp
        and "K" in packet["flags"]
        and _is_idr(_hex_dump(packet.get("data", "")), index.nal_length_size)
    )


def plan_copy(
    source: Path,
    spans: Sequence[tuple[int, int]],
    config: ExportConfig,
    *,
    options: ExportOptions = DEFAULT_OPTIONS,
    snap_tolerance_ms: float = 0,
) -> CopyPlan:
    """Default: zero snapping. Explicit nonzero tolerance returns signed errors.

    Snapping is NEVER applied when falling back: original spans are reencoded.
    This API has no arbitrary FFmpeg args; unsupported edits cannot be ignored.
    """
    validate_config(config, options)
    if not math.isfinite(snap_tolerance_ms) or not 0 <= snap_tolerance_ms <= 1000:
        raise ValueError("snap_tolerance_ms must be finite in 0..1000")
    for a, b in spans:
        Segment(source, a, b)
    if not spans:
        raise ValueError("At least one span required")
    reports = tuple(SpanReport((a, b), (float(a), float(b)), (0, 0)) for a, b in spans)

    def fallback(reason: str) -> CopyPlan:
        return CopyPlan("reencode", (reason,), reports)

    if len(spans) != 1:
        return fallback("Multiple spans require the single-pass concat graph")
    if (
        config.ass_path
        or config.lut_path
        or config.music
        or (config.brightness, config.contrast, config.saturation) != (0, 1, 1)
    ):
        return fallback("Picture/subtitle/music edits require filtering")
    try:
        info = probe_media(source, options)
        video = info.video
        if not video or not set(info.format_name.split(",")) & {"mov", "mp4"}:
            return fallback("Only MP4/MOV video is whitelisted")
        if (video.get("width"), video.get("height")) != (config.width, config.height):
            return fallback("Resize/pad requires filtering")
        if (
            Fraction(video["avg_frame_rate"]) != config.fps
            or Fraction(video["r_frame_rate"]) != config.fps
            or video.get("sample_aspect_ratio", "1:1") != "1:1"
        ):
            return fallback("FPS/SAR normalization requires filtering")
        if video.get("side_data_list"):
            return fallback("Rotation/HDR/other side data is outside the copy whitelist")
        if any(abs(float(s.get("start_time", 0))) > 0.000001 for s in (video, info.audio) if s):
            return fallback("Only zero-origin synchronized streams are admitted")
        if info.audio and info.audio.get("codec_name") not in {
            "aac",
            "alac",
            "mp3",
            "pcm_s16le",
            "pcm_s24le",
            "pcm_s32le",
            "pcm_f32le",
        }:
            return fallback("Audio decoder/container combination not whitelisted")
        index = build_keyframe_index(source, options)
        eof = index.packets[-1].pts + index.packets[-1].duration
        requested_start, requested_end = (Fraction(n, 1000) for n in spans[0])
        if requested_end > eof or requested_start < 0:
            return fallback("Requested span is outside packet duration")
        if not index.keyframes:
            return fallback("No keyframe candidates")
        start = min(index.keyframes, key=lambda n: (abs(n - requested_start), n))
        end = min((*index.keyframes, eof), key=lambda n: (abs(n - requested_end), n))
        errors = ((start - requested_start) * 1000, (end - requested_end) * 1000)
        if start >= end or any(abs(e) > snap_tolerance_ms for e in errors):
            return fallback("Cut is not on verified sync boundaries; no silent snapping")
        if not _boundary_is_idr(source, start, index, options):
            return fallback("Start K flag is not verified IDR evidence")
        if end != eof and not _boundary_is_idr(source, end, index, options):
            return fallback("End K flag is not verified IDR evidence")
        if end == eof and abs(float(eof) - info.duration_s) > 0.001:
            return fallback("Video/audio/container EOF differ")
        report = SpanReport(
            spans[0], (float(start * 1000), float(end * 1000)), (float(errors[0]), float(errors[1]))
        )
        return CopyPlan(
            "copy_video_encode_audio",
            ("Verified AVC IDR endpoints; no B frames; AAC is reencoded, not copied",),
            (report,),
            start,
            end,
            info.audio is not None,
        )
    except (ValueError, KeyError, IndexError, OSError, subprocess.SubprocessError) as exc:
        return fallback(f"Copy safety not proven: {exc}")


def run_smart_cut(
    source: Path,
    spans: Sequence[tuple[int, int]],
    config: ExportConfig,
    *,
    options: ExportOptions = DEFAULT_OPTIONS,
    snap_tolerance_ms: float = 0,
    cancel: threading.Event | None = None,
    progress: Callable[[float], None] | None = None,
) -> tuple[CopyPlan, ExportResult]:
    source = Path(source).resolve(strict=True)
    fingerprint = (source.stat().st_size, source.stat().st_mtime_ns)
    plan = plan_copy(source, spans, config, options=options, snap_tolerance_ms=snap_tolerance_ms)
    if plan.mode == "reencode":
        return plan, run_export(
            [Segment(source, a, b) for a, b in spans],
            config,
            options=options,
            cancel=cancel,
            progress=progress,
        )
    if fingerprint != (source.stat().st_size, source.stat().st_mtime_ns):
        raise ValueError("Source changed during copy planning")
    if plan.start_s is None or plan.end_s is None:
        raise ValueError("Missing admitted copy boundaries")
    output = Path(config.output).resolve()
    if output == source or output.suffix.lower() != ".mp4":
        raise ValueError("Output must be a different MP4 file")
    if output.exists() and not options.overwrite:
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = float(plan.end_s - plan.start_s)
    fd, filename = tempfile.mkstemp(prefix=".lahza-copy-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    temp = Path(filename)
    command = [
        tool_path(options.ffmpeg),
        "-v",
        "error",
        "-nostdin",
        "-y",
        "-threads",
        "1",
        "-ss",
        f"{float(plan.start_s):.9f}",
        "-t",
        f"{duration:.9f}",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
    ]
    if plan.audio_present:
        command += [
            "-map",
            "0:a:0",
            "-af",
            f"atrim=duration={duration:.9f},asetpts=PTS-STARTPTS,apad,atrim=duration={duration:.9f}",
            "-c:a",
            "aac",
            "-ar",
            str(config.sample_rate),
            "-ac",
            "2",
            "-b:a",
            "192k",
            "-threads:a",
            str(options.threads),
        ]
    else:
        command += ["-an"]  # Copy path preserves absence of source audio.
    command += [
        "-t",
        f"{duration:.9f}",
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        "-f",
        "mp4",
        str(temp),
    ]
    try:
        execute_command(
            command,
            cwd=output.parent,
            options=options,
            duration_s=duration,
            cancel=cancel,
            progress=progress,
        )
        publish_output(temp, output, options.overwrite)
        if progress:
            progress(1.0)
        return plan, ExportResult(output, duration, "copy", tuple(command))
    finally:
        temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--span", action="append", required=True, metavar="START_MS:END_MS")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    spans = [tuple(map(int, s.split(":"))) for s in args.span]
    plan, result = run_smart_cut(
        args.source,
        spans,
        ExportConfig(args.output, width=args.width, height=args.height),
        options=ExportOptions(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe),
    )
    print(
        json.dumps(
            {"mode": plan.mode, "reason": plan.reasons, "output": str(result.output)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
