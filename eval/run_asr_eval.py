"""ASR baholash: WER, CER (normallashtirilgan), ixtiyoriy RTF.

    python eval/run_asr_eval.py --data eval/data/uzpodcast --hyp-dir out/ --model-id asr-x
    python eval/run_asr_eval.py --data eval/data/uzpodcast --engine-asr --model-id asr-x

Etalon: <id>.txt (YORIQNOMA.md bo'yicha); [..] belgilari va {ru}/{en} teglari olib tashlanadi.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from lahza_engine.eval_metrics import cer, edit_distance, normalize_for_wer

_TAGS = re.compile(r"\[[^\]]*\]|\{[a-z]{2}\}")
_SPK = re.compile(r"^\s*\[[A-Z]\]\s*", flags=re.M)


def clean_reference(text: str) -> str:
    return _TAGS.sub(" ", _SPK.sub("", text))


def transcribe_with_engine(wav: Path) -> tuple[str, float]:
    from lahza_engine.asr.base import AsrOptions, plan_chunks
    from lahza_engine.config import Settings
    from lahza_engine.core.services import build_services
    from lahza_engine.media.probe import read_wav_mono
    from lahza_engine.models.store import ModelStore
    from lahza_engine.vad.energy import energy_vad

    svc = build_services(ModelStore(Settings().models_dir))
    if svc.asr is None:
        raise SystemExit("ASR modeli o'rnatilmagan")
    pcm, sr = read_wav_mono(wav)
    t0 = time.perf_counter()
    words = []
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        for i, (a, b) in enumerate(plan_chunks(energy_vad(pcm, sr))):
            piece = Path(td) / f"{i}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a / 1000}", "-t", f"{(b - a) / 1000}",
                            "-i", str(wav), str(piece)], check=True)
            words += svc.asr.transcribe_chunk(piece, a, AsrOptions())
    elapsed = time.perf_counter() - t0
    return " ".join(w.text for w in words), elapsed / (len(pcm) / sr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--hyp-dir", type=Path)
    ap.add_argument("--engine-asr", action="store_true")
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    a = ap.parse_args()

    rows = []
    tot_err = tot_words = 0
    rtfs = []
    for ref_path in sorted(a.data.glob("*.txt")):
        ref = clean_reference(ref_path.read_text(encoding="utf-8"))
        if a.engine_asr:
            hyp, rtf = transcribe_with_engine(ref_path.with_suffix(".wav"))
            rtfs.append(rtf)
        else:
            hyp_path = (a.hyp_dir or Path(".")) / ref_path.name
            if not hyp_path.exists():
                print(f"o'tkazib yuborildi (gipoteza yo'q): {ref_path.name}")
                continue
            hyp = hyp_path.read_text(encoding="utf-8")
        r, h = normalize_for_wer(ref), normalize_for_wer(hyp)
        err = edit_distance(r, h)
        tot_err += err
        tot_words += len(r)
        rows.append({"id": ref_path.stem, "wer": err / max(1, len(r)), "cer": cer(ref, hyp), "words": len(r)})

    summary = {
        "model_id": a.model_id,
        "files": len(rows),
        "wer": tot_err / max(1, tot_words),  # so'zlar bo'yicha vaznli
        "cer_mean": sum(x["cer"] for x in rows) / max(1, len(rows)),
        "rtf_mean": (sum(rtfs) / len(rtfs)) if rtfs else None,
        "rows": rows,
    }
    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / f"{a.model_id}.asr.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{a.model_id}: WER {summary['wer']:.3f}, CER {summary['cer_mean']:.3f} -> {out}")


if __name__ == "__main__":
    main()
