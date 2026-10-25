"""`lahza` buyruq qatori (M1 CLI MVP va diagnostika).

    lahza serve --port 0 --token T      # Tauri sidecar rejimi
    lahza serve --discovery             # + <data_dir>/engine.json (Adobe plaginlari)
    lahza hw                            # apparat va daraja
    lahza bundle                        # katalogdan mos model to'plami
    lahza analyze VIDEO --project-dir D [--lite]
    lahza batch VIDEO... --out-dir D [--lite]   # partiyaviy tahlil (ketma-ket)
    lahza clips --project-dir D
    lahza export --project-dir D --clip ID --out OUT [--orthography new]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_serve(a: argparse.Namespace) -> int:
    # Ota jarayon watchdog'i eng boshida: ilova engine yuklanayotganda o'ldirilsa ham chiqamiz.
    a.server_slot = {}
    if a.parent_pid or a.watch_stdin:
        from lahza_engine.core import lifecycle

        def on_parent_lost(_reason: str) -> None:
            lifecycle.arm_hard_exit(a.shutdown_timeout)
            server = a.server_slot.get("server")
            if server is None:
                lifecycle.finish(0)  # server hali ishga tushmagan - yumshoq to'xtatadigan narsa yo'q
            server.should_exit = True  # main_loop har 0.1 s tekshiradi

        lifecycle.ParentWatchdog(on_parent_lost, parent_pid=a.parent_pid,
                                 watch_stdin=a.watch_stdin).start()

    import logging

    from lahza_engine import __version__
    from lahza_engine.api.app import create_app
    from lahza_engine.config import Settings
    from lahza_engine.core.discovery import Discovery, discovery_enabled, pick_discovery_port
    from lahza_engine.core.ipc import IpcServer, ipc_enabled
    from lahza_engine.core.llama_server import free_port
    from lahza_engine.core.logs import setup_file_logging

    settings = Settings()
    # M2-APP-11 / NFR-12: Logs/engine.log (aylanma, transkript matnisiz - NFR-02).
    setup_file_logging(settings.logs_dir)
    logging.getLogger("lahza_engine").info("engine %s ishga tushdi", __version__)
    use_discovery = discovery_enabled(getattr(a, "discovery", False))
    if a.port:
        port = a.port
    elif use_discovery:
        # UXP manifest `network.domains` portlarni oldindan sanaydi - qat'iy ro'yxat.
        port = pick_discovery_port()
        if port is None:
            print("Xato: Lahza engine uchun 47600, 47601 va 47602 portlarining hammasi band. "
                  "Boshqa Lahza engine ishlayotgan bo'lishi mumkin - uni yoping yoki portlarni "
                  "bo'shating.", file=sys.stderr, flush=True)
            return 2
    else:
        port = free_port()
    token = a.token or os.environ.get("LAHZA_TOKEN")
    discovery = None
    if use_discovery and not token:
        import secrets

        token = secrets.token_urlsafe(24)
    app = create_app(settings, token=token)
    if use_discovery and token:
        # Adobe plaginlari engine'ni shu fayl orqali topadi (docs/04 "Adobe plaginlari").
        discovery = Discovery(settings.data_dir, port, token, __version__)
        discovery.start()
        app.state.shutdown_hooks.append(discovery.stop)
    if token and ipc_enabled(use_discovery):
        # Fayl-IPC (`lahza.ipc/1`) - UXP'da HTTP ishlamasa zaxira transport.
        ipc = IpcServer(app, settings.data_dir)
        ipc.prepare()
        app.state.background.append(ipc.run)
    # Tauri shu qatorni o'qib portni biladi (app/src-tauri/src/engine.rs).
    print(f"LAHZA_READY port={port}", flush=True)
    cleanup = discovery.stop if discovery is not None else (lambda: None)
    _run_server(app, port, a, cleanup)  # haqiqiy serverda qaytmaydi (lifecycle.finish)
    cleanup()
    return 0


SERVE_HOST = "127.0.0.1"


def _run_server(app, port: int, a: argparse.Namespace, cleanup) -> None:  # type: ignore[no-untyped-def]
    """uvicorn + to'xtash himoyasi (docs/01 "Engine hayot sikli"); oxirida `os._exit`."""
    import uvicorn

    from lahza_engine.core import lifecycle

    class _Server(uvicorn.Server):
        def handle_exit(self, sig, frame) -> None:  # type: ignore[no-untyped-def]
            # SIGTERM/SIGINT: uvicorn `should_exit` + majburiy chiqish taymeri.
            lifecycle.arm_hard_exit(a.shutdown_timeout)
            super().handle_exit(sig, frame)

        async def shutdown(self, sockets=None) -> None:  # type: ignore[no-untyped-def]
            try:
                await super().shutdown(sockets=sockets)
            finally:
                # uvicorn signalni keyin qayta ko'taradi (raise_signal) - bola jarayonlar undan oldin.
                with contextlib.suppress(Exception):
                    cleanup()
                lifecycle.kill_descendants()

    # Uzilgan WebSocket (`/v1/events`) handler'ini cheksiz kutmaslik.
    config = uvicorn.Config(app, host=SERVE_HOST, port=port, log_level="warning",
                            timeout_graceful_shutdown=2)
    server = _Server(config)
    getattr(a, "server_slot", {})["server"] = server  # cmd_serve watchdog'i uchun
    code = 0
    try:
        server.run()
    except KeyboardInterrupt:
        code = 130
    finally:
        with contextlib.suppress(Exception):
            cleanup()
    # Og'ir vazifadagi ThreadPool oqimlari (non-daemon) interpreter chiqishini to'sadi -
    # kutmasdan, bola jarayonlarni o'ldirib chiqamiz.
    lifecycle.finish(code)


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


