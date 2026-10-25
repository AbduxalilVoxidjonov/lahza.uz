"""Standalone, stdlib-only reference exporter. No production imports.

Spans are source-time half-open [start_ms, end_ms). ASS must already use
OUTPUT timeline time. Cumulative output boundaries are rounded to frames (no
per-segment rounding drift). Sub-frame output segments are rejected. Encoded AAC may have
encoder priming/padding (1024 samples, normally hidden by MP4 edit lists).
Filters execute on CPU; hardware selection accelerates encoding, not the graph.

build_command() stages only small ASS/LUT/font assets in workdir; execute its
returned argv with cwd=workdir and shell=False. run_export() owns staging,
preflight, cancellation, progress, cleanup and atomic, non-overwriting publish.
At most 64 bounded inputs, decoder threads=1. Split larger edits explicitly;
this reference never silently batches into intermediate media.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


class ExportError(RuntimeError):
    pass


class ExportCancelled(ExportError):
    pass


@dataclass(frozen=True)
class Segment:
    source: Path
    start_ms: int
    end_ms: int
    speed: float = 1.0
    gain_db: float = 0.0
    mute: bool = False

    def __post_init__(self) -> None:
        if any(type(n) is not int for n in (self.start_ms, self.end_ms)):
            raise ValueError("Spans require integer milliseconds")
        if not 0 <= self.start_ms < self.end_ms:
            raise ValueError("Expected half-open span 0 <= start_ms < end_ms")
        _number(self.speed, 0.25, 4.0, "speed")
        _number(self.gain_db, -60, 24, "gain_db")
        if type(self.mute) is not bool:
            raise ValueError("mute must be boolean")

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / (1000 * self.speed)


@dataclass(frozen=True)
class ExportConfig:
    output: Path
    width: int = 1080
    height: int = 1920
    fps: int = 30
    sample_rate: int = 48000
    bitrate_kbps: int = 8000
    encoder: str = "auto"
    ass_path: Path | None = None
    lut_path: Path | None = None
    fonts_dir: Path | None = None
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    color_filter: str = "lut3d"  # LGPL default: explicit RGB grade, see _stage_assets.
    music: Path | None = None
    music_gain_db: float = -18.0
    duck_music: bool = True


@dataclass(frozen=True)
class ExportOptions:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    threads: int = 2
    filter_threads: int = 1
    max_segments: int = 64
    timeout_s: float = 1800.0
    probe_timeout_s: float = 20.0
    preflight: bool = True
    allow_libx264: bool = False  # Explicit development fallback, never implicit.
    overwrite: bool = False


@dataclass(frozen=True)
class MediaInfo:
    duration_s: float
    video: dict | None
    audio: dict | None
    format_name: str


DEFAULT_OPTIONS = ExportOptions()


@dataclass(frozen=True)
class ExportResult:
    output: Path
    duration_s: float
    encoder: str
    command: tuple[str, ...]


def _number(value: float, low: float, high: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite in [{low}, {high}]")


def _file(path: Path) -> Path:
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")
    return path


def tool_path(value: str) -> str:
    found = shutil.which(str(value))
    if not found:
        raise ExportError(f"Executable unavailable: {value}")
    return str(Path(found).resolve())


def probe_media(path: Path, options: ExportOptions = DEFAULT_OPTIONS) -> MediaInfo:
    result = subprocess.run(
        [
            tool_path(options.ffprobe),
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(_file(path)),
        ],
        capture_output=True,
        text=True,
        timeout=options.probe_timeout_s,
        shell=False,
        check=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    duration = float(data.get("format", {}).get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Finite positive media duration required: {path}")
    return MediaInfo(duration, video, audio, data.get("format", {}).get("format_name", ""))


def validate_config(config: ExportConfig, options: ExportOptions) -> None:
    for name, value, low, high in (
        ("width", config.width, 16, 7680),
        ("height", config.height, 16, 7680),
        ("fps", config.fps, 1, 120),
        ("sample_rate", config.sample_rate, 8000, 96000),
        ("bitrate_kbps", config.bitrate_kbps, 100, 100000),
        ("threads", options.threads, 1, 16),
        ("filter_threads", options.filter_threads, 1, 8),
        ("max_segments", options.max_segments, 1, 64),
    ):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be integer in [{low}, {high}]")
    if config.width % 2 or config.height % 2:
        raise ValueError("H.264 4:2:0 dimensions must be even")
    if Path(config.output).suffix.lower() != ".mp4":
        raise ValueError("This reference exports MP4 only")
    _number(config.brightness, -1, 1, "brightness")
    _number(config.contrast, 0, 3, "contrast")
    _number(config.saturation, 0, 3, "saturation")
    _number(config.music_gain_db, -60, 12, "music_gain_db")
    if config.color_filter not in ("lut3d", "eq"):
        raise ValueError("color_filter must be lut3d or eq (eq needs a GPL-enabled FFmpeg)")
    _number(options.timeout_s, 0.001, 86400, "timeout_s")
    _number(options.probe_timeout_s, 0.001, 120, "probe_timeout_s")


ENCODERS = ("h264_videotoolbox", "h264_nvenc", "h264_amf", "h264_qsv", "h264_mf")


def _encoder_args(name: str, config: ExportConfig, options: ExportOptions) -> list[str]:
    if name not in ENCODERS and not (name == "libx264" and options.allow_libx264):
        raise ValueError(f"Encoder not allowed: {name}; libx264 requires allow_libx264=True")
    result = ["-c:v", name, "-b:v", f"{config.bitrate_kbps}k"]
    if name == "h264_videotoolbox":
        result += ["-allow_sw", "0"]
    elif name == "h264_nvenc":
        result += ["-preset", "p4"]
    elif name == "libx264":
        result += ["-preset", "veryfast", "-threads:v", str(options.threads)]
    result += ["-pix_fmt", "nv12" if name == "h264_qsv" else "yuv420p"]
    return result


def select_encoder(config: ExportConfig, options: ExportOptions) -> str:
    validate_config(config, options)
    if config.encoder == "auto":
        order = (
            ["h264_videotoolbox"]
            if sys.platform == "darwin"
            else ["h264_nvenc", "h264_amf", "h264_qsv", "h264_mf"]
        )
        if options.allow_libx264:
            order.append("libx264")
    else:
        order = [config.encoder]
    if not options.preflight:
        if config.encoder == "auto":
            raise ValueError("auto encoder selection requires preflight")
        _encoder_args(order[0], config, options)
        return order[0]
    errors = []
    for name in order:
        args = _encoder_args(name, config, options)
        try:
            result = subprocess.run(
                [
                    tool_path(options.ffmpeg),
                    "-v",
                    "error",
                    "-nostdin",
                    "-filter_threads",
                    "1",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=s={config.width}x{config.height}:r={config.fps}:d=0.12",
                    *args,
                    "-frames:v",
                    "3",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                timeout=options.probe_timeout_s,
                shell=False,
            )
            if result.returncode == 0:
                return name
            errors.append(f"{name}: {result.stderr[-1000:].decode(errors='replace')}")
        except subprocess.TimeoutExpired:
            errors.append(f"{name}: preflight timed out")
    raise ExportError("No working encoder. " + "\n".join(errors))


def _stage_file(source: Path, target: Path, max_bytes: int) -> None:
    source = _file(source)
    if source.stat().st_size > max_bytes:
        raise ValueError(f"Asset exceeds {max_bytes} bytes: {source}")
    # All graph filenames are controlled ASCII basenames. No user path enters
    # the filter expression, even paths containing : ' \\ , ; [] or Unicode.
    if source != target.resolve():
        shutil.copyfile(source, target)


def _stage_assets(config: ExportConfig, workdir: Path) -> list[str]:
    filters = []
    if config.lut_path:
        _stage_file(config.lut_path, workdir / "grade.cube", 64 * 1024 * 1024)
        filters.append("lut3d=file=grade.cube")
    if (config.brightness, config.contrast, config.saturation) != (0, 1, 1):
        if config.color_filter == "eq":
            # Opt-in only; bundled LGPL FFmpeg intentionally has no eq filter.
            filters.append(
                f"eq=brightness={config.brightness:.9g}:contrast={config.contrast:.9g}"
                f":saturation={config.saturation:.9g}"
            )
        else:
            # Defined RGB grade (not a claim of identical FFmpeg eq semantics):
            # contrast around 0.5, additive brightness, BT.709 luma saturation.
            # A tiny 17^3 text LUT is allowed; no intermediate media is written.
            with (workdir / "color.cube").open("w", encoding="ascii") as handle:
                handle.write("LUT_3D_SIZE 17\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
                for b in range(17):
                    for g in range(17):
                        for r in range(17):
                            rgb = [
                                (v / 16 - 0.5) * config.contrast + 0.5 + config.brightness
                                for v in (r, g, b)
                            ]
                            luma = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                            handle.write(
                                " ".join(
                                    f"{min(1, max(0, luma + (v - luma) * config.saturation)):.8f}"
                                    for v in rgb
                                )
                                + "\n"
                            )
            filters.append("lut3d=file=color.cube:interp=tetrahedral")
    if config.ass_path:
        _stage_file(config.ass_path, workdir / "captions.ass", 16 * 1024 * 1024)
        font_option = ""
        if config.fonts_dir:
            fonts = sorted(
                p
                for p in Path(config.fonts_dir).iterdir()
                if p.suffix.lower() in (".ttf", ".otf", ".ttc")
            )
            if not 1 <= len(fonts) <= 32:
                raise ValueError("fonts_dir requires 1..32 fonts")
            if sum(_file(p).stat().st_size for p in fonts) > 64 * 1024 * 1024:
                raise ValueError("Font assets exceed 64 MiB")
            (workdir / "fonts").mkdir(exist_ok=True)
            for i, path in enumerate(fonts):
                _stage_file(
                    path, workdir / "fonts" / f"font{i}{path.suffix.lower()}", 32 * 1024 * 1024
                )
            font_option = ":fontsdir=fonts"
        filters.append("ass=filename=captions.ass" + font_option)
    return filters


def _atempo(speed: float) -> str:
    filters = []
    while speed > 2:
        filters.append("atempo=2")
        speed /= 2
    while speed < 0.5:
        filters.append("atempo=0.5")
        speed /= 0.5
    filters.append(f"atempo={speed:.12g}")
    return ",".join(filters)


def timeline_durations(segments: Sequence[Segment], fps: int) -> list[float]:
    cumulative = 0.0
    previous_frame = 0
    durations = []
    for segment in segments:
        cumulative += segment.duration_s
        frame = round(cumulative * fps)
        if frame <= previous_frame:
            raise ValueError("A segment is shorter than one output frame; merge it explicitly")
        durations.append((frame - previous_frame) / fps)
        previous_frame = frame
    return durations


def build_command(
    segments: Sequence[Segment],
    config: ExportConfig,
    *,
    workdir: Path,
    options: ExportOptions = DEFAULT_OPTIONS,
    encoder: str | None = None,
    output: Path | None = None,
) -> list[str]:
    """Return runnable argv; cwd MUST equal workdir. Does not run the export.

    Output existence policy and atomic publication belong to run_export().
    A supplied encoder bypasses preflight but is still whitelisted/validated.
    """
    validate_config(config, options)
    if not 1 <= len(segments) <= options.max_segments:
        raise ValueError(f"Expected 1..{options.max_segments} segments")
    workdir = Path(workdir).resolve(strict=True)
    encoder = encoder or select_encoder(config, options)
    encoding = _encoder_args(encoder, config, options)
    infos: dict[Path, MediaInfo] = {}
    command = [
        tool_path(options.ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-filter_complex_threads",
        str(options.filter_threads),
        "-filter_threads",
        str(options.filter_threads),
    ]
    graph: list[str] = []
    durations = timeline_durations(segments, config.fps)
    duration = sum(durations)
    for i, segment in enumerate(segments):
        path = _file(segment.source)
        if path not in infos:
            infos[path] = probe_media(path, options)
        info = infos[path]
        if not info.video:
            raise ValueError(f"Segment has no video: {path}")
        if info.video.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
            raise ValueError(
                "HDR requires an explicit tone-map/colorspace adapter; SDR reference only"
            )
        if info.video.get("sample_aspect_ratio", "1:1") not in {"1:1", "N/A"}:
            raise ValueError("Non-square source pixels require an explicit aspect-ratio adapter")
        # No silently clipped sources, including out-of-range tail requests.
        if segment.end_ms / 1000 > info.duration_s + 0.000001:
            raise ValueError(f"Segment extends beyond media duration: {path}")
        for stream in (info.video, info.audio):
            if stream and abs(float(stream.get("start_time", 0))) > 0.000001:
                raise ValueError(
                    "Reference requires zero-origin synchronized streams; normalize first"
                )
        source_duration = (segment.end_ms - segment.start_ms) / 1000
        command += [
            "-threads",
            "1",
            "-ss",
            f"{segment.start_ms / 1000:.6f}",
            "-t",
            f"{source_duration:.6f}",
            "-i",
            str(path),
        ]
        v_index = info.video["index"]
        graph.append(
            f"[{i}:{v_index}]trim=start=0:duration={source_duration:.9f},"
            f"setpts=(PTS-STARTPTS)/{segment.speed:.12g},"
            f"scale={config.width}:{config.height}:force_original_aspect_ratio=decrease,"
            f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fps={config.fps},format=yuv420p,"
            # tpad only repairs a final frame lost in temporal quantization;
            # it never creates a media file. Limit to requested output span.
            f"tpad=stop_mode=clone:stop_duration={1 / config.fps:.9f},"
            f"trim=end_frame={round(durations[i] * config.fps)},setpts=PTS-STARTPTS[v{i}]"
        )
        audio_format = (
            f"aresample={config.sample_rate},"
            f"aformat=sample_fmts=fltp:sample_rates={config.sample_rate}"
            ":channel_layouts=stereo"
        )
        if info.audio and not segment.mute:
            graph.append(
                f"[{i}:{info.audio['index']}]atrim=start=0:duration={source_duration:.9f},"
                f"asetpts=PTS-STARTPTS,{_atempo(segment.speed)},{audio_format},"
                f"volume={segment.gain_db:.9g}dB,apad,"
                f"atrim=duration={durations[i]:.9f},asetpts=PTS-STARTPTS[a{i}]"
            )
        else:
            graph.append(
                f"anullsrc=r={config.sample_rate}:cl=stereo,{audio_format},"
                f"atrim=duration={durations[i]:.9f},asetpts=PTS-STARTPTS[a{i}]"
            )
    graph.append(
        "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
        + f"concat=n={len(segments)}:v=1:a=1[cutv][speech]"
    )
    video_filters = _stage_assets(config, workdir)
    graph.append("[cutv]" + ",".join(video_filters + ["format=yuv420p"]) + "[video]")
    if config.music:
        music = _file(config.music)
        music_info = probe_media(music, options)
        if not music_info.audio:
            raise ValueError("Music file has no audio")
        command += [
            "-threads",
            "1",
            "-stream_loop",
            "-1",
            "-t",
            f"{duration:.9f}",
            "-i",
            str(music),
        ]
        graph.append(
            f"[{len(segments)}:{music_info.audio['index']}]aresample={config.sample_rate},"
            f"aformat=sample_fmts=fltp:sample_rates={config.sample_rate}:channel_layouts=stereo,"
            f"atrim=duration={duration:.9f},asetpts=PTS-STARTPTS,"
            f"volume={config.music_gain_db:.9g}dB[music]"
        )
        if config.duck_music:
            graph += [
                "[speech]asplit=2[voice][sidechain]",
                "[music][sidechain]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=350[bed]",
                "[voice][bed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95:latency=1[audio]",
            ]
        else:
            graph.append(
                "[speech][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95:latency=1[audio]"
            )
    else:
        graph.append("[speech]anull[audio]")
    return command + [
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[video]",
        "-map",
        "[audio]",
        *encoding,
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        str(config.sample_rate),
        "-ac",
        "2",
        "-threads:a",
        str(options.threads),
        "-t",
        f"{duration:.9f}",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        "-progress",
        "pipe:1",
        "-stats_period",
        "0.2",
        "-nostats",
        "-f",
        "mp4",
        str(Path(output or config.output).resolve()),
    ]


def execute_command(
    command: Sequence[str],
    *,
    cwd: Path,
    options: ExportOptions,
    duration_s: float,
    cancel: threading.Event | None = None,
    progress: Callable[[float], None] | None = None,
) -> None:
    """Drain both pipes while polling timeout/cancel, even when no progress arrives.

    Callback runs on the caller's thread. Callback exceptions stop the process.
    Diagnostics and the progress queue are bounded, independent of export length.
    """
    if cancel and cancel.is_set():
        raise ExportCancelled("Export cancelled before start")
    events: queue.Queue[float] = queue.Queue(maxsize=32)
    diagnostics: deque[bytes] = deque(maxlen=16)
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    def read_progress() -> None:
        assert process.stdout is not None
        while line := process.stdout.readline(4096):
            if line.startswith(b"out_time_us="):
                try:
                    value = min(0.999, max(0, int(line.split(b"=", 1)[1]) / 1e6 / duration_s))
                    events.put_nowait(value)
                except (ValueError, queue.Full):
                    pass

    def read_stderr() -> None:
        assert process.stderr is not None
        while block := process.stderr.read(4096):
            diagnostics.append(block)

    readers = [
        threading.Thread(target=read_progress, daemon=True),
        threading.Thread(target=read_stderr, daemon=True),
    ]
    for reader in readers:
        reader.start()
    started = time.monotonic()
    last = 0.0
    try:
        while True:
            if cancel and cancel.is_set():
                raise ExportCancelled("Export cancelled")
            if time.monotonic() - started > options.timeout_s:
                raise TimeoutError(f"Export exceeded {options.timeout_s}s")
            try:
                value = events.get(timeout=0.05)
                last = max(last, value)
                if progress:
                    progress(last)
            except queue.Empty:
                pass
            if process.poll() is not None:
                break
        for reader in readers:
            reader.join(timeout=2)
        if process.returncode:
            raise ExportError(b"".join(diagnostics).decode(errors="replace")[-16000:])
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=2)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()


def publish_output(temp: Path, output: Path, overwrite: bool) -> None:
    if not temp.is_file() or temp.stat().st_size == 0:
        raise ExportError("Encoder produced no output")
    if overwrite:
        os.replace(temp, output)
    else:
        # Same-filesystem hard link is atomic and fails if destination appeared
        # during export. Unlike exists()+replace(), it cannot overwrite a race.
        os.link(temp, output)
        temp.unlink()


def run_export(
    segments: Sequence[Segment],
    config: ExportConfig,
    *,
    options: ExportOptions = DEFAULT_OPTIONS,
    cancel: threading.Event | None = None,
    progress: Callable[[float], None] | None = None,
) -> ExportResult:
    validate_config(config, options)
    if not 1 <= len(segments) <= options.max_segments:
        raise ValueError(f"Expected 1..{options.max_segments} segments")
    duration = sum(timeline_durations(segments, config.fps))
    output = Path(config.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    assets = [s.source for s in segments] + [config.music, config.ass_path, config.lut_path]
    if any(p is not None and Path(p).resolve() == output for p in assets):
        raise ValueError("Output must not replace an input or asset")
    if output.exists() and not options.overwrite:
        raise FileExistsError(output)
    if cancel and cancel.is_set():
        raise ExportCancelled("Export cancelled before preflight")
    encoder = select_encoder(config, options)
    fd, filename = tempfile.mkstemp(prefix=".lahza-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    temp = Path(filename)
    try:
        with tempfile.TemporaryDirectory(prefix="lahza-graph-") as directory:
            command = build_command(
                segments,
                config,
                options=options,
                encoder=encoder,
                workdir=Path(directory),
                output=temp,
            )
            execute_command(
                command,
                cwd=Path(directory),
                options=options,
                duration_s=duration,
                cancel=cancel,
                progress=progress,
            )
            publish_output(temp, output, options.overwrite)
        if progress:
            progress(1.0)
        return ExportResult(output, duration, encoder, tuple(command))
    finally:
        temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--span", action="append", required=True, metavar="START_MS:END_MS:SPEED")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--encoder", default="auto")
    parser.add_argument("--allow-libx264", action="store_true")
    parser.add_argument("--ass", type=Path)
    parser.add_argument("--lut", type=Path)
    parser.add_argument("--fonts-dir", type=Path)
    parser.add_argument("--music", type=Path)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    args = parser.parse_args()
    segments = []
    for item in args.span:
        start, end, *speed = item.split(":")
        segments.append(Segment(args.source, int(start), int(end), float(speed[0]) if speed else 1))
    result = run_export(
        segments,
        ExportConfig(
            args.output,
            width=args.width,
            height=args.height,
            encoder=args.encoder,
            ass_path=args.ass,
            lut_path=args.lut,
            fonts_dir=args.fonts_dir,
            music=args.music,
        ),
        options=ExportOptions(
            ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, allow_libx264=args.allow_libx264
        ),
    )
    print(
        json.dumps(
            {"output": str(result.output), "seconds": result.duration_s, "encoder": result.encoder}
        )
    )


if __name__ == "__main__":
    main()
