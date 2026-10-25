"""Modellar: katalog to'plami, o'rnatish, o'chirish, standart, o'z-o'zini sinash, .lzpack."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from lahza_engine.api.state import State
from lahza_engine.core.jobs import Job
from lahza_engine.core.runner import Cancelled
from lahza_engine.models import catalog as cat
from lahza_engine.models.hardware import classify, detect
from lahza_engine.models.store import InstalledModel


class InstallIn(BaseModel):
    entry_ids: list[str] | None = None
    consent: bool = False  # NFR-01: tarmoqdan foydalanishga foydalanuvchi roziligi


class PackIn(BaseModel):
    path: str
    model_ids: list[str] | None = None


class _SingleModelStore:
    """build_services() uchun: faqat sinalayotgan modelni beradi (boshqa vazifalar yuklanmaydi)."""

    def __init__(self, model: InstalledModel) -> None:
        self.model = model

    def default_for(self, task: cat.Task) -> InstalledModel | None:
        return self.model if task == self.model.task else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def self_test(s: State, m: InstalledModel) -> tuple[bool, str]:
    """Fayllar mavjudligi + katalogdagi sha256 + backend yuklanishi (services build orqali)."""
    p = Path(m.path)
    if not p.exists() or (p.is_dir() and not any(p.iterdir())):
        return False, "model fayllari topilmadi"
    notes: list[str] = []
    try:
        entry = next((e for e in s.catalog().entries if e.id == m.id), None)
    except Exception:  # noqa: BLE001 - katalogsiz ham sinov davom etadi
        entry = None
    if entry is not None and m.source == "catalog":
        for f in entry.files:
            fp = Path(m.path) / f.path
            if not fp.exists():
                return False, f"fayl yo'q: {f.path}"
            if f.sha256 and _sha256(fp) != f.sha256.lower():
                return False, f"sha256 mos emas: {f.path}"
        notes.append("sha256 mos")
    else:
        notes.append("katalogda sha256 yo'q - tekshirilmadi")

    from lahza_engine.core.services import build_services

    try:
        svc = build_services(_SingleModelStore(m))  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        return False, f"backend yuklanmadi: {type(e).__name__}"
    loaded: dict[cat.Task, Callable[[], Any]] = {
        cat.Task.ASR: lambda: svc.asr,
        cat.Task.DIARIZATION: lambda: svc.diarizer,
        cat.Task.LLM: lambda: svc.llm_model_path,
        cat.Task.ALIGN: lambda: getattr(svc, "aligner", None),
        cat.Task.VAD: lambda: svc.vad,
        cat.Task.VISION: lambda: svc.face_detector,
    }
    if loaded[m.task]() is None:
        return False, "backend yuklanmadi (format yoki kutubxona yo'q)"
    notes.append("backend yuklandi")
    return True, "; ".join(notes)


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/catalog/bundle")
    def bundle(s: State = Depends(auth)) -> dict[str, Any]:
        hw = detect(str(Path.home()))
        tier = classify(hw).tier
        items = cat.select_bundle(s.catalog(), hw, tier)
        return {"tier": tier, "items": [i.model_dump(mode="json") for i in items]}

    @app.get("/v1/models")
    def models(s: State = Depends(auth)) -> dict[str, Any]:
        return s.store.load().model_dump(mode="json")

    @app.post("/v1/models:scan")
    def scan(s: State = Depends(auth)) -> dict[str, Any]:
        return {"added": [m.model_dump(mode="json") for m in s.store.scan_custom()]}

    @app.post("/v1/models:bootstrap")
    def bootstrap_model(body: InstallIn, s: State = Depends(auth)) -> dict[str, Any]:
        if not body.consent:
            raise HTTPException(400, "model yuklash uchun foydalanuvchi roziligi kerak (consent=true)")
        if body.entry_ids is not None:
            raise HTTPException(400, "boshlang'ich model uchun entry_ids berilmaydi")
        from lahza_engine.models.local_bootstrap import bootstrap

        def work(job: Job) -> dict[str, Any]:
            def progress(have: int, total: int | None) -> None:
                if job.cancel.is_set():
                    raise Cancelled()
                s.jobs.progress(job, "asr", have / total if total else 0.0)

            progress(0, None)
            installed = bootstrap(s.store, consent=True, progress=progress)
            s.invalidate_services()
            return {"installed": [installed.id], "catalog_approved": False}

        return s.jobs.submit("install", work, op="bootstrap").public()

    @app.post("/v1/models:install")
    def install(body: InstallIn, s: State = Depends(auth)) -> dict[str, Any]:
        if not body.consent:
            raise HTTPException(400, "model yuklash uchun foydalanuvchi roziligi kerak (consent=true)")
        catalog = s.catalog()
        hw = detect(str(Path.home()))
        chosen = [i.entry for i in cat.select_bundle(catalog, hw, classify(hw).tier) if i.entry]
        if body.entry_ids:
            chosen = [e for e in catalog.entries if e.id in body.entry_ids]
        # ASR birinchi: dastur tezroq ishga tayyor bo'lsin (TZ 13-bo'lim).
        chosen.sort(key=lambda e: 0 if e.task == cat.Task.ASR else 1)

        def work(job: Job) -> dict[str, Any]:
            done = []
            for i, e in enumerate(chosen):
                if job.cancel.is_set():
                    raise Cancelled()

                def prog(have: int, total: int | None, _i: int = i, _id: str = e.id) -> None:
                    frac = (have / total) if total else 0.0
                    s.jobs.progress(job, _id, (_i + frac) / max(1, len(chosen)))

                s.store.install(e, prog)
                done.append(e.id)
            s.invalidate_services()
            return {"installed": done}

        return s.jobs.submit("install", work).public()

    @app.delete("/v1/models/{model_id}")
    def delete_model(model_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        try:
            s.store.remove(model_id)
        except KeyError as e:
            raise HTTPException(404, "model topilmadi") from e
        s.invalidate_services()
        return {"ok": True}

    @app.post("/v1/models/{model_id}:default")
    def set_default(model_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        m = s.store.get(model_id)
        if m is None:
            raise HTTPException(404, "model topilmadi")
        s.store.set_default(m.task, model_id)
        s.invalidate_services()
        return {"ok": True}

    @app.post("/v1/models/{model_id}:test")
    def test_model(model_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        m = s.store.get(model_id)
        if m is None:
            raise HTTPException(404, "model topilmadi")
        ok, detail = self_test(s, m)
        s.store.set_self_test(model_id, ok)
        return {"ok": ok, "detail": detail}

    @app.post("/v1/models:export-pack")
    def export_pack(body: PackIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.models import lzpack

        out = Path(body.path)
        if out.suffix != ".lzpack":
            raise HTTPException(400, "fayl kengaytmasi .lzpack bo'lishi kerak")
        if not out.parent.is_dir():
            raise HTTPException(400, "papka topilmadi")
        if not s.store.load().models:
            raise HTTPException(409, "o'rnatilgan model yo'q")

        def work(job: Job) -> dict[str, Any]:
            try:
                return lzpack.export_pack(
                    s.store, out, body.model_ids, os.environ.get("LAHZA_PACK_PRIVKEY") or None,
                    progress=lambda f: s.jobs.progress(job, "export-pack", f),
                    is_cancelled=job.cancel.is_set)
            except lzpack.PackError:
                if job.cancel.is_set():
                    raise Cancelled() from None
                raise

        return s.jobs.submit("pack", work, op="export", path=str(out)).public()

    @app.post("/v1/models:import-pack")
    def import_pack(body: PackIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.models import lzpack

        src = Path(body.path)
        if not src.is_file():
            raise HTTPException(400, "fayl topilmadi")

        def work(job: Job) -> dict[str, Any]:
            try:
                res = lzpack.import_pack(
                    s.store, src, progress=lambda f: s.jobs.progress(job, "import-pack", f),
                    is_cancelled=job.cancel.is_set)
            except lzpack.PackError:
                if job.cancel.is_set():
                    raise Cancelled() from None
                raise
            s.invalidate_services()
            return res

        return s.jobs.submit("pack", work, op="import", path=str(src)).public()
