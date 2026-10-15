"""Kutubxona: lug'at (lexicon), uslub shablonlari (style_templates), shriftlar."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ValidationError

from lahza_engine.api.state import State
from lahza_engine.subtitle.style import StyleTemplate

MAX_STYLE_FILE = 1024 * 1024


class LexiconIn(BaseModel):
    show_id: str | None = None
    term: str
    variants: list[str] = []
    kind: Literal["ism", "brend", "atama"] = "atama"


class StyleIn(BaseModel):
    name: str
    template: StyleTemplate


class PathIn(BaseModel):
    path: str


def _lex_row(r) -> dict[str, Any]:
    return {"id": r["id"], "show_id": r["show_id"], "term": r["term"],
            "variants": json.loads(r["variants_json"] or "[]"), "kind": r["kind"]}


def _style_row(r) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"],
            "template": StyleTemplate.model_validate_json(r["json"]).model_dump(mode="json")}


def _get_style(s: State, sid: str):
    rows = s.lib("SELECT * FROM style_templates WHERE id = ?", (sid,))
    if not rows:
        raise HTTPException(404, "shablon topilmadi")
    return rows[0]


def _save_style(s: State, sid: str | None, name: str, tpl: StyleTemplate) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise HTTPException(400, "shablon nomi bo'sh")
    data = tpl.model_copy(update={"name": name}).model_dump_json()
    if sid is None:
        sid = uuid.uuid4().hex[:12]
        s.lib_write("INSERT INTO style_templates(id, name, json, updated_at) VALUES (?,?,?,datetime('now'))",
                    (sid, name, data))
    else:
        s.lib_write("UPDATE style_templates SET name = ?, json = ?, updated_at = datetime('now')"
                    " WHERE id = ?", (name, data, sid))
    return _style_row(_get_style(s, sid))


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    # ---- Lug'at -----------------------------------------------------------------
    @app.get("/v1/lexicon")
    def lexicon(project_id: str | None = Query(None), s: State = Depends(auth)) -> list[dict[str, Any]]:
        if project_id:
            rows = s.lib("SELECT * FROM lexicon WHERE show_id = ? OR show_id IS NULL ORDER BY term",
                         (project_id,))
        else:
            rows = s.lib("SELECT * FROM lexicon ORDER BY term")
        return [_lex_row(r) for r in rows]

    @app.post("/v1/lexicon")
    def add_lexicon(body: LexiconIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.text.orthography import normalize

        term = normalize(body.term).strip()
        if not term:
            raise HTTPException(400, "atama bo'sh")
        if body.show_id and not s.lib("SELECT 1 FROM shows WHERE id = ?", (body.show_id,)):
            raise HTTPException(404, "loyiha topilmadi")
        variants = []
        for v in body.variants:
            v = normalize(v).strip()
            if v and v != term and v not in variants:
                variants.append(v)
        cur = s.lib_write("INSERT INTO lexicon(show_id, term, variants_json, kind) VALUES (?,?,?,?)",
                          (body.show_id, term, json.dumps(variants, ensure_ascii=False), body.kind))
        return _lex_row(s.lib("SELECT * FROM lexicon WHERE id = ?", (cur.lastrowid,))[0])

    @app.delete("/v1/lexicon/{lex_id}")
    def delete_lexicon(lex_id: int, s: State = Depends(auth)) -> dict[str, Any]:
        if s.lib_write("DELETE FROM lexicon WHERE id = ?", (lex_id,)).rowcount == 0:
            raise HTTPException(404, "yozuv topilmadi")
        return {"ok": True}

    # ---- Uslub shablonlari ------------------------------------------------------
    @app.get("/v1/styles")
    def styles(s: State = Depends(auth)) -> list[dict[str, Any]]:
        return [_style_row(r) for r in s.lib("SELECT * FROM style_templates ORDER BY name")]

    @app.post("/v1/styles")
    def create_style(body: StyleIn, s: State = Depends(auth)) -> dict[str, Any]:
        return _save_style(s, None, body.name, body.template)

    @app.put("/v1/styles/{sid}")
    def update_style(sid: str, body: StyleIn, s: State = Depends(auth)) -> dict[str, Any]:
        _get_style(s, sid)
        return _save_style(s, sid, body.name, body.template)

    @app.delete("/v1/styles/{sid}")
    def delete_style(sid: str, s: State = Depends(auth)) -> dict[str, Any]:
        if s.lib_write("DELETE FROM style_templates WHERE id = ?", (sid,)).rowcount == 0:
            raise HTTPException(404, "shablon topilmadi")
        return {"ok": True}

    @app.post("/v1/styles:import")
    def import_style(body: PathIn, s: State = Depends(auth)) -> dict[str, Any]:
        p = Path(body.path)
        if not p.is_file() or p.suffix.lower() != ".json":
            raise HTTPException(400, "JSON fayl topilmadi")
        if p.stat().st_size > MAX_STYLE_FILE:
            raise HTTPException(400, "fayl juda katta")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("template"), dict):
                tpl = StyleTemplate.model_validate(data["template"])
                name = str(data.get("name") or tpl.name)
            else:
                tpl = StyleTemplate.model_validate(data)
                name = tpl.name
        except (ValueError, ValidationError) as e:
            raise HTTPException(400, "shablon fayli yaroqsiz") from e
        return _save_style(s, None, name or p.stem, tpl)

    @app.post("/v1/styles/{sid}:export")
    def export_style(sid: str, body: PathIn, s: State = Depends(auth)) -> dict[str, Any]:
        row = _style_row(_get_style(s, sid))
        p = Path(body.path)
        if p.suffix.lower() != ".json":
            p = p.with_suffix(".json")
        if not p.parent.is_dir():
            raise HTTPException(400, "papka topilmadi")
        p.write_text(json.dumps({"name": row["name"], "template": row["template"]},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True}

    # ---- Shriftlar --------------------------------------------------------------
    @app.get("/v1/fonts")
    def fonts(s: State = Depends(auth)) -> list[dict[str, Any]]:
        try:
            from lahza_engine.subtitle.fonts import list_fonts
        except ImportError as e:
            raise HTTPException(501, "shriftlar ro'yxati bu versiyada mavjud emas") from e
        return [f.model_dump(mode="json") for f in list_fonts()]
