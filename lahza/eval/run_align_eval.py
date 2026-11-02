"""So'z chegarasi baholash (Align-Eval): median va p95 xato, ms.

    python eval/run_align_eval.py --gold eval/data/align --hyp-dir out/ --model-id align-x

Har fayl: <id>.words.json = [{"text", "start_ms", "end_ms"}, ...] (bir xil tartibda).
Maqsad (TZ 6-bo'lim, R0'da tasdiqlanadi): median <= 80 ms, p95 <= 250 ms.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lahza_engine.eval_metrics import boundary_errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--hyp-dir", type=Path, required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    a = ap.parse_args()
    ref_all: list[tuple[int, int]] = []
    hyp_all: list[tuple[int, int]] = []
    for g in sorted(a.gold.glob("*.words.json")):
        h = a.hyp_dir / g.name
        if not h.exists():
            continue
        gw = json.loads(g.read_text(encoding="utf-8"))
        hw = json.loads(h.read_text(encoding="utf-8"))
        n = min(len(gw), len(hw))
        ref_all += [(w["start_ms"], w["end_ms"]) for w in gw[:n]]
        hyp_all += [(w["start_ms"], w["end_ms"]) for w in hw[:n]]
    res = {"model_id": a.model_id, "words": len(ref_all), **boundary_errors(ref_all, hyp_all)}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"{a.model_id}.align.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(res)


if __name__ == "__main__":
    main()
