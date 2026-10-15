"""`lahza` buyruq qatori (M1 CLI MVP va diagnostika).

    lahza serve --port 0 --token T      # Tauri sidecar rejimi
    lahza hw                            # apparat va daraja
    lahza bundle                        # katalogdan mos model to'plami
    lahza analyze VIDEO --project-dir D [--lite]
    lahza clips --project-dir D
    lahza export --project-dir D --clip ID --out OUT [--orthography new]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_serve(a: argparse.Namespace) -> int:
    import logging

    import uvicorn

    from lahza_engine import __version__
    from lahza_engine.api.app import create_app
    from lahza_engine.config import Settings
    from lahza_engine.core.llama_server import free_port
    from lahza_engine.core.logs import setup_file_logging

    settings = Settings()
    # M2-APP-11 / NFR-12: Logs/engine.log (aylanma, transkript matnisiz - NFR-02).
    setup_file_logging(settings.logs_dir)
    logging.getLogger("lahza_engine").info("engine %s ishga tushdi", __version__)
    port = a.port or free_port()
    token = a.token or os.environ.get("LAHZA_TOKEN")
    app = create_app(settings, token=token)
    # Tauri shu qatorni o'qib portni biladi (app/src-tauri/src/engine.rs).
    print(f"LAHZA_READY port={port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


def cmd_hw(a: argparse.Namespace) -> int:
    from lahza_engine.models.hardware import classify, detect

    hw = detect()
    d = classify(hw)
    _print({"profile": hw.to_dict(), "tier": d.tier, "reasons": d.reasons})
    return 0


def cmd_bundle(a: argparse.Namespace) -> int:
    from lahza_engine.models import catalog as cat
    from lahza_engine.models.hardware import classify, detect

    hw = detect()
    tier = classify(hw).tier
    items = cat.select_bundle(cat.load_catalog(a.catalog), hw, tier)
    _print({"tier": tier, "items": [i.model_dump(mode="json") for i in items]})
    return 0


def cmd_analyze(a: argparse.Namespace) -> int:
    from lahza_engine.config import Settings
    from lahza_engine.core.analyze import analyze
    from lahza_engine.core.runner import StageContext
    from lahza_engine.core.services import build_services
    from lahza_engine.db import store as db
    from lahza_engine.media.probe import fast_hash
    from lahza_engine.models.store import ModelStore

    settings = Settings()
    src = Path(a.video)
    pdir = Path(a.project_dir)
    conn = db.open_project(pdir)
    svc = build_services(ModelStore(settings.models_dir))
    ctx = StageContext(
        media_id=a.media_id, media_hash=fast_hash(src), project_dir=pdir, conn=conn,
        services={"src": str(src), "svc": svc, "force_lite": a.lite, "focus": a.focus},
        on_progress=lambda st, f: print(f"[{f * 100:5.1f}%] {st}", file=sys.stderr, flush=True),
    )
    res = analyze(ctx, settings)
    _print({"mode": res["highlight"]["mode"], "clips": res["highlight"]["clips"]})
    return 0


def cmd_clips(a: argparse.Namespace) -> int:
    from lahza_engine.db import store as db

    conn = db.open_project(Path(a.project_dir))
    _print([c.model_dump(mode="json") for c in db.load_clips(conn, a.media_id)])
    return 0


def cmd_export(a: argparse.Namespace) -> int:
    from lahza_engine.config import Settings
    from lahza_engine.core.export import export_clip
    from lahza_engine.db import store as db
    from lahza_engine.media.tools import find_tool
    from lahza_engine.models.hardware import detect
    from lahza_engine.render.encoders import choose_encoder
    from lahza_engine.subtitle.style import StyleTemplate
    from lahza_engine.text.orthography import Orthography

    settings = Settings()
    pdir = Path(a.project_dir)
    conn = db.open_project(pdir)
    clip = next(c for c in db.load_clips(conn, a.media_id) if c.id == a.clip)
    gpu = detect().best_gpu()
    enc = choose_encoder(find_tool("ffmpeg"), gpu.vendor if gpu else None,
                         settings.render.video_bitrate_kbps, allow_dev_fallback=a.dev_encoder)
    style = StyleTemplate(orthography=Orthography(a.orthography))
    res = export_clip(conn, a.media_id, clip, Path(a.out), pdir / "work" / clip.id, settings, enc, style)
    _print({"video": res.video, "srt": res.srt, "caption": res.caption, "cover": res.cover,
            "encoder": enc.name})
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lahza")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--token")
    s.set_defaults(fn=cmd_serve)

    sub.add_parser("hw").set_defaults(fn=cmd_hw)

    b = sub.add_parser("bundle")
    b.add_argument("--catalog", default=os.environ.get("LAHZA_CATALOG", "catalog/catalog.json"))
    b.set_defaults(fn=cmd_bundle)

    an = sub.add_parser("analyze")
    an.add_argument("video")
    an.add_argument("--project-dir", required=True)
    an.add_argument("--media-id", default="m1")
    an.add_argument("--lite", action="store_true", help="LLM'siz (signal + qoidalar)")
    an.add_argument("--focus", help="ustuvor mavzu")
    an.set_defaults(fn=cmd_analyze)

    c = sub.add_parser("clips")
    c.add_argument("--project-dir", required=True)
    c.add_argument("--media-id", default="m1")
    c.set_defaults(fn=cmd_clips)

    e = sub.add_parser("export")
    e.add_argument("--project-dir", required=True)
    e.add_argument("--media-id", default="m1")
    e.add_argument("--clip", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--orthography", default="official", choices=["official", "ascii", "new"])
    e.add_argument("--dev-encoder", action="store_true", help="dasturchi muhiti: libx264/mpeg4 zaxirasi")
    e.set_defaults(fn=cmd_export)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