def _build_services(settings):
    from lahza_engine.core.services import build_services
    from lahza_engine.models.store import ModelStore

    return build_services(ModelStore(settings.models_dir))


def _analyze_one(settings, svc, src: Path, pdir: Path, media_id: str, lite: bool,
                 focus: str | None, prefix: str = "") -> dict:
    """Bitta video tahlili (`analyze` va `batch` buyruqlari uchun umumiy)."""
    from lahza_engine.core.analyze import analyze
    from lahza_engine.core.runner import StageContext
    from lahza_engine.db import store as db
    from lahza_engine.media.probe import fast_hash

    conn = db.open_project(pdir)
    try:
        ctx = StageContext(
            media_id=media_id, media_hash=fast_hash(src), project_dir=pdir, conn=conn,
            services={"src": str(src), "svc": svc, "force_lite": lite, "focus": focus},
            on_progress=lambda st, f: print(f"{prefix}[{f * 100:5.1f}%] {st}", file=sys.stderr, flush=True),
        )
        return analyze(ctx, settings)
    finally:
        conn.close()


def cmd_analyze(a: argparse.Namespace) -> int:
    from lahza_engine.config import Settings

    settings = Settings()
    res = _analyze_one(settings, _build_services(settings), Path(a.video), Path(a.project_dir),
                       a.media_id, a.lite, a.focus)
    _print({"mode": res["highlight"]["mode"], "clips": res["highlight"]["clips"]})
    return 0


def cmd_batch(a: argparse.Namespace) -> int:
    """Partiyaviy tahlil (PRO-5): videolar ketma-ket, har biri `<out-dir>/<nom>.lahza` ga.
    Bitta faylning xatosi qolganlarini to'xtatmaydi; Ctrl+C - qolganlari bekor qilinadi.
    Chiqish kodi: hammasi tayyor - 0, aks holda 1."""
    from lahza_engine.config import Settings

    settings = Settings()
    out = Path(a.out_dir)
    videos = [Path(v) for v in a.videos]
    items: list[dict] = []
    used: set[Path] = set()
    svc = None
    interrupted = False
    for i, src in enumerate(videos, 1):
        prefix = f"[{i}/{len(videos)}] "
        if interrupted:
            items.append({"video": str(src), "status": "cancelled"})
            continue
        pdir = out / f"{src.stem}.lahza"
        n = 2
        while pdir in used:
            pdir = out / f"{src.stem}-{n}.lahza"
            n += 1
        used.add(pdir)
        print(f"{prefix}{src.name}", file=sys.stderr, flush=True)
        if not src.is_file():
            items.append({"video": str(src), "status": "failed", "error": "fayl topilmadi"})
            continue
        try:
            if svc is None:
                svc = _build_services(settings)
            res = _analyze_one(settings, svc, src, pdir, a.media_id, a.lite, a.focus, prefix)
            items.append({"video": str(src), "project_dir": str(pdir), "status": "done",
                          "mode": res["highlight"]["mode"], "clips": len(res["highlight"]["clips"])})
        except KeyboardInterrupt:
            interrupted = True
            items.append({"video": str(src), "project_dir": str(pdir), "status": "cancelled"})
        except Exception as e:  # noqa: BLE001 - xato hisobotga yoziladi, navbat davom etadi
            items.append({"video": str(src), "project_dir": str(pdir), "status": "failed",
                          "error": str(e) or type(e).__name__})
            print(f"{prefix}xato: {type(e).__name__}", file=sys.stderr, flush=True)
    counts = {k: sum(1 for x in items if x["status"] == k) for k in ("done", "failed", "cancelled")}
    _print({"items": items, **counts})
    return 0 if counts["done"] == len(items) else 1


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
    s.add_argument("--discovery", action="store_true",
                   help="<data_dir>/engine.json yozish (Adobe plaginlari uchun; LAHZA_DISCOVERY=1)")
    s.add_argument("--parent-pid", type=int, default=None,
                   help="ota jarayon (Tauri) pid'i: u o'lsa engine o'zini to'xtatadi")
    s.add_argument("--watch-stdin", action="store_true",
                   help="stdin EOF bo'lsa (ota jarayon yopildi) engine o'zini to'xtatadi")
    s.add_argument("--shutdown-timeout", type=float, default=5.0,
                   help="yumshoq to'xtashdan keyin majburiy chiqishgacha soniya")
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

    ba = sub.add_parser("batch", help="bir nechta videoni ketma-ket tahlil qilish")
    ba.add_argument("videos", nargs="+")
    ba.add_argument("--out-dir", required=True, help="har video uchun <nom>.lahza papkasi shu yerda")
    ba.add_argument("--media-id", default="m1")
    ba.add_argument("--lite", action="store_true", help="LLM'siz (signal + qoidalar)")
    ba.add_argument("--focus", help="ustuvor mavzu")
    ba.set_defaults(fn=cmd_batch)

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
