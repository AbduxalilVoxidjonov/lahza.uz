"""Highlight baholash (UzHighlight-Eval): precision@k va mutaxassis lahzalarini topish ulushi.

    python eval/run_highlight_eval.py --gold eval/data/highlight --project-root /path/to/episodes --model-id llm-x

gold: <epizod>.gold.json = [{"annotator", "start_ms", "end_ms"}, ...]
pred: <project-root>/<epizod>.lahza/project.db dagi kliplar (ball bo'yicha saralangan).
Moslik: IoU >= 0.5 (TZ 7-bo'lim).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from lahza_engine.eval_metrics import precision_at_k, recall


def load_pred(db: Path) -> list[tuple[int, int]]:
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT start_ms, end_ms FROM clips ORDER BY score DESC").fetchall()
    conn.close()
    return [(int(a), int(b)) for a, b in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    a = ap.parse_args()
    per = []
    for g in sorted(a.gold.glob("*.gold.json")):
        ep = g.name.removesuffix(".gold.json")
        db = a.project_root / f"{ep}.lahza" / "project.db"
        if not db.exists():
            continue
        gold = [(x["start_ms"], x["end_ms"]) for x in json.loads(g.read_text(encoding="utf-8"))]
        pred = load_pred(db)
        per.append({"episode": ep, f"p@{a.k}": precision_at_k(pred, gold, a.k), "recall": recall(pred, gold)})
    n = max(1, len(per))
    res = {
        "model_id": a.model_id,
        "episodes": len(per),
        f"p@{a.k}": sum(x[f"p@{a.k}"] for x in per) / n,
        "recall": sum(x["recall"] for x in per) / n,
        "rows": per,
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"{a.model_id}.highlight.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print({k: v for k, v in res.items() if k != "rows"})


if __name__ == "__main__":
    main()
