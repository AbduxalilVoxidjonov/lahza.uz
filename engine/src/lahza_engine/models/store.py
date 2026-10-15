"""O'rnatilgan modellar ombori: `Models/<vazifa>/<model_id>/` + `installed.json` (TZ 13-bo'lim).

Katalogdan tashqari modellar (ilg'or sozlama): `Models/<vazifa>/` ga tashlangan fayllar skanerlanadi.
Faqat format sarlavhasi tekshirilgan fayllar qabul qilinadi; hech narsa ishga tushirilmaydi.
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from lahza_engine.models.catalog import CatalogEntry, Task
from lahza_engine.models.downloader import ProgressFn, download

GGUF_MAGIC = b"GGUF"
_EXECUTABLE_MAGICS = (b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"#!")


class InstalledModel(BaseModel):
    id: str
    task: Task
    version: str
    path: str
    source: str = "catalog"  # catalog | custom
    installed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    self_test_ok: bool | None = None
    verified: bool = True  # custom modellar uchun False: "sifat kafolatlanmaydi"


class Registry(BaseModel):
    models: list[InstalledModel] = Field(default_factory=list)
    defaults: dict[str, str] = Field(default_factory=dict)


def sniff_custom_file(path: Path) -> str | None:
    """Fayl turini sarlavhadan aniqlaydi. Qabul qilinmasa - None."""
    with path.open("rb") as f:
        head = f.read(8)
    if any(head.startswith(m) for m in _EXECUTABLE_MAGICS):
        return None
    if head.startswith(GGUF_MAGIC):
        return "gguf"
    return None


class ModelStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @property
    def _registry_path(self) -> Path:
        return self.root / "installed.json"

    def load(self) -> Registry:
        if not self._registry_path.exists():
            return Registry()
        return Registry.model_validate_json(self._registry_path.read_text(encoding="utf-8"))

    def _save(self, reg: Registry) -> None:
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(reg.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self._registry_path)

    def model_dir(self, task: Task, model_id: str) -> Path:
        return self.root / task.value / model_id

    def install(self, entry: CatalogEntry, progress: ProgressFn | None = None) -> InstalledModel:
        if entry.status != "approved":
            raise ValueError(f"{entry.id} hali tasdiqlanmagan (status={entry.status})")
        target = self.model_dir(entry.task, entry.id)
        for f in entry.files:
            download(f.urls, target / f.path, f.sha256, f.size_bytes, progress)
        im = InstalledModel(id=entry.id, task=entry.task, version=entry.version, path=str(target))
        with self._lock:
            reg = self.load()
            reg.models = [m for m in reg.models if m.id != entry.id] + [im]
            reg.defaults.setdefault(entry.task.value, entry.id)
            self._save(reg)
        return im

    def set_default(self, task: Task, model_id: str) -> None:
        with self._lock:
            reg = self.load()
            if not any(m.id == model_id and m.task == task for m in reg.models):
                raise KeyError(model_id)
            reg.defaults[task.value] = model_id
            self._save(reg)

    def get(self, model_id: str) -> InstalledModel | None:
        return next((m for m in self.load().models if m.id == model_id), None)

    def _inside_root(self, p: Path) -> bool:
        try:
            p.resolve().relative_to(self.root.resolve())
            return True
        except ValueError:
            return False

    def remove(self, model_id: str) -> InstalledModel:
        """Fayllarni va registry yozuvini o'chiradi. Standart bo'lsa - shu vazifadagi boshqa
        modelga o'tadi, boshqasi bo'lmasa standart o'chiriladi."""
        with self._lock:
            reg = self.load()
            m = next((x for x in reg.models if x.id == model_id), None)
            if m is None:
                raise KeyError(model_id)
            p = Path(m.path)
            # Xavfsizlik: faqat Models/ ichidagi fayllar o'chiriladi.
            if p.exists() and self._inside_root(p) and p.resolve() != self.root.resolve():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            reg.models = [x for x in reg.models if x.id != model_id]
            if reg.defaults.get(m.task.value) == model_id:
                other = next((x for x in reg.models if x.task == m.task), None)
                if other is not None:
                    reg.defaults[m.task.value] = other.id
                else:
                    reg.defaults.pop(m.task.value, None)
            self._save(reg)
            return m

    def set_self_test(self, model_id: str, ok: bool) -> None:
        with self._lock:
            reg = self.load()
            for m in reg.models:
                if m.id == model_id:
                    m.self_test_ok = ok
            self._save(reg)

    def register(self, models: list[InstalledModel]) -> None:
        """Tashqaridan (masalan .lzpack) kelgan yozuvlarni qo'shadi; bir xil ID almashtiriladi."""
        with self._lock:
            reg = self.load()
            ids = {m.id for m in models}
            reg.models = [m for m in reg.models if m.id not in ids] + list(models)
            for m in models:
                reg.defaults.setdefault(m.task.value, m.id)
            self._save(reg)

    def default_for(self, task: Task) -> InstalledModel | None:
        reg = self.load()
        mid = reg.defaults.get(task.value)
        return next((m for m in reg.models if m.id == mid), None)

    def scan_custom(self) -> list[InstalledModel]:
        """`Models/llm/*.gguf` kabi qo'lda qo'shilgan fayllarni ro'yxatga oladi."""
        added: list[InstalledModel] = []
        with self._lock:
            reg = self.load()
            known = {Path(m.path).resolve() for m in reg.models}
            llm_dir = self.root / Task.LLM.value
            for p in sorted(llm_dir.glob("*.gguf")) if llm_dir.exists() else []:
                if p.resolve() in known or sniff_custom_file(p) != "gguf":
                    continue
                im = InstalledModel(
                    id=f"custom:{p.stem}", task=Task.LLM, version="custom", path=str(p),
                    source="custom", verified=False,
                )
                reg.models.append(im)
                added.append(im)
            if added:
                self._save(reg)
        return added

    def export_manifest(self) -> str:
        """.lzpack uchun manifest (oflayn ko'chirish)."""
        return json.dumps(self.load().model_dump(mode="json"), ensure_ascii=False, indent=2)
