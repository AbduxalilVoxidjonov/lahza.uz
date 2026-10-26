"""Pro: shaxsiy lug'at (PRO-1) va real natijalardan ball vaznlarini o'rganish (PRO-6). To'liq oflayn.

Lug'at `library.db -> personal_dictionary` da (umumiy, foydalanuvchiga xos); juftliklar
`PATCH /v1/episodes/{id}/words` tuzatishlaridan yig'iladi. Fine-tune manifesti epizodlarning
`project.db -> corrections` jadvalidan quriladi (audio ko'chirilmaydi - yo'l + vaqt).

Vaznlar `library.db -> highlight_weights` da: `scope = 'global'` yoki loyiha (shou) ID'si.
Tahlilda loyiha vaznlari, bo'lmasa global, bo'lmasa standart (`HighlightConfig`) ishlatiladi.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from lahza_engine.api.state import State
from lahza_engine.config import Settings
from lahza_engine.db import store as db
from lahza_engine.highlight import learning
from lahza_engine.text import personal_dict as pd

GLOBAL = "global"
WAV_NAME = "audio16k.wav"


class MetricsIn(BaseModel):
    views: int = Field(ge=0, le=10**12)
    likes: int | None = Field(default=None, ge=0, le=10**12)


class ResetIn(BaseModel):
    project_id: str | None = None


class PathOutIn(BaseModel):
    out_path: str


class ManifestExportIn(PathOutIn):
    project_id: str | None = None


def _out_file(raw: str, suffix: str) -> Path:
    """Chiqish fayli: mavjud papka bo'lsa - ichida standart nom; kengaytma majburiy."""
    out = Path(raw).expanduser()
    if out.is_dir():
        out = out / ("lahza-dictionary.json" if suffix == ".json" else "lahza-finetune.jsonl")
    if out.suffix.lower() != suffix:
        out = out.with_suffix(suffix)
    if not out.parent.is_dir():
        raise HTTPException(400, "papka topilmadi")
    return out


# ---- Lug'at -------------------------------------------------------------------------------


def harvest_correction(s: State, episode_id: str, before: str, after: str) -> list[tuple[str, str]]:
    """Bitta tuzatishdan juftliklarni lug'atga qo'shadi (count += 1). Xato tahrirni to'xtatmaydi."""
    pairs = pd.diff_pairs(before, after)
    for wrong, right in pairs:
        s.lib_write(
            "INSERT INTO personal_dictionary(wrong, right, kind, count, last_episode_id) VALUES (?,?,?,1,?)"
            " ON CONFLICT(wrong, right) DO UPDATE SET count = count + 1,"
            " last_episode_id = excluded.last_episode_id, updated_at = datetime('now')",
            (wrong, right, pd.classify(right), episode_id))
    return pairs


def dictionary_rows(s: State) -> list[pd.DictEntry]:
    return [pd.DictEntry(r["wrong"], r["right"], r["count"], r["kind"])
            for r in s.lib("SELECT wrong, right, count, kind FROM personal_dictionary")]


def active_dictionary(s: State) -> list[pd.DictEntry]:
    return pd.resolve(dictionary_rows(s))


def merge_hotwords(base: list[str], entries: list[pd.DictEntry]) -> list[str]:
    """Lexicon hotwords'idan keyin lug'at ismlari/atamalari (takrorsiz, tartib saqlanadi)."""
    seen = {h.lower() for h in base}
    out = list(base)
    for h in pd.hotwords(entries):
        if h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out


def _entry_json(r, active: set[tuple[str, str]]) -> dict[str, Any]:
    return {"id": r["id"], "wrong": r["wrong"], "right": r["right"], "kind": r["kind"],
            "count": r["count"], "active": (r["wrong"], r["right"]) in active,
            "last_episode_id": r["last_episode_id"], "updated_at": r["updated_at"]}


def _dictionary_json(s: State) -> list[dict[str, Any]]:
    active = {(e.wrong, e.right) for e in active_dictionary(s)}
    rows = s.lib("SELECT * FROM personal_dictionary ORDER BY count DESC, wrong, right")
    return [_entry_json(r, active) for r in rows]


