"""Lahza MCP tool'lari: mavjud HTTP API endpointlariga xarita (yangi endpoint yo'q).

Xavfsizlik chegaralari:
* ixtiyoriy fayl yo'lini o'qiydigan/yozadigan tool yo'q - eksport papkasi Claude tomonidan
  tanlanmaydi (`LAHZA_MCP_EXPORT_DIR` yoki `~/Movies/Lahza`), preview kadri server boshqaradigan
  vaqtinchalik papkaga yoziladi;
* video/audio baytlari qaytarilmaydi (faqat JPEG preview kadri, hajmi cheklangan);
* har javob matni `MAX_TEXT_CHARS` bilan cheklanadi;
* eksport faqat `confirm: true` bilan.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import sys
import tempfile
import threading
import types
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lahza_engine.mcp_server.engine_client import (
    EngineClient,
    EngineHTTPError,
    EngineNotRunning,
    seg,
)
from lahza_engine.mcp_server.schema import validate

MAX_TEXT_CHARS = 60_000
MAX_LIST = 200
MAX_IMAGE_BYTES = 4 * 1024 * 1024
PREVIEW_KEEP = 20
UNDO_DEPTH = 20
PLATFORMS = ["instagram_reels", "youtube_shorts", "youtube_video"]
ID = {"type": "string", "minLength": 1, "maxLength": 128}


class ToolError(Exception):
    """Foydalanuvchiga ko'rinadigan tool xatosi (`isError: true`)."""


def export_dir() -> Path:
    """Eksport papkasi - foydalanuvchi muhiti belgilaydi, Claude emas."""
    env = os.environ.get("LAHZA_MCP_EXPORT_DIR")
    if env:
        return Path(env).expanduser()
    home = Path.home()
    return home / ("Movies" if sys.platform == "darwin" else "Videos") / "Lahza"


def preview_dir() -> Path:
    return Path(tempfile.gettempdir()) / "lahza-mcp" / "previews"


def _pick(d: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: d.get(k) for k in keys if k in d}


def _short(text: Any, n: int = 300) -> Any:
    return text[:n] + "…" if isinstance(text, str) and len(text) > n else text


@dataclass
class UndoEntry:
    montage_id: str
    before: dict[str, Any]  # tahrirdan oldingi saqlangan timeline
    after_revision: str  # qo'llangandan keyingi timeline revision'i (selection=None)


@dataclass
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    annotations: dict[str, Any]

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": self.input_schema, "annotations": {"title": self.title, **self.annotations}}


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}


