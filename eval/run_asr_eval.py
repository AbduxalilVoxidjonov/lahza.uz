"""ASR baholash: WER, CER, RTF, so'z/daq, "cho'zilgan so'zlar" - haqiqiy engine pipeline orqali.

Asosiy (takrorlanuvchi benchmark, FLEURS uz test; to'plam birinchi marta o'zi yuklanadi):

    engine/.venv/bin/python -I eval/run_asr_eval.py --set fleurs-uz --model base
    engine/.venv/bin/python -I eval/run_asr_eval.py --set fleurs-uz --model small
    engine/.venv/bin/python -I eval/run_asr_eval.py --table build/asr-eval/results-*.json
    make asr-eval            # ikkalasi + jadval

O'z ma'lumotlarimiz (<id>.wav + <id>.txt, YORIQNOMA.md):

    ... run_asr_eval.py --data eval/data/uzpodcast --engine-asr --model base
    ... run_asr_eval.py --data eval/data/uzpodcast --hyp-dir out/ --model-id asr-x

--model: `base` | `small` | o'rnatilgan model ID (custom:...) | CTranslate2 papkasi (model.bin).
Har fayl engine bosqichlaridan o'tadi: core.analyze.stage_vad -> stage_asr (plan_chunks, ffmpeg
bo'laklari, transcribe_chunk, dedupe_overlaps, transcript_density) -> stage_normalize. Kod
nusxalanmaydi; foydalanuvchi model ombori o'zgartirilmaydi (vaqtinchalik ombor quriladi).
Natijada o'lchangan kod holati ("code_state") qayd etiladi - keyin qayta o'lchab solishtirish uchun.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from lahza_engine.eval_metrics import edit_distance, normalize_for_wer

REPO = Path(__file__).resolve().parents[1]
ENGINE_PKG = REPO / "engine" / "src" / "lahza_engine"
ALIASES = {"base": "custom:navai-whisper-base-uzbek", "small": "custom:navai-whisper-small-uzbek"}
_TAGS = re.compile(r"\[[^\]]*\]|\{[a-z]{2}\}")
_SPK = re.compile(r"^\s*\[[A-Z]\]\s*", flags=re.M)


def clean_reference(text: str) -> str:
    return _TAGS.sub(" ", _SPK.sub("", text))


def align_ops(ref: list[str], hyp: list[str]) -> dict[str, int]:
    """Levenshtein: almashtirish / tushib qolish / qo'shilish soni (WER tarkibi)."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    s = de = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            s += ref[i - 1] != hyp[j - 1]
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            de += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return {"sub": s, "del": de, "ins": ins}


# --- model / servislar ---------------------------------------------------------------------------

def build_eval_services(model: str, aligner: Path | None = None) -> tuple[Any, dict[str, Any]]:
    """Engine build_services() ni vaqtinchalik omborda chaqiradi: tanlangan ASR + foydalanuvchining
    standart VAD va ALIGN modeli (yoki `aligner` papkasi). Aligner bor-yo'qligi stage_asr rejimini
    belgilaydi (AsrOptions.timestamps). Foydalanuvchi `installed.json` iga yozilmaydi."""
    from lahza_engine.config import Settings
    from lahza_engine.core.services import _align_model, build_services
    from lahza_engine.models.catalog import Task
    from lahza_engine.models.store import InstalledModel, ModelStore

    user = ModelStore(Settings().models_dir)
    mid = ALIASES.get(model, model)
    p = Path(model).expanduser()
    if (p / "model.bin").exists():
        asr = InstalledModel(id=f"path:{p.resolve().name}", task=Task.ASR, version="local",
                             path=str(p.resolve()), source="custom")
    else:
        asr = user.get(mid)
        if asr is None or asr.task != Task.ASR:
            raise SystemExit(f"ASR modeli topilmadi: {model} (o'rnatilganlar: "
                             f"{[m.id for m in user.load().models if m.task == Task.ASR]})")
    vad = user.default_for(Task.VAD)
    align = _align_model(user)
    if aligner is not None:
        align = InstalledModel(id=f"path:{aligner.resolve().name}", task=Task.ALIGN, version="local",
                               path=str(aligner.resolve()), source="custom")
    tmp = Path(tempfile.mkdtemp(prefix="lahza-asr-eval-store-"))
    store = ModelStore(tmp)
    store.register([asr] + ([vad] if vad else []) + ([align] if align else []))
    store.set_default(Task.ASR, asr.id)
    if align:
        store.set_default(Task.ALIGN, align.id)
    svc = build_services(store)
    if svc.asr is None:
        raise SystemExit(f"ASR backend qurilmadi: {asr.path}")
    info = {"id": asr.id, "path": asr.path, "version": asr.version,
            "model_bin_sha256": _sha256(Path(asr.path) / "model.bin"),
            "backend": type(svc.asr).__name__,
            "vad_model": vad.id if vad else None,
            "align_model": align.id if align and svc.aligner is not None else None}
    return svc, info


