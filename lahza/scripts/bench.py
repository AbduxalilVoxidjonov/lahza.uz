"""M3-PERF-1: tahlil tezligi benchmarki - bosqichlar bo'yicha vaqt va TZ 2-bo'lim maqsadi.

    engine/.venv/bin/python scripts/bench.py --minutes 10            # sintetik nutqli video
    engine/.venv/bin/python scripts/bench.py --video /abs/podcast.mp4 --out build/bench.json
    make bench BENCH_ARGS="--minutes 60"

O'rnatilgan modellar (Settings().models_dir) ishlatiladi, hech narsa yuklanmaydi. Bosqichlar:
dekod (ffmpeg -> 16 kHz WAV), proksi, VAD, ASR, align, diarize, highlight (LLM yoki lite) va
bitta klip render (eksport). Model o'rnatilmagan bosqich "o'lchanmadi" deb belgilanadi.

Sintetik video (`--minutes`): macOS `say` (tr_TR ovozi) o'zbekcha lotin matnni o'qiydi, video -
1920x1080 testsrc2. Bu tezlik o'lchovi uchun; ASR sifati (WER) baholanmaydi.
Natija 60 daqiqaga chiziqli ekstrapolyatsiya qilinadi (`--target-minutes`) va apparat
darajasining maqsadi bilan solishtiriladi.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# TZ 2-bo'lim jadvali: "Maqsad: 60 daq video tahlili" (daqiqa). ANIQLANSIN - R0 dan keyin.
TIER_TARGET_MIN = {"lite": 60.0, "standard": 20.0, "pro": 10.0}

SAY_TEXT = (
    "Assalomu alaykum, aziz tinglovchilar. Bugun biz podkastimizda sun'iy intellekt va uning "
    "o'zbek tilidagi kontentga ta'siri haqida gaplashamiz. Mehmonimiz ko'p yillardan beri "
    "dasturlash bilan shug'ullanadi. Birinchi savol: nima uchun mahalliy modellar muhim? "
    "Chunki ma'lumotlar foydalanuvchi kompyuteridan chiqmasligi kerak. Ikkinchidan, internet "
    "har doim ham tez emas. Keling, endi amaliy misollarga o'tamiz. Masalan, bir soatlik "
    "suhbatdan eng qiziqarli lahzalarni topish uchun avval nutq matnga aylantiriladi, keyin "
    "har bir gap baholanadi. Bu juda qiziq, lekin qiyin vazifa. Rahmat, davom etamiz."
)


def _run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]}: {r.stderr[-400:]}")


def synth_video(dst: Path, minutes: float, ffmpeg: str, size: str = "1920x1080",
                fps: int = 30) -> Path:
    """`say` bilan nutq (pauzalar bilan) + testsrc2 video, `minutes` uzunlikda."""
    say = shutil.which("say")
    if say is None:
        raise SystemExit("--minutes faqat macOS `say` bilan; boshqa tizimda --video bering")
    work = dst.parent
    aiff = work / "speech.aiff"
    _run([say, "-v", "Yelda", "-r", "170", "-o", str(aiff), SAY_TEXT])
    # Nutq + 1.5 s jimlik -> bitta "segment", keyin takrorlanadi.
    seg = work / "segment.wav"
    _run([ffmpeg, "-v", "error", "-y", "-i", str(aiff), "-af", "apad=pad_dur=1.5",
          "-ar", "48000", "-ac", "2", str(seg)])
    secs = int(minutes * 60)
    _run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={size}:r={fps}:d={secs}",
          "-stream_loop", "-1", "-i", str(seg), "-t", str(secs), "-map", "0:v", "-map", "1:a",
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-g", str(fps * 2),
          "-c:a", "aac", "-b:a", "128k", str(dst)])
    return dst


def hardware() -> dict[str, Any]:
    from lahza_engine.models.hardware import classify, detect

    hw = detect(tempfile.gettempdir())
    dec = classify(hw)
    return {"cpu": hw.cpu, "ram_gb": hw.ram_gb, "os": hw.os,
            "os_version": platform.mac_ver()[0] or hw.os_version, "arch": hw.arch,
            "gpus": [g.name for g in hw.gpus], "cores": os.cpu_count(),
            "tier": dec.tier.value, "tier_reasons": dec.reasons}


def bench(src: Path, work: Path, lite: bool, render: bool) -> dict[str, Any]:
    from lahza_engine.config import Settings
    from lahza_engine.core import analyze as an
    from lahza_engine.core.runner import StageContext, run_stages
    from lahza_engine.core.services import build_services
    from lahza_engine.db import store as db
    from lahza_engine.media.probe import fast_hash, probe
    from lahza_engine.models.store import ModelStore

    settings = Settings()
    t = time.perf_counter()
    svc = build_services(ModelStore(settings.models_dir))
    load_s = time.perf_counter() - t
    if svc.asr is None:
        raise SystemExit("ASR modeli o'rnatilmagan - benchmark o'tkazilmaydi")

    times: dict[str, float] = {}

    def timed(name: str, fn):  # type: ignore[no-untyped-def]
        def inner(*a, **kw):  # type: ignore[no-untyped-def]
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                times[name] = times.get(name, 0.0) + time.perf_counter() - t0
        return inner

    # Ingest ichidagi dekod va proksi alohida o'lchanadi.
    an.extract_wav = timed("decode", an.extract_wav)
    an.make_proxy = timed("proxy", an.make_proxy)
    stages = an.analysis_stages(settings)
    for sd in stages:
        sd.fn = timed(sd.name, sd.fn)

    info = probe(src)
    pdir = work / "bench.lahza"
    conn = db.open_project(pdir)
    try:
        ctx = StageContext("bench", fast_hash(src), pdir, conn,
                           services={"src": str(src), "svc": svc, "force_lite": lite,
                                     "settings": settings})
        t0 = time.perf_counter()
        res = run_stages(stages, ctx)
        total = time.perf_counter() - t0
        tr = db.load_transcript(conn, "bench")
        clips = db.load_clips(conn, "bench")
        render_res = _render(conn, clips, work, settings, svc) if render and clips else None
    finally:
        conn.close()

    methods = {
        "vad": res["vad"].get("method"),
        "asr": svc.asr_model_id,
        "align": res["align"].get("method"),
        "diarize": res["diarize"].get("method"),
        "highlight": res["highlight"].get("mode"),
    }
    not_measured = []
    if methods["align"] in (None, "asr-timestamps"):
        not_measured.append("align: CTC aligner o'rnatilmagan - ASR vaqtlari ishlatildi")
    if methods["diarize"] == "none":
        not_measured.append("diarize: diarizatsiya modeli o'rnatilmagan")
    if methods["highlight"] != "llm":
        not_measured.append("highlight LLM: o'chirilgan yoki LLM o'rnatilmagan (lite rejim)")
    if methods["vad"] == "energy":
        not_measured.append("VAD: Silero o'rnatilmagan - energiya VAD o'lchandi")
    return {
        "media": {"path": src.name, "duration_s": round(info.duration_ms / 1000, 1),
                  "width": info.width, "height": info.height, "fps": info.fps},
        "service_load_s": round(load_s, 2),
        "stage_s": {k: round(v, 2) for k, v in times.items()},
        "analysis_total_s": round(total, 2),
        "methods": methods, "llm_model": svc.llm_model_id if methods["highlight"] == "llm" else None,
        "words": sum(len(s.words) for s in tr.sentences), "sentences": len(tr.sentences),
        "clips": len(clips), "render": render_res, "not_measured": not_measured,
    }


def _render(conn, clips, work: Path, settings, svc) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    from lahza_engine.core.export import export_clip
    from lahza_engine.media.tools import find_tool
    from lahza_engine.render.capabilities import has_filter
    from lahza_engine.render.encoders import choose_encoder
    from lahza_engine.subtitle.fonts import list_fonts
    from lahza_engine.subtitle.style import StyleTemplate

    ffmpeg = find_tool("ffmpeg")
    enc = choose_encoder(ffmpeg, None, settings.render.video_bitrate_kbps, allow_dev_fallback=True)
    fonts = [f for f in list_fonts() if f.ok]
    style = StyleTemplate(font_family=fonts[0].family) if fonts else StyleTemplate()
    clip = clips[0]
    t0 = time.perf_counter()
    res = export_clip(conn, "bench", clip, work / "export", work / "render-work", settings, enc,
                      style, detector=svc.face_detector, allow_no_subs=True)
    dt = time.perf_counter() - t0
    clip_s = (clip.end_ms - clip.start_ms) / 1000
    return {"encoder": enc.name, "libass": has_filter(str(ffmpeg), "ass"), "clip_s": round(clip_s, 1),
            "render_s": round(dt, 2), "speed_x": round(clip_s / dt, 2) if dt else None,
            "face_detector": type(svc.face_detector).__name__ if svc.face_detector else None,
            "warnings": res.warnings}


def compare(result: dict[str, Any], hw: dict[str, Any], target_minutes: float) -> dict[str, Any]:
    dur_min = result["media"]["duration_s"] / 60
    scale = target_minutes / dur_min if dur_min else 0.0
    est = result["analysis_total_s"] * scale / 60
    tgt = TIER_TARGET_MIN.get(hw["tier"])
    return {"target_minutes_video": target_minutes, "scale": round(scale, 2),
            "estimated_analysis_min": round(est, 1), "tier": hw["tier"], "tier_target_min": tgt,
            "rtf": round(result["analysis_total_s"] / (dur_min * 60), 4) if dur_min else None,
            "meets_target": None if tgt is None else est <= tgt}


def markdown(rep: dict[str, Any]) -> str:
    r, c, hw = rep["result"], rep["comparison"], rep["hardware"]
    dur = r["media"]["duration_s"]
    rows = ["| Bosqich | Vaqt, s | RTF | Usul / izoh |", "| --- | ---: | ---: | --- |"]
    labels = [("decode", "Dekod (16 kHz WAV)", ""), ("proxy", "Proksi (540p)", ""),
              ("vad", "VAD", r["methods"]["vad"]), ("asr", "ASR", r["methods"]["asr"]),
              ("align", "Align", r["methods"]["align"]), ("diarize", "Diarize", r["methods"]["diarize"]),
              ("signals", "Signallar", ""),
              ("highlight", "Highlight", f"{r['methods']['highlight']} {r['llm_model'] or ''}".strip())]
    for key, name, note in labels:
        v = r["stage_s"].get(key)
        rows.append(f"| {name} | {v:.1f} | {v / dur:.3f} | {note} |" if v is not None
                    else f"| {name} | - | - | o'lchanmadi |")
    rows.append(f"| **Tahlil jami** | **{r['analysis_total_s']:.1f}** | "
                f"**{r['analysis_total_s'] / dur:.3f}** | {dur / 60:.1f} daq video |")
    if r["render"]:
        rd = r["render"]
        rows.append(f"| Render (1 klip, {rd['clip_s']:.0f} s) | {rd['render_s']:.1f} | - | "
                    f"{rd['encoder']}, {rd['speed_x']}x real vaqt, libass={rd['libass']} |")
    head = (f"Apparat: {hw['cpu']}, {hw['ram_gb']:.0f} GB, macOS {hw['os_version']} - daraja "
            f"**{hw['tier']}** (maqsad <= {c['tier_target_min']} daq / 60 daq video). "
            f"Ekstrapolyatsiya: {c['target_minutes_video']:.0f} daq video ~ "
            f"**{c['estimated_analysis_min']} daq** -> "
            f"{'maqsadga sig`adi' if c['meets_target'] else 'maqsaddan oshadi'}.")
    return head + "\n\n" + "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--video", type=Path, help="haqiqiy video (absolut yo'l)")
    src.add_argument("--minutes", type=float, default=10.0, help="sintetik video uzunligi")
    ap.add_argument("--target-minutes", type=float, default=60.0)
    ap.add_argument("--lite", action="store_true", help="LLM'siz (lite highlight)")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--out", type=Path, help="JSON hisobot yo'li")
    ap.add_argument("--keep", action="store_true", help="vaqtinchalik papkani o'chirmaslik")
    args = ap.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    bundled = ROOT / "app" / "src-tauri" / "resources" / "bin"
    if "LAHZA_BIN_DIR" not in os.environ and (bundled / "ffmpeg").is_file():
        os.environ["LAHZA_BIN_DIR"] = str(bundled)

    from lahza_engine.media.tools import find_tool

    work = Path(tempfile.mkdtemp(prefix="lahza-bench-"))
    try:
        if args.video:
            video = args.video.expanduser().resolve(strict=True)
            synth_s = None
        else:
            t0 = time.perf_counter()
            # Sintez uchun libx264'li tizim ffmpeg'i (yetkaziladigan ffmpeg'da libx264 bo'lmasligi mumkin).
            synth_ff = shutil.which("ffmpeg") or str(find_tool("ffmpeg"))
            video = synth_video(work / "bench.mp4", args.minutes, synth_ff)
            synth_s = round(time.perf_counter() - t0, 1)
        hw = hardware()
        result = bench(video, work, args.lite, not args.no_render)
        rep = {"date": datetime.now().date().isoformat(), "hardware": hw,
               "input": "real" if args.video else f"synthetic say(Yelda)+testsrc2, synth {synth_s}s",
               "bin_dir": os.environ.get("LAHZA_BIN_DIR"), "python": sys.version.split()[0],
               "result": result, "comparison": compare(result, hw, args.target_minutes)}
        rep["markdown"] = markdown(rep)
        text = json.dumps(rep, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text)
        print("\n" + rep["markdown"])
    finally:
        if args.keep:
            print(f"vaqtinchalik papka saqlandi: {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