class LahzaTools:
    def __init__(self, client: EngineClient | None = None) -> None:
        self.client = client or EngineClient()
        self.undo: list[UndoEntry] = []
        self._lock = threading.Lock()
        self.tools: dict[str, Tool] = {t.name: t for t in self._build()}

    # ---- Umumiy -----------------------------------------------------------------------
    def list(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self.tools.values()]

    def call(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        """MCP `tools/call` natijasi. Noma'lum tool - KeyError (protokol xatosi)."""
        tool = self.tools[name]
        args = arguments if arguments is not None else {}
        errors = validate(args, tool.input_schema)
        if errors:
            return _error("Argumentlar noto'g'ri / invalid arguments: " + "; ".join(errors[:20]))
        try:
            with self._lock:  # bitta stdio sessiya - tool'lar ketma-ket
                out = tool.handler(args)
        except (ToolError, EngineNotRunning, EngineHTTPError) as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001 - kutilmagan xato ham tool xatosi, server yiqilmaydi
            return _error(f"Ichki xato / internal error: {type(e).__name__}: {_short(str(e), 500)}")
        if isinstance(out, dict) and "content" in out:
            return out
        return _text(out)

    def _montage(self, mid: str) -> dict[str, Any]:
        return self.client.get(f"/v1/montages/{seg(mid)}")

    @staticmethod
    def _timeline(detail: dict[str, Any]):
        from lahza_engine.montage.model import MontageTimeline

        if not detail.get("timeline"):
            raise ToolError(f"montaj hali tayyor emas (status: {detail.get('status')}) / montage has no "
                            "timeline yet")
        return MontageTimeline.model_validate(detail["timeline"])

    # ---- Handlerlar -------------------------------------------------------------------
    def lahza_status(self, a: dict[str, Any]) -> Any:
        from lahza_engine.editing_agent.model import OPERATIONS

        info = self.client.info(refresh=True)
        health = self.client.get("/v1/health")
        return {"connected": True, "engine_version": health.get("version"), "port": info.get("port"),
                "pid": info.get("pid"), "edit_operations": OPERATIONS,
                "export_dir": str(export_dir()), "undo_stack": len(self.undo)}

    def list_projects(self, a: dict[str, Any]) -> Any:
        rows = self.client.get("/v1/projects")
        return {"projects": [_pick(r, ("id", "name", "created_at")) for r in rows[:MAX_LIST]],
                "total": len(rows)}

    def list_episodes(self, a: dict[str, Any]) -> Any:
        rows = self.client.get(f"/v1/projects/{seg(a['project_id'])}/episodes")
        return {"episodes": [_pick(r, ("id", "title", "status", "created_at")) for r in rows[:MAX_LIST]],
                "total": len(rows)}

    def list_montages(self, a: dict[str, Any]) -> Any:
        q = f"?project_id={seg(a['project_id'])}" if a.get("project_id") else ""
        rows = self.client.get(f"/v1/montages{q}")
        return {"montages": [_pick(r, ("id", "name", "status", "duration_ms", "template_id", "project_id",
                                       "updated_at")) for r in rows[:MAX_LIST]], "total": len(rows)}

    def list_clips(self, a: dict[str, Any]) -> Any:
        rows = self.client.get(f"/v1/episodes/{seg(a['episode_id'])}/clips")
        if a.get("status"):
            rows = [r for r in rows if r.get("status") == a["status"]]
        offset, limit = a.get("offset", 0), a.get("limit", 50)
        out = []
        for r in rows[offset:offset + limit]:
            item = _pick(r, ("id", "start_ms", "end_ms", "title", "kind", "score", "status", "source"))
            item["reason"] = _short(r.get("reason", ""), 200)
            item["cuts"] = len(r.get("cuts") or [])
            item["hook"] = bool(r.get("hook"))
            out.append(item)
        end = offset + len(out)
        return {"clips": out, "total": len(rows), "next_offset": end if end < len(rows) else None}

    def get_transcript(self, a: dict[str, Any]) -> Any:
        data = self.client.get(f"/v1/episodes/{seg(a['episode_id'])}/transcript")
        sentences = data.get("sentences") or []
        lo, hi = a.get("start_ms"), a.get("end_ms")
        if lo is not None or hi is not None:
            sentences = [x for x in sentences if (hi is None or x["start_ms"] < hi)
                         and (lo is None or x["end_ms"] > lo)]
        offset, limit = a.get("offset", 0), a.get("limit", 50)
        max_chars = a.get("max_chars", 20_000)
        out, used, i = [], 0, offset
        for x in sentences[offset:offset + limit]:
            item = {"id": x.get("id"), "start_ms": x.get("start_ms"), "end_ms": x.get("end_ms"),
                    "speaker": x.get("speaker"), "text": x.get("text", "")}
            size = len(json.dumps(item, ensure_ascii=False))
            if out and used + size > max_chars:
                break
            out.append(item)
            used += size
            i += 1
        return {"sentences": out, "offset": offset, "next_offset": i if i < len(sentences) else None,
                "total": len(sentences)}

    def get_timeline(self, a: dict[str, Any]) -> Any:
        from lahza_engine.editing_agent.executor import revision
        from lahza_engine.editing_agent.model import OPERATIONS
        from lahza_engine.editing_agent.planner import compact_context

        detail = self._montage(a["montage_id"])
        tl = self._timeline(detail)
        sel = a.get("selected_video_id")
        if sel is not None and sel not in {v.id for v in tl.video}:
            raise ToolError(f"selected_video_id '{sel}' montajda yo'q")
        try:
            context = compact_context(types.SimpleNamespace(timeline=tl, selected_video_id=sel))
        except ValueError as e:
            raise ToolError(str(e)) from e
        return {"montage_id": detail.get("id"), "name": detail.get("name"), "status": detail.get("status"),
                "base_revision": revision(tl, sel), "selected_video_id": sel, "timeline": context,
                "supported_operations": OPERATIONS,
                "plan_format": {"schema": "lahza.edit-plan/1", "base_revision": "<base_revision>",
                                "commands": [{"tool": "<operation>", "args": {}}], "unresolved": []}}

    def _plan(self, a: dict[str, Any]):
        """Rejani `editing_agent/model.py` bo'yicha tekshiradi. Qaytaradi: (EditPlan|None, xatolar)."""
        from pydantic import ValidationError

        from lahza_engine.editing_agent.model import EditPlan

        raw = dict(a["plan"])
        raw.setdefault("schema", "lahza.edit-plan/1")
        raw.setdefault("unresolved", [])
        try:
            return EditPlan.model_validate(raw), []
        except ValidationError as e:
            return None, [f"{'.'.join(str(x) for x in err['loc']) or 'plan'}: {err['msg']}"
                          for err in e.errors()[:30]]

    def _preview(self, a: dict[str, Any], plan, tl) -> dict[str, Any]:
        body = {"timeline": tl.to_json(), "plan": plan.model_dump(mode="json", by_alias=True),
                "selected_video_id": a.get("selected_video_id")}
        try:
            return self.client.post("/v1/editing-agent:preview", body)
        except EngineHTTPError as e:
            if e.status == 409:
                raise ToolError(f"409 Conflict: {e.detail}. Reja eskirgan - get_timeline bilan yangi "
                                "base_revision oling / plan is stale: call get_timeline again.") from None
            if e.status == 422:
                raise ToolError(f"Reja qo'llanmaydi / plan rejected: {e.detail}") from None
            raise

    def propose_edit_plan(self, a: dict[str, Any]) -> Any:
        from lahza_engine.editing_agent.executor import revision

        plan, errors = self._plan(a)
        if plan is None:
            return {"valid": False, "errors": errors, "changes": [], "warnings": []}
        tl = self._timeline(self._montage(a["montage_id"]))
        current = revision(tl, a.get("selected_video_id"))
        if plan.base_revision != current:
            return {"valid": False, "errors": ["base_revision eskirgan (409) - get_timeline'ni qayta chaqiring"],
                    "current_base_revision": current, "changes": [], "warnings": []}
        if plan.unresolved:
            return {"valid": False, "errors": ["unresolved bo'sh bo'lishi kerak: " + "; ".join(plan.unresolved)],
                    "changes": [], "warnings": []}
        try:
            out = self._preview(a, plan, tl)
        except ToolError as e:
            return {"valid": False, "errors": [str(e)], "changes": [], "warnings": []}
        return {"valid": True, "errors": [], "changes": out.get("changes", []),
                "warnings": out.get("warnings", []), "applied": False}

    def apply_edit_plan(self, a: dict[str, Any]) -> Any:
        from lahza_engine.editing_agent.executor import revision
        from lahza_engine.montage.model import MontageTimeline

        plan, errors = self._plan(a)
        if plan is None:
            raise ToolError("Reja sxemaga mos emas / invalid plan: " + "; ".join(errors))
        mid = a["montage_id"]
        detail = self._montage(mid)
        if detail.get("status") == "planning":
            raise ToolError("409 Conflict: montaj hozir rejalashtirilmoqda / montage is being planned")
        tl = self._timeline(detail)
        if plan.base_revision != revision(tl, a.get("selected_video_id")):
            raise ToolError("409 Conflict: Timeline or selection changed; generate a new plan "
                            "(get_timeline'ni qayta chaqiring)")
        out = self._preview(a, plan, tl)  # draft: engine executor'i tekshiradi va qo'llaydi
        saved = self.client.put(f"/v1/montages/{seg(mid)}/timeline", out["timeline"])
        after = MontageTimeline.model_validate(saved.get("timeline") or out["timeline"])
        self.undo.append(UndoEntry(mid, tl.to_json(), revision(after, None)))
        del self.undo[:-UNDO_DEPTH]
        return {"applied": True, "montage_id": mid, "changes": out.get("changes", []),
                "warnings": out.get("warnings", []),
                "base_revision": revision(after, a.get("selected_video_id")),
                "undo_available": len(self.undo)}

    def undo_last_edit(self, a: dict[str, Any]) -> Any:
        from lahza_engine.editing_agent.executor import revision

        mid = a.get("montage_id")
        idx = next((i for i in range(len(self.undo) - 1, -1, -1)
                    if mid is None or self.undo[i].montage_id == mid), None)
        if idx is None:
            raise ToolError("Bekor qilinadigan tahrir yo'q (shu MCP sessiyasida) / nothing to undo")
        entry = self.undo[idx]
        tl = self._timeline(self._montage(entry.montage_id))
        if revision(tl, None) != entry.after_revision:
            self.undo.pop(idx)
            raise ToolError("409 Conflict: montaj tahrirdan keyin boshqa joyda o'zgartirilgan - bekor qilish "
                            "xavfli, o'tkazib yuborildi / montage changed since the edit; undo refused")
        self.client.put(f"/v1/montages/{seg(entry.montage_id)}/timeline", entry.before)
        self.undo.pop(idx)
        return {"undone": True, "montage_id": entry.montage_id, "undo_available": len(self.undo)}

    def render_preview(self, a: dict[str, Any]) -> Any:
        t_ms = a.get("t_ms", 0)
        if a.get("montage_id"):
            if a.get("episode_id") or a.get("clip_id"):
                raise ToolError("montage_id yoki (episode_id + clip_id) - bittasini bering")
            path = f"/v1/montages/{seg(a['montage_id'])}:preview"
        elif a.get("episode_id") and a.get("clip_id"):
            path = f"/v1/episodes/{seg(a['episode_id'])}/clips/{seg(a['clip_id'])}:preview"
        else:
            raise ToolError("montage_id yoki episode_id + clip_id kerak / need montage_id or episode_id+clip_id")
        raw, ctype = self.client.request("POST", path, {"t_ms": t_ms}, timeout_s=120)
        if not ctype.startswith("image/jpeg") or not raw.startswith(b"\xff\xd8"):
            raise ToolError("engine JPEG kadr qaytarmadi")
        if len(raw) > MAX_IMAGE_BYTES:
            raise ToolError("kadr juda katta")
        d = preview_dir()
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        out = d / f"preview-{uuid.uuid4().hex[:12]}.jpg"
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        old = sorted(d.glob("preview-*.jpg"), key=lambda p: p.stat().st_mtime)[:-PREVIEW_KEEP]
        for p in old:
            with contextlib.suppress(OSError):
                p.unlink()
        meta = {"preview_path": str(out), "t_ms": t_ms, "bytes": len(raw), "mime": "image/jpeg"}
        content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}]
        if a.get("include_image", True):
            content.append({"type": "image", "data": base64.b64encode(raw).decode("ascii"),
                            "mimeType": "image/jpeg"})
        return {"content": content, "isError": False}

    def export_clip(self, a: dict[str, Any]) -> Any:
        if a.get("confirm") is not True:
            raise ToolError("Eksport rad etildi: foydalanuvchi tasdig'i kerak - `confirm: true` bering / "
                            "export refused: requires confirm=true after the user agrees")
        out_dir = export_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        if a.get("montage_id"):
            if a.get("episode_id") or a.get("clip_id"):
                raise ToolError("montage_id yoki (episode_id + clip_id) - bittasini bering")
            job = self.client.post(f"/v1/montages/{seg(a['montage_id'])}:render", {"out_dir": str(out_dir)})
        elif a.get("episode_id") and a.get("clip_id"):
            body = {"out_dir": str(out_dir), "platform": a.get("platform", "instagram_reels")}
            job = self.client.post(f"/v1/episodes/{seg(a['episode_id'])}/clips/{seg(a['clip_id'])}:export", body)
        else:
            raise ToolError("montage_id yoki episode_id + clip_id kerak")
        return {"started": True, "export_dir": str(out_dir),
                "job": _pick(job, ("id", "kind", "status", "progress", "stage", "error")),
                "hint": "Holatni job_status bilan kuzating / poll job_status"}

    def job_status(self, a: dict[str, Any]) -> Any:
        job = self.client.get(f"/v1/jobs/{seg(a['job_id'])}")
        out = _pick(job, ("id", "kind", "status", "progress", "stage", "error"))
        res = job.get("result")
        if isinstance(res, dict):  # natijadan faqat qisqa maydonlar (yo'llar - foydalanuvchi uchun)
            out["result"] = {k: v for k, v in res.items()
                             if isinstance(v, (str, int, float, bool)) or v is None}
        return out

    # ---- Ro'yxat ----------------------------------------------------------------------
    def _build(self) -> list[Tool]:
        sel = {"type": "string", "minLength": 1, "maxLength": 128,
               "description": "Tanlangan video element id (ixtiyoriy) / optional selected timeline video id"}
        plan = {"type": "object", "required": ["base_revision", "commands"],
                "properties": {
                    "schema": {"type": "string", "enum": ["lahza.edit-plan/1"]},
                    "base_revision": {"type": "string", "pattern": "^[a-f0-9]{64}$",
                                      "description": "get_timeline natijasidagi base_revision"},
                    "commands": {"type": "array", "maxItems": 12,
                                 "items": {"type": "object", "required": ["tool", "args"],
                                           "properties": {"tool": {"type": "string", "enum": [
                                               "set_format", "set_captions", "add_caption", "set_color",
                                               "freeze_clip"]}, "args": {"type": "object"}}}},
                    "unresolved": {"type": "array", "items": {"type": "string"}}},
                "description":
                "lahza.edit-plan/1: {schema?, base_revision, commands:[{tool,args}], unresolved?}. "
                "Operatsiyalar: set_format{profile}, set_captions{enabled,font_size}, "
                "add_caption{text,start_ms,end_ms}, set_color{preset}, freeze_clip{clip_id,at_ms,duration_ms}."}
        target = {"montage_id": {**ID, "description": "Montaj id"},
                  "episode_id": {**ID, "description": "Epizod id (klip uchun)"},
                  "clip_id": {**ID, "description": "Klip id"}}
        T = Tool
        return [
            T("lahza_status", "Lahza status",
              "Engine ulanishini tekshiradi. / Checks the connection to the running Lahza engine.",
              _obj({}), self.lahza_status, READ),
            T("list_projects", "List projects", "Loyihalar (shoular) ro'yxati. / Lists projects (shows).",
              _obj({}), self.list_projects, READ),
            T("list_episodes", "List episodes",
              "Loyiha epizodlari. / Lists episodes of a project.",
              _obj({"project_id": {**ID, "description": "list_projects dagi id"}}, ["project_id"]),
              self.list_episodes, READ),
            T("list_montages", "List montages",
              "Montajlar (tahrirlanadigan timeline'lar). / Lists montages (editable timelines).",
              _obj({"project_id": {**ID, "description": "Ixtiyoriy filtr / optional filter"}}),
              self.list_montages, READ),
            T("list_clips", "List clips",
              "Epizod kliplari (vaqt, sarlavha, ball). / Lists an episode's clips.",
              _obj({"episode_id": ID,
                    "status": {"type": "string", "enum": ["nomzod", "qabul", "rad", "eksport_qilingan"]},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                   ["episode_id"]), self.list_clips, READ),
            T("get_transcript", "Get transcript",
              "Epizod transkripti, sahifalangan (offset/limit, max_chars). / Paginated, size-bounded "
              "episode transcript.",
              _obj({"episode_id": ID,
                    "offset": {"type": "integer", "minimum": 0, "description": "Gap indeksi"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    "max_chars": {"type": "integer", "minimum": 1000, "maximum": 50_000},
                    "start_ms": {"type": "integer", "minimum": 0},
                    "end_ms": {"type": "integer", "minimum": 1}}, ["episode_id"]),
              self.get_transcript, READ),
            T("get_timeline", "Get timeline",
              "Montaj timeline'ining chegaralangan tavsifi va base_revision. / Bounded montage timeline "
              "summary plus the base_revision required for edit plans.",
              _obj({"montage_id": ID, "selected_video_id": sel}, ["montage_id"]), self.get_timeline, READ),
            T("propose_edit_plan", "Validate edit plan",
              "Rejani tekshiradi va o'zgarishlarni ko'rsatadi, QO'LLAMAYDI. / Validates an edit plan and "
              "lists the resulting changes without applying it.",
              _obj({"montage_id": ID, "plan": plan, "selected_video_id": sel}, ["montage_id", "plan"]),
              self.propose_edit_plan, READ),
            T("apply_edit_plan", "Apply edit plan",
              "Rejani montajga qo'llaydi (base_revision majburiy; eskirgan bo'lsa 409). undo_last_edit "
              "bilan qaytariladi. / Applies a plan to the montage; stale base_revision gives 409; "
              "reversible with undo_last_edit.",
              _obj({"montage_id": ID, "plan": plan, "selected_video_id": sel}, ["montage_id", "plan"]),
              self.apply_edit_plan, WRITE),
            T("undo_last_edit", "Undo last edit",
              "Shu sessiyadagi oxirgi apply_edit_plan'ni bekor qiladi. / Reverts the last edit applied "
              "in this MCP session.",
              _obj({"montage_id": {**ID, "description": "Ixtiyoriy / optional"}}), self.undo_last_edit, WRITE),
            T("render_preview", "Render preview frame",
              "Bitta preview kadri (JPEG) va uning fayl yo'li. / Renders one JPEG preview frame of a montage "
              "or clip.",
              _obj({**target, "t_ms": {"type": "integer", "minimum": 0},
                    "include_image": {"type": "boolean", "description": "Rasmni javobga qo'shish (standart true)"}}),
              self.render_preview, {**READ, "idempotentHint": False}),
            T("export_clip", "Export video",
              "Klip yoki montajni videoga eksport qiladi (Lahza eksport papkasiga). Faqat foydalanuvchi "
              "roziligidan keyin confirm=true bilan. / Exports a clip or montage to the Lahza export folder; "
              "requires confirm=true.",
              _obj({**target, "platform": {"type": "string", "enum": PLATFORMS},
                    "confirm": {"type": "boolean", "description": "Foydalanuvchi tasdiqladi / user confirmed"}},
                   ["confirm"]),
              self.export_clip, {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False,
                                 "openWorldHint": False}),
            T("job_status", "Job status", "Vazifa (eksport) holati. / Status of a background job.",
              _obj({"job_id": ID}, ["job_id"]), self.job_status, READ),
        ]


def _text(obj: Any) -> dict[str, Any]:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n…[javob qisqartirildi / truncated]"
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _error(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": msg[:4000]}], "isError": True}