# --- kod holati ----------------------------------------------------------------------------------

def _sha256(p: Path) -> str | None:
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _defaults(fn: Any) -> dict[str, Any]:
    return {k: v.default for k, v in inspect.signature(fn).parameters.items()
            if v.default is not inspect.Parameter.empty and isinstance(v.default, int | float | str | bool)}


def apply_overrides(svc: Any, a: argparse.Namespace) -> dict[str, Any]:
    """Ablyatsiya: engine kodiga tegmasdan, faqat shu jarayonda parametrlarni almashtirish.

    * --vad-pad-ms / --vad-min-silence-ms - qurilgan SileroOnnxVad nusxasining atributlari;
    * --temperature - stage_asr yaratadigan AsrOptions standarti (`fallback` = faster-whisper'ning
      eski (0.0, 0.2, ..., 1.0) zanjiri);
    * --no-gain-norm - stage_asr dagi asr/preprocess.normalize_wav_file o'chiriladi.
    """
    import functools

    from lahza_engine.core import analyze

    applied: dict[str, Any] = {}
    for opt, attr in (("vad_pad_ms", "pad_ms"), ("vad_min_silence_ms", "min_silence_ms")):
        v = getattr(a, opt)
        if v is not None:
            if svc.vad is None or not hasattr(svc.vad, attr):
                raise SystemExit(f"--{opt.replace('_', '-')}: VAD'da {attr} yo'q")
            setattr(svc.vad, attr, v)
            applied[attr] = v
    if a.temperature is not None:
        t: Any = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) if a.temperature == "fallback" else float(a.temperature)
        analyze.AsrOptions = functools.partial(analyze.AsrOptions, temperature=t)
        applied["temperature"] = t
    if a.no_gain_norm:
        if not hasattr(analyze, "normalize_wav_file"):
            raise SystemExit("--no-gain-norm: core.analyze da normalize_wav_file yo'q")
        analyze.normalize_wav_file = lambda *_a, **_k: None
        applied["gain_norm"] = False
    return applied


def code_state(svc: Any) -> dict[str, Any]:
    import ctranslate2
    import faster_whisper
    import onnxruntime
    from lahza_engine.asr import base as asr_base
    from lahza_engine.asr import faster_whisper_backend as fwb
    from lahza_engine.vad import silero_onnx

    tree = hashlib.sha256()
    for f in sorted(ENGINE_PKG.rglob("*.py")):
        tree.update(str(f.relative_to(ENGINE_PKG)).encode() + b"\0" + f.read_bytes())
    key_files = ["vad/silero_onnx.py", "vad/energy.py", "asr/base.py", "asr/faster_whisper_backend.py",
                 "core/analyze.py", "core/services.py", "text/orthography.py", "eval_metrics.py"]
    fw_src = inspect.getsource(fwb)
    decode_lines = [ln.strip() for ln in fw_src.splitlines()
                    if re.search(r"temperature|beam_size|best_of|no_repeat|repetition_penalty|"
                                 r"condition_on_previous_text|compression_ratio|log_prob|no_speech|"
                                 r"hallucination|patience", ln)]
    vad_runtime = None
    if svc.vad is not None:
        vad_runtime = {"class": type(svc.vad).__name__,
                       **{k: v for k, v in vars(svc.vad).items() if isinstance(v, int | float | str | bool)}}
    return {
        "git_head": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "engine_dirty_files": [ln[3:] for ln in _git("status", "--porcelain", "--", "engine/src").splitlines()],
        "engine_tree_sha256": tree.hexdigest(),
        "file_sha256": {k: _sha256(ENGINE_PKG / k) for k in key_files},
        "vad_silero_defaults": _defaults(silero_onnx.SileroOnnxVad.__init__),
        "vad_runtime": vad_runtime,
        "plan_chunks_defaults": _defaults(asr_base.plan_chunks),
        "asr_options_defaults": {k: v for k, v in vars(asr_base.AsrOptions()).items() if k != "hotwords"},
        "ASR_TARGET_CHUNK_MS": getattr(asr_base, "ASR_TARGET_CHUNK_MS", None),
        "MAX_CHUNK_MS": getattr(asr_base, "MAX_CHUNK_MS", None),
        "SPARSE_WPM": getattr(asr_base, "SPARSE_WPM", None),
        "decoder_has_temperature": "temperature" in fw_src,
        "decoder_kwargs_lines": decode_lines,
        "aligner_loaded": svc.aligner is not None,  # stage_asr rejimi: bor -> "ctc", yo'q -> "whisper"
        "versions": {"python": platform.python_version(), "faster_whisper": faster_whisper.__version__,
                     "ctranslate2": ctranslate2.__version__, "onnxruntime": onnxruntime.__version__},
        "machine": {"platform": platform.platform(), "processor": platform.processor(),
                    "cpu_count": os.cpu_count()},
    }