def manifest_lines(s: State, project_id: str | None = None) -> Iterator[dict[str, Any]]:
    """Tuzatilgan gaplar: har (epizod, gap) uchun bitta qator, joriy (yakuniy) matn bilan.
    Audio fayl ko'chirilmaydi; gap butunlay qaytarilgan (matn = ASR matni) bo'lsa - o'tkaziladi."""
    if project_id:
        eps = s.lib("SELECT id, show_id, project_dir FROM episodes WHERE show_id = ? ORDER BY created_at, id",
                    (project_id,))
    else:
        eps = s.lib("SELECT id, show_id, project_dir FROM episodes ORDER BY created_at, id")
    for ep in eps:
        pdir = Path(ep["project_dir"])
        if not (pdir / "project.db").exists():
            continue
        wav = pdir / "cache" / WAV_NAME
        conn = db.open_project(pdir)
        try:
            firsts: dict[int, str] = {}
            for r in conn.execute("SELECT sentence_id, before_text FROM corrections WHERE media_id = ?"
                                  " AND sentence_id IS NOT NULL ORDER BY id", (ep["id"],)):
                firsts.setdefault(r["sentence_id"], r["before_text"])
            for sid, asr_text in sorted(firsts.items()):
                sent = db.load_sentence(conn, ep["id"], sid)
                if sent is None or not sent.words:
                    continue
                text = sent.text.strip()
                if not text or text == asr_text.strip():
                    continue
                yield {"audio": str(wav), "audio_exists": wav.exists(), "start_ms": sent.start_ms,
                       "end_ms": sent.end_ms, "duration_ms": sent.end_ms - sent.start_ms,
                       "text": text, "asr_text": asr_text, "language": "uz",
                       "episode_id": ep["id"], "project_id": ep["show_id"], "sentence_id": sid}
        finally:
            conn.close()


# ---- Vaznlar ------------------------------------------------------------------------------


def _weights_row(s: State, scope: str):
    rows = s.lib("SELECT * FROM highlight_weights WHERE scope = ?", (scope,))
    return rows[0] if rows else None


def _samples(s: State, scope: str) -> list[learning.Sample]:
    row = _weights_row(s, scope)
    since = row["since_id"] if row else 0
    if scope == GLOBAL:
        rows = s.lib("SELECT * FROM clip_metrics WHERE id > ? ORDER BY id", (since,))
    else:
        rows = s.lib("SELECT * FROM clip_metrics WHERE show_id = ? AND id > ? ORDER BY id", (scope, since))
    return [learning.Sample(json.loads(r["features_json"] or "{}"), r["views"], r["likes"]) for r in rows]


def relearn(s: State, scope: str) -> learning.LearnResult:
    res = learning.fit_weights(_samples(s, scope), learning.default_weights(s.settings.highlight))
    s.lib_write(
        "INSERT INTO highlight_weights(scope, weights_json, n_samples) VALUES (?,?,?)"
        " ON CONFLICT(scope) DO UPDATE SET weights_json = excluded.weights_json,"
        " n_samples = excluded.n_samples, updated_at = datetime('now')",
        (scope, json.dumps(res.weights) if res.learned else None, res.n_used))
    return res


def effective_weights(s: State, show_id: str | None) -> tuple[dict[str, float], str]:
    """(vaznlar, manba): manba `project | global | default`."""
    for scope, src in ((show_id, "project"), (GLOBAL, "global")):
        if not scope:
            continue
        row = _weights_row(s, scope)
        if row is not None and row["weights_json"]:
            return json.loads(row["weights_json"]), src
    return learning.default_weights(s.settings.highlight), "default"


def settings_for(s: State, show_id: str | None) -> Settings:
    """Tahlil uchun sozlamalar: o'rganilgan vaznlar bilan (standart bo'lsa - o'sha obyekt)."""
    weights, src = effective_weights(s, show_id)
    if src == "default":
        return s.settings
    return s.settings.model_copy(update={"highlight": learning.apply_weights(s.settings.highlight, weights)})


def weights_info(s: State, project_id: str | None) -> dict[str, Any]:
    scope = project_id or GLOBAL
    row = _weights_row(s, scope)
    weights, src = effective_weights(s, project_id)
    return {"scope": scope, "weights": weights, "source": src,
            "defaults": learning.default_weights(s.settings.highlight),
            "learned": bool(row is not None and row["weights_json"]),
            "n_samples": row["n_samples"] if row else 0, "min_samples": learning.MIN_SAMPLES}


