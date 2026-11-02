"""O'rnatilgan haqiqiy ASR bilan video -> klip -> subtitrli MP4 sinovi.

    engine/.venv/bin/python scripts/smoke_local.py --video /absolute/podcast.mp4

Model yuklamaydi. Natijalar build/local-smoke/ ichida qoladi. Sintetik nutq ishlatilsa
--sample-kind synthetic deb belgilang; bunday sinov o'zbekcha sifat bahosi emas.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("build/local-smoke"))
    ap.add_argument("--resume", type=Path, help="oldingi sinov papkasi; mos tahlil keshidan foydalanadi")
    ap.add_argument("--sample-kind", choices=("real", "synthetic"), default="real")
    args = ap.parse_args()
    # O'rnatilgan lokal model ishlatiladi: HF hech narsani avtomatik yuklamaydi.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    from lahza_engine.config import Settings
    from lahza_engine.core.analyze import analyze
    from lahza_engine.core.export import export_clip
    from lahza_engine.core.runner import StageContext
    from lahza_engine.core.services import build_services
    from lahza_engine.db import store as db
    from lahza_engine.media.probe import fast_hash, probe
    from lahza_engine.media.tools import find_tool, run
    from lahza_engine.models.store import ModelStore
    from lahza_engine.render.capabilities import has_filter
    from lahza_engine.render.encoders import choose_encoder
    from lahza_engine.subtitle.fonts import list_fonts
    from lahza_engine.subtitle.style import StyleTemplate

    src = args.video.expanduser().resolve(strict=True)
    settings = Settings(**({"data_dir": args.data_dir.expanduser().resolve()} if args.data_dir else {}))
    ffmpeg = find_tool("ffmpeg")
    if not has_filter(str(ffmpeg), "ass"):
        raise RuntimeError("FFmpeg ass filtri yo'q: avval lokal render muhitini sozlang")
    fonts = [f for f in list_fonts() if f.ok]
    if not fonts:
        raise RuntimeError("O'zbekcha gliflari to'liq shrift topilmadi")
    svc = build_services(ModelStore(settings.models_dir))
    if svc.asr is None:
        raise RuntimeError("ASR o'rnatilmagan: avval lokal modelni sozlang")
    encoder = choose_encoder(ffmpeg, None, settings.render.video_bitrate_kbps)
    if args.resume:
        root = args.resume.expanduser().resolve(strict=True)
        if not (root / "episode.lahza" / "project.db").is_file():
            raise ValueError("Oldingi sinov project.db fayli topilmadi")
    else:
        root = args.out.expanduser().resolve() / uuid.uuid4().hex[:12]
        root.mkdir(parents=True)
    conn = db.open_project(root / "episode.lahza")
    started = time.monotonic()
    try:
        ctx = StageContext(
            "smoke", fast_hash(src), root / "episode.lahza", conn,
            services={"src": str(src), "svc": svc, "force_lite": True},
            on_progress=lambda stage, frac: print(f"{stage}: {frac:.0%}", flush=True),
        )
        analyze(ctx, settings)
        transcript = db.load_transcript(conn, "smoke")
        word_count = sum(len(s.words) for s in transcript.sentences)
        clips = db.load_clips(conn, "smoke")
        (root / "transcript.json").write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
        (root / "clips.json").write_text(
            json.dumps([c.model_dump(mode="json") for c in clips], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if word_count == 0 or not clips:
            raise RuntimeError(f"Tahlilda {word_count} so'z va {len(clips)} klip: sinov o'tmadi")
        result = export_clip(
            conn, "smoke", clips[0], root / "export", root / "work", settings, encoder,
            StyleTemplate(font_family=fonts[0].family), detector=svc.face_detector,
            show_name="Lokal sinov", episode="01",
        )
        info = probe(result.video)
        if (info.width, info.height) != (1080, 1920):
            raise RuntimeError("Natija o'lchami 1080x1920 emas")
        if not result.srt.read_text(encoding="utf-8").strip():
            raise RuntimeError("SRT bo'sh")
        streams = run([find_tool("ffprobe"), "-v", "error", "-show_streams", "-of", "json", result.video])
        if streams.returncode:
            raise RuntimeError(streams.stderr)
        data = json.loads(streams.stdout)["streams"]
        audio = next(s for s in data if s["codec_type"] == "audio")
        video = next(s for s in data if s["codec_type"] == "video")
        delta = abs(float(video["duration"]) - float(audio["duration"]))
        if delta > 0.25:
            raise RuntimeError(f"Video/ovoz davomiyligi farqi {delta:.3f} soniya")
        from lahza_engine.timeline import Timeline

        expected_ms = Timeline(clips[0].start_ms, clips[0].end_ms, clips[0].cuts).duration_ms
        if abs(info.duration_ms - expected_ms) > 250:
            raise RuntimeError("Eksport davomiyligi tanlangan klipga mos emas")
        report = {
            "sample_kind": args.sample_kind,
            "resumed": bool(args.resume),
            "quality_evaluated": False,
            "asr_model": svc.asr_model_id,
            "words": word_count, "clips": len(clips),
            "elapsed_s": round(time.monotonic() - started, 2),
            "encoder": encoder.name, "font": fonts[0].family,
            "video": str(result.video), "srt": str(result.srt),
            "transcript": str(root / "transcript.json"),
            "width": info.width, "height": info.height, "av_delta_s": delta,
            "warnings": result.warnings,
        }
        (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