# --- pipeline ------------------------------------------------------------------------------------

def run_pipeline(svc: Any, wav: Path) -> tuple[str, dict[str, Any], float]:
    """stage_vad -> stage_asr -> stage_normalize (core/analyze.py), sof soat vaqti bilan."""
    from lahza_engine.core.analyze import stage_asr, stage_normalize, stage_vad
    from lahza_engine.core.runner import StageContext

    with tempfile.TemporaryDirectory() as td:
        ctx = StageContext(media_id=wav.stem, media_hash="eval", project_dir=Path(td),
                           conn=sqlite3.connect(":memory:"),
                           services={"svc": svc, "progress": lambda _f: None})
        ctx.results["ingest"] = {"wav": str(wav)}
        t0 = time.perf_counter()
        ctx.results["vad"] = stage_vad(ctx)
        ctx.results["asr"] = stage_asr(ctx)
        ctx.results["normalize"] = stage_normalize(ctx)
        elapsed = time.perf_counter() - t0
        ctx.conn.close()
    words = ctx.results["normalize"]["words"]
    asr = ctx.results["asr"]
    words_raw = asr["words"]
    diag = {"vad_method": ctx.results["vad"].get("method"), "vad_segments": len(ctx.results["vad"]["speech"]),
            "chunks": asr["chunks"], "density": asr["density"],
            "longest_words": sorted(({"text": w["text"], "ms": w["end_ms"] - w["start_ms"]} for w in words_raw),
                                    key=lambda x: -x["ms"])[:3]}
    return " ".join(w["text"] for w in words), diag, elapsed


def run_direct(svc: Any, wav: Path) -> tuple[str, dict[str, Any], float]:
    """Taqqoslash uchun: butun fayl to'g'ridan-to'g'ri backend'ga (VAD/plan_chunks'siz; faster-whisper
    o'zining 30 s oynalari bilan). Pipeline xatosini model xatosidan ajratish uchun."""
    from lahza_engine.asr.base import AsrOptions, resolve_timestamps, transcript_density
    from lahza_engine.text.orthography import normalize

    t0 = time.perf_counter()
    words = svc.asr.transcribe_chunk(wav, 0, resolve_timestamps(AsrOptions(), svc.aligner))
    elapsed = time.perf_counter() - t0
    dens = transcript_density(words, None, int(_wav_seconds(wav) * 1000))
    diag = {"vad_method": None, "vad_segments": 0, "chunks": 1, "density": dens,
            "longest_words": sorted(({"text": w.text, "ms": w.end_ms - w.start_ms} for w in words),
                                    key=lambda x: -x["ms"])[:3]}
    return " ".join(normalize(w.text) for w in words), diag, elapsed


def _wav_seconds(wav: Path) -> float:
    import wave

    with wave.open(str(wav), "rb") as w:
        return w.getnframes() / w.getframerate()