def _metrics_json(r) -> dict[str, Any]:
    return {"clip_id": r["clip_id"], "views": r["views"], "likes": r["likes"],
            "recorded_at": r["recorded_at"]}


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/dictionary")
    def dictionary(s: State = Depends(auth)) -> dict[str, Any]:
        return {"entries": _dictionary_json(s), "min_count": pd.DEFAULT_MIN_COUNT,
                "conf_threshold": pd.DEFAULT_CONF_THRESHOLD}

    @app.delete("/v1/dictionary/{entry_id}")
    def delete_entry(entry_id: int, s: State = Depends(auth)) -> dict[str, Any]:
        if s.lib_write("DELETE FROM personal_dictionary WHERE id = ?", (entry_id,)).rowcount == 0:
            raise HTTPException(404, "lug'at yozuvi topilmadi")
        return {"ok": True}

    @app.get("/v1/dictionary:export")
    def export_dictionary(s: State = Depends(auth)) -> dict[str, Any]:
        return {"format": "lahza.dictionary/1", "entries": _dictionary_json(s)}

    @app.post("/v1/dictionary:export")
    def export_dictionary_file(body: PathOutIn, s: State = Depends(auth)) -> dict[str, Any]:
        out = _out_file(body.out_path, ".json")
        entries = _dictionary_json(s)
        out.write_text(json.dumps({"format": "lahza.dictionary/1", "entries": entries}, ensure_ascii=False,
                                  indent=2), encoding="utf-8")
        return {"path": str(out), "entries": len(entries)}

    @app.get("/v1/dictionary/finetune-manifest")
    def finetune_manifest(project_id: str | None = Query(None), s: State = Depends(auth)) -> PlainTextResponse:
        body = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in manifest_lines(s, project_id))
        return PlainTextResponse(body, media_type="application/x-ndjson")

    @app.post("/v1/dictionary/finetune-manifest:export")
    def export_manifest(body: ManifestExportIn, s: State = Depends(auth)) -> dict[str, Any]:
        out = _out_file(body.out_path, ".jsonl")
        n = 0
        with out.open("w", encoding="utf-8") as f:
            for x in manifest_lines(s, body.project_id):
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
                n += 1
        return {"path": str(out), "segments": n}

    @app.get("/v1/episodes/{eid}/clip-metrics")
    def clip_metrics(eid: str, s: State = Depends(auth)) -> dict[str, Any]:
        s.episode_row(eid)
        return {r["clip_id"]: _metrics_json(r)
                for r in s.lib("SELECT * FROM clip_metrics WHERE episode_id = ?", (eid,))}

    @app.put("/v1/episodes/{eid}/clips/{cid}/metrics")
    def put_metrics(eid: str, cid: str, body: MetricsIn, s: State = Depends(auth)) -> dict[str, Any]:
        row = s.episode_row(eid)
        with s.project(eid) as conn:
            clip = db.get_clip(conn, eid, cid)
        if clip is None:
            raise HTTPException(404, "klip topilmadi")
        feats = learning.features_of(clip.scores)
        # O'chirib qayta yozish: yangilangan natija "reset"dan keyingi yangi namuna hisoblanadi.
        with s.lib_lock, s.library:
            s.library.execute("DELETE FROM clip_metrics WHERE episode_id = ? AND clip_id = ?", (eid, cid))
            s.library.execute(
                "INSERT INTO clip_metrics(episode_id, show_id, clip_id, views, likes, features_json, score,"
                " source) VALUES (?,?,?,?,?,?,?,?)",
                (eid, row["show_id"], cid, body.views, body.likes, json.dumps(feats), clip.score,
                 clip.source.value))
        relearn(s, row["show_id"])
        relearn(s, GLOBAL)
        r = s.lib("SELECT * FROM clip_metrics WHERE episode_id = ? AND clip_id = ?", (eid, cid))[0]
        return {"metrics": _metrics_json(r), "weights": weights_info(s, row["show_id"])}

    @app.delete("/v1/episodes/{eid}/clips/{cid}/metrics")
    def delete_metrics(eid: str, cid: str, s: State = Depends(auth)) -> dict[str, Any]:
        row = s.episode_row(eid)
        if s.lib_write("DELETE FROM clip_metrics WHERE episode_id = ? AND clip_id = ?",
                       (eid, cid)).rowcount == 0:
            raise HTTPException(404, "natija topilmadi")
        relearn(s, row["show_id"])
        relearn(s, GLOBAL)
        return {"ok": True}

    @app.get("/v1/highlight/weights")
    def get_weights(project_id: str | None = Query(None), s: State = Depends(auth)) -> dict[str, Any]:
        if project_id and not s.lib("SELECT 1 FROM shows WHERE id = ?", (project_id,)):
            raise HTTPException(404, "loyiha topilmadi")
        return weights_info(s, project_id)

    @app.post("/v1/highlight/weights:reset")
    def reset_weights(body: ResetIn | None = None, s: State = Depends(auth)) -> dict[str, Any]:
        project_id = body.project_id if body else None
        if project_id and not s.lib("SELECT 1 FROM shows WHERE id = ?", (project_id,)):
            raise HTTPException(404, "loyiha topilmadi")
        scope = project_id or GLOBAL
        last = s.lib("SELECT COALESCE(MAX(id), 0) AS m FROM clip_metrics")[0]["m"]
        # Eski namunalar o'rganishdan chiqariladi (since_id); keyingi kiritishlardan qayta o'rganiladi.
        s.lib_write(
            "INSERT INTO highlight_weights(scope, weights_json, n_samples, since_id) VALUES (?, NULL, 0, ?)"
            " ON CONFLICT(scope) DO UPDATE SET weights_json = NULL, n_samples = 0,"
            " since_id = excluded.since_id, updated_at = datetime('now')", (scope, last))
        return weights_info(s, project_id)
