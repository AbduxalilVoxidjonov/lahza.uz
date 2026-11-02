"""Synthetic integration smoke test; no models, network, or production state.

Run from the repository root: python -m examples.efficient_pipeline.demo
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from .edit_model import delete_source
from .single_pass import ExportConfig, ExportOptions, Segment, probe_media, run_export
from .vad_cleaner import Word, plan_cleanup


def ass_time(milliseconds: int) -> str:
    centiseconds = round(milliseconds / 10)
    seconds, cs = divmod(centiseconds, 100)
    minutes, sec = divmod(seconds, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour}:{minute:02}:{sec:02}.{cs:02}"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    output_dir = root / "build/efficient-pipeline-verification"
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = root / "app/src-tauri/resources/bin/ffmpeg"
    ffprobe = root / "app/src-tauri/resources/bin/ffprobe"
    source, music = output_dir / "source.mp4", output_dir / "music.wav"

    # MPEG-4 is only a tiny fixture; the final export uses VideoToolbox H.264.
    subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-filter_threads",
            "1",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=6",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        timeout=30,
    )
    subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=160:sample_rate=48000:duration=2",
            str(music),
        ],
        check=True,
        timeout=15,
    )

    words = [
        Word("w0", "Salom", 200, 600, 0.98),
        Word("w1", "haligi", 800, 1100, 0.96),
        Word("w2", "bugun", 1400, 1800, 0.97),
        Word("w3", "demak", 3100, 3500, 0.98),
        Word("w4", "boshlaymiz", 4500, 5200, 0.97),
    ]
    speech = [(100, 1900), (3000, 3600), (4400, 5400)]
    cleanup = plan_cleanup(words, speech, 6000)
    speed = 1.25
    timeline = {
        "schema": "lahza.timeline/1",
        "media": {"source": {"id": "source", "path": str(source), "duration_ms": 6000}},
        "video": [
            {
                "id": "occurrence-1",
                "media": "source",
                "src_in_ms": 0,
                "src_out_ms": 6000,
                "speed": speed,
                "fx": [],
                "transition_in": None,
            }
        ],
        "captions": {
            "enabled": True,
            "words": [
                {
                    "text": w.text,
                    "start_ms": round(w.start_ms / speed),
                    "end_ms": round(w.end_ms / speed),
                }
                for w in words
            ],
        },
        "text": [],
        "stickers": [],
        "music": [],
    }
    edited = delete_source(timeline, "occurrence-1", cleanup.cuts)
    assert len(timeline["video"]) == 1  # original remains an undo snapshot
    assert [w["text"] for w in edited["captions"]["words"]] == [
        "Salom",
        "bugun",
        "demak",
        "boshlaymiz",
    ]
    assert cleanup.review[0].text == "demak"

    ass = output_dir / "captions.ass"
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,32,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,24,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass.write_text(
        header
        + "".join(
            f"Dialogue: 0,{ass_time(w['start_ms'])},{ass_time(w['end_ms'])},Default,,0,0,0,,{w['text']}\n"
            for w in edited["captions"]["words"]
        ),
        encoding="utf-8",
    )
    lut = output_dir / "identity.cube"
    lut.write_text(
        "LUT_3D_SIZE 2\n"
        + "".join(f"{r} {g} {b}\n" for b in (0, 1) for g in (0, 1) for r in (0, 1)),
        encoding="ascii",
    )
    segments = [
        Segment(source, clip["src_in_ms"], clip["src_out_ms"], clip["speed"])
        for clip in edited["video"]
    ]
    options = ExportOptions(ffmpeg=str(ffmpeg), ffprobe=str(ffprobe), overwrite=True)
    result = run_export(
        segments,
        ExportConfig(
            output_dir / "result.mp4",
            width=640,
            height=360,
            fps=30,
            encoder="h264_videotoolbox",
            ass_path=ass,
            lut_path=lut,
            fonts_dir=root / "engine/src/lahza_engine/subtitle/fonts",
            music=music,
            music_gain_db=-24,
            saturation=1.05,
        ),
        options=options,
    )
    info = probe_media(result.output, options)
    assert info.video and info.audio
    assert (info.video["width"], info.video["height"]) == (640, 360)
    assert abs(info.duration_s - result.duration_s) < 1 / 30 + 0.03
    report = {
        "cleanup": asdict(cleanup),
        "timeline": edited,
        "export": {
            "output": str(result.output),
            "encoder": result.encoder,
            "planned_seconds": result.duration_s,
            "actual_seconds": info.duration_s,
            "segments": len(segments),
        },
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["export"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