def score(ref_text: str, hyp_text: str) -> dict[str, Any]:
    r, h = normalize_for_wer(ref_text), normalize_for_wer(hyp_text)
    rc, hc = list(" ".join(r)), list(" ".join(h))
    return {"ref_words": len(r), "hyp_words": len(h), "word_errors": edit_distance(r, h),
            "ref_chars": len(rc), "char_errors": edit_distance(rc, hc), **align_ops(r, h)}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    s = lambda k: sum(x[k] for x in rows)  # noqa: E731
    out: dict[str, Any] = {
        "files": len(rows), "ref_words": s("ref_words"), "hyp_words": s("hyp_words"),
        "wer": round(s("word_errors") / max(1, s("ref_words")), 4),
        "cer": round(s("char_errors") / max(1, s("ref_chars")), 4),
        "sub": s("sub"), "del": s("del"), "ins": s("ins"),
    }
    if all("audio_s" in x for x in rows):
        dens = [x["diag"]["density"] for x in rows]
        speech_ms = sum(d["speech_ms"] for d in dens)
        out.update({
            "audio_s": round(s("audio_s"), 1), "proc_s": round(s("proc_s"), 1),
            "rtf": round(s("proc_s") / max(1e-9, s("audio_s")), 4),
            "chunks": sum(x["diag"]["chunks"] for x in rows),
            "words_per_min": round(sum(d["words"] for d in dens) / (speech_ms / 60_000), 1) if speech_ms else 0,
            "ref_words_per_min": round(s("ref_words") / (speech_ms / 60_000), 1) if speech_ms else 0,
            "stretched_words": sum(d["stretched_words"] for d in dens),
            "stretched_ms": sum(d["stretched_ms"] for d in dens),
            "longest_word_ms": max(d["longest_word_ms"] for d in dens),
            "longest_gap_ms": max(d["longest_gap_ms"] for d in dens),
            "sparse_files": sum(1 for d in dens if d["sparse"]),
        })
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s.split(":")[-1]).strip("-")


def eval_set(svc: Any, subsets: dict[str, list[tuple[Path, Path]]], warmup: Path | None,
             direct: bool = False) -> dict[str, Any]:
    if warmup is not None:  # birinchi chaqiruvdagi yuklanish/JIT RTF'ga tushmasin
        run_pipeline(svc, warmup)
    res: dict[str, Any] = {"subsets": {}, "rows": []}
    jobs = [(n, p, run_pipeline) for n, p in subsets.items()]
    if direct:
        jobs += [(f"{n}:direct", p, run_direct) for n, p in subsets.items()]
    for name, pairs, fn in jobs:
        rows = []
        for i, (wav, ref_path) in enumerate(pairs, 1):
            ref = clean_reference(ref_path.read_text(encoding="utf-8"))
            hyp, diag, elapsed = fn(svc, wav)
            row = {"subset": name, "id": wav.stem, "audio_s": round(_wav_seconds(wav), 2),
                   "proc_s": round(elapsed, 2), **score(ref, hyp), "diag": diag, "hyp": hyp}
            row["wer"] = round(row["word_errors"] / max(1, row["ref_words"]), 4)
            rows.append(row)
            print(f"  [{name} {i}/{len(pairs)}] {wav.stem}: WER {row['wer']:.3f} "
                  f"RTF {elapsed / max(1e-9, row['audio_s']):.3f}", flush=True)
        res["subsets"][name] = summarize(rows)
        res["rows"] += rows
    res["subsets"]["all"] = summarize([r for r in res["rows"] if ":" not in r["subset"]])
    return res


def _load_fleurs() -> Any:
    spec = importlib.util.spec_from_file_location("lahza_eval_fleurs_uz", Path(__file__).with_name("fleurs_uz.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pairs(d: Path, limit: int | None) -> list[tuple[Path, Path]]:
    out = [(t.with_suffix(".wav"), t) for t in sorted(d.glob("*.txt")) if t.with_suffix(".wav").exists()]
    return out[:limit] if limit else out


# --- jadval --------------------------------------------------------------------------------------

def print_table(paths: list[Path]) -> None:
    cols = [("WER", "wer", "{:.1%}"), ("CER", "cer", "{:.1%}"), ("S/D/I", None, ""), ("RTF", "rtf", "{:.3f}"),
            ("so'z/daq", "words_per_min", "{:.0f}"), ("etalon so'z/daq", "ref_words_per_min", "{:.0f}"),
            ("cho'zilgan so'z", "stretched_words", "{}"), ("eng uzun so'z ms", "longest_word_ms", "{}"),
            ("siyrak fayl", "sparse_files", "{}")]
    print("| model | to'plam | fayl | " + " | ".join(c[0] for c in cols) + " |")
    print("|---" * (len(cols) + 3) + "|")
    for p in paths:
        d = json.loads(p.read_text(encoding="utf-8"))
        for sub, s in d["subsets"].items():
            cells = []
            for _h, k, f in cols:
                cells.append(f"{s['sub']}/{s['del']}/{s['ins']}" if k is None else
                             (f.format(s[k]) if k in s and s[k] is not None else "-"))
            name = _slug(d["model"]["id"]) + (f" [{d['tag']}]" if d.get("tag") else "")
            print(f"| {name} | {sub} | {s['files']} | " + " | ".join(cells) + " |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=["fleurs-uz"], help="tayyor test to'plami (build/asr-eval/)")
    ap.add_argument("--data", type=Path, help="<id>.wav + <id>.txt papkasi")
    ap.add_argument("--hyp-dir", type=Path, help="tayyor gipotezalar <id>.txt (ASR ishga tushirilmaydi)")
    ap.add_argument("--engine-asr", action="store_true", help="--data uchun engine pipeline'ini ishlatish")
    ap.add_argument("--model", default="base", help="base | small | model ID | CT2 papka")
    ap.add_argument("--model-id", help="--hyp-dir rejimida natija nomi")
    ap.add_argument("--direct", action="store_true",
                    help="qo'shimcha: butun faylni VAD/bo'laklashsiz backend'ga berib solishtirish")
    ap.add_argument("--vad-pad-ms", type=int, help="ablyatsiya: SileroOnnxVad.pad_ms")
    ap.add_argument("--vad-min-silence-ms", type=int, help="ablyatsiya: SileroOnnxVad.min_silence_ms")
    ap.add_argument("--temperature", help="ablyatsiya: AsrOptions.temperature (son yoki 'fallback')")
    ap.add_argument("--no-gain-norm", action="store_true", help="ablyatsiya: ovoz normalizatsiyasini o'chirish")
    ap.add_argument("--aligner", type=Path,
                    help="CTC aligner papkasi (stage_asr \"ctc\" rejimi; standart - o'rnatilgan ALIGN modeli)")
    ap.add_argument("--tag", help="natija fayl nomiga qo'shimcha (masalan ablyatsiya nomi)")
    ap.add_argument("--limit", type=int, help="har to'plamdan faqat N fayl (tez tekshiruv)")
    ap.add_argument("--root", type=Path, default=REPO / "build" / "asr-eval")
    ap.add_argument("--out", type=Path, help="natija JSON yo'li")
    ap.add_argument("--table", type=Path, nargs="+", help="natija JSON'laridan markdown jadval")
    a = ap.parse_args()

    if a.table:
        print_table(a.table)
        return

    today = dt.date.today().isoformat()
    if a.hyp_dir:
        rows = []
        for wav, ref_path in _pairs(a.data, a.limit):
            hyp_path = a.hyp_dir / ref_path.name
            if not hyp_path.exists():
                print(f"o'tkazib yuborildi (gipoteza yo'q): {ref_path.name}")
                continue
            r = score(clean_reference(ref_path.read_text(encoding="utf-8")), hyp_path.read_text(encoding="utf-8"))
            rows.append({"id": wav.stem, **r})
        result = {"model": {"id": a.model_id or "hyp"}, "subsets": {"all": summarize(rows)}, "rows": rows}
        out = a.out or a.root / f"results-{today}-{_slug(a.model_id or 'hyp')}.json"
    else:
        if a.set == "fleurs-uz":
            fl = _load_fleurs()
            ds = fl.build(a.root)
            subsets = {"short": _pairs(ds / "short", a.limit), "long": _pairs(ds / "long", a.limit)}
            dataset = json.loads((ds / "manifest.json").read_text(encoding="utf-8"))
            dataset = {k: dataset[k] for k in ("source", "revision", "license")} | {
                "path": str(ds), "short": len(subsets["short"]), "long": len(subsets["long"])}
        elif a.data and a.engine_asr:
            subsets = {a.data.name: _pairs(a.data, a.limit)}
            dataset = {"source": str(a.data)}
        else:
            ap.error("--set, yoki --data bilan --engine-asr / --hyp-dir kerak")
        svc, model_info = build_eval_services(a.model, a.aligner)
        overrides = apply_overrides(svc, a)
        state = code_state(svc)
        state["overrides"] = overrides
        print(f"model {model_info['id']} | VAD {state['vad_runtime']} | temperature: "
              f"{state['decoder_has_temperature']} | dirty: {len(state['engine_dirty_files'])} fayl", flush=True)
        first = next((p[0][0] for p in subsets.values() if p), None)
        t0 = time.time()
        res = eval_set(svc, subsets, first, a.direct)
        result = {"created": dt.datetime.now().isoformat(timespec="seconds"), "dataset": dataset,
                  "model": model_info, "tag": a.tag, "overrides": overrides, "direct_baseline": a.direct, "code_state": state, "wall_s": round(time.time() - t0, 1), **res}
        tag = f"-{_slug(a.tag)}" if a.tag else ""
        out = a.out or a.root / f"results-{today}-{_slug(model_info['id'])}{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {out}")
    print_table([out])


if __name__ == "__main__":
    sys.exit(main())
