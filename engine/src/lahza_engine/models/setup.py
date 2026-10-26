"""Consent-only first-run installation with offline, cached readiness and durable jobs.

One coordinator per resolved model store serializes auto-starts in this engine process.
A filesystem lease also prevents another engine process from downloading into the same store.
Interrupted jobs are reported as failed, never silently restarted by a GET.
"""
from __future__ import annotations

import importlib
import json
import os
import struct
import sys
import threading
from pathlib import Path
from typing import Any

from lahza_engine.core.jobs import Job, JobManager
from lahza_engine.core.runner import Cancelled
from lahza_engine.media.tools import run
from lahza_engine.models import local_aligner, local_llm
from lahza_engine.models import local_bootstrap as bootstrap
from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import sha256_file
from lahza_engine.models.store import InstalledModel, ModelStore

SIZES = {"asr": 149_000_000, "vad": 2328599, "align": local_aligner.MODEL_SIZE,
         "llm": local_llm.MODEL_SIZE}
# Birinchi ishga tushirishda o'rnatiladigan modellar (tartib - yuklash tartibi).
TASKS = (Task.ASR, Task.VAD, Task.ALIGN, Task.LLM)
_TERMINAL = {"done", "failed", "cancelled"}
_COORDINATORS: dict[Path, Setup] = {}
_COORDINATOR_LOCK = threading.Lock()


def coordinator(store: ModelStore, jobs: JobManager) -> Setup:
    with _COORDINATOR_LOCK:
        key = store.root.resolve()
        previous = _COORDINATORS.get(key)
        # A live installer must remain shared even when two API States use the same store.
        if previous is None or (previous.jobs is not jobs and
                                (previous.job is None or previous.job.status in _TERMINAL)):
            previous = _COORDINATORS[key] = Setup(store, jobs)
        return previous


def _fingerprint(path: Path) -> tuple:
    stat = path.stat()
    return (str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _lease(path: Path):
    """Nonblocking OS lock; released by the OS on crashes. Never delete the lock inode."""
    handle = path.open("a+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


class Setup:
    def __init__(self, store: ModelStore, jobs: JobManager) -> None:
        self.store, self.jobs = store, jobs
        self.lock = threading.RLock()
        self.journal = store.root / "setup-job.json"
        self.lease_path = store.root / "setup.lock"
        self.job: Job | None = None
        self.external = False
        self._validation: dict[tuple, tuple[bool, str | None]] = {}
        self._runtime_cache: dict[tuple, tuple[bool, str | None]] = {}
        self._recover()

    def _recover(self) -> None:
        if not self.journal.exists():
            return
        try:
            data = json.loads(self.journal.read_text(encoding="utf-8"))
            self.job = Job(**data)
            self.external = False
            if self.job.status not in _TERMINAL:
                lease = _lease(self.lease_path)
                if lease is not None:
                    try:
                        self.job.status = "failed"
                        self.job.error = "Sozlash uzilib qolgan. Davom ettirish uchun qayta urining."
                        self._save(self.job)
                    finally:
                        lease.close()
                else:
                    self.external = True
            self.jobs.jobs[self.job.id] = self.job
        except (ValueError, TypeError, OSError):
            # A broken journal must not claim a successful installation or block retry.
            self.job = None

    def _save(self, job: Job) -> None:
        with self.lock:
            self._write(job)

    def _write(self, job: Job) -> None:
        temporary = self.journal.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(job.public(), stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.journal)

    def _runtime(self, names: tuple[str, ...]) -> tuple[bool, str | None]:
        key = None
        try:
            base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "bin"
            configured = os.environ.get("LAHZA_BIN_DIR")
            roots = [Path(configured)] if configured else [base]
            paths = []
            for name in names:
                filename = name + (".exe" if sys.platform == "win32" else "")
                path = next((root / filename for root in roots if (root / filename).is_file()), None)
                if path is None:
                    raise RuntimeError(f"{name} ilova paketida yo‘q. To‘liq desktop paketini qayta o‘rnating.")
                paths.append(path)
            # Include sibling shared libraries so repairs invalidate failed preflights too.
            siblings = {p for path in paths for p in path.parent.iterdir()
                        if p.is_file() and p.suffix in (".dll", ".dylib", ".so")}
            key = tuple(_fingerprint(p) for p in [*paths, *sorted(siblings)])
            if key not in self._runtime_cache:
                for path in paths:
                    flag = "--version" if path.stem == "llama-server" else "-version"
                    if run([path, flag], timeout=15).returncode != 0:
                        raise RuntimeError(f"{path.name} ishga tushmadi. Desktop paketini qayta o‘rnating.")
                if "ffmpeg" in names:
                    filters = run([paths[0], "-hide_banner", "-filters"], timeout=15)
                    if filters.returncode or not any(" ass " in line for line in filters.stdout.splitlines()):
                        raise RuntimeError("ffmpeg subtitr (libass) imkoniyatisiz. To‘liq desktop paketini o‘rnating.")
                self._runtime_cache[key] = (True, None)
            return self._runtime_cache[key]
        except Exception as exc:  # readiness is a report, not an API error
            if key is not None:
                self._runtime_cache[key] = (False, str(exc))
            return False, str(exc)

    def _default(self, task: Task) -> InstalledModel | None:
        model = self.store.default_for(task)
        return model if model is not None and model.task == task else None

    def _model(self, model: InstalledModel | None) -> tuple[bool, str | None]:
        if model is None:
            return False, "Birinchi foydalanish uchun model yuklanadi."
        try:
            root = Path(model.path)
            files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
            if not files or not root.exists():
                raise ValueError("Model fayllari yo‘q. Qayta yuklashni boshlang.")
            if root.is_file():
                files += [p for p in (root.parent / "provenance.json",
                                      root.parent / "metadata/SOURCE.json") if p.is_file()]
                metadata_dir = root.parent / "metadata"
                if metadata_dir.is_dir():
                    files += sorted(p for p in metadata_dir.iterdir() if p.is_file() and p not in files)
            key = (model.task.value, model.id, model.version, *(_fingerprint(p) for p in files))
            if key not in self._validation:
                try:
                    self._validate_model(model, root)
                    value = (True, None)
                except Exception as exc:
                    value = (False, f"Model ishlatishga tayyor emas: {exc}. Qayta urining.")
                # Keep only current fingerprints; polling must not hash GBs or reload ML models.
                if len(self._validation) > 32:
                    self._validation.clear()
                self._validation[key] = value
            return self._validation[key]
        except Exception as exc:
            return False, f"Model tekshiruvi: {exc}. Qayta urining."

    def _validate_model(self, model: InstalledModel, root: Path) -> None:
        base = root if root.is_dir() else root.parent
        provenance = base / "provenance.json"
        if provenance.is_file():
            data = json.loads(provenance.read_text(encoding="utf-8"))
            for record in data.get("files", []):
                path = (base / record["path"]).resolve()
                if not path.is_relative_to(base.resolve()) or not path.is_file():
                    raise ValueError("provenance fayli topilmadi")
                if record.get("sha256") and sha256_file(path) != record["sha256"]:
                    raise ValueError(f"sha256 mos emas: {path.name}")
        if model.task == Task.ASR:
            if not (root / "model.bin").is_file():
                candidates = [root] if root.is_file() else sorted(root.rglob("*.bin"))
                candidates += [] if root.is_file() else sorted(root.rglob("*.gguf"))
                if not candidates:
                    raise ValueError("ASR model fayli topilmadi")
                with candidates[0].open("rb") as stream:
                    header = stream.read(16)
                if len(header) < 16 or header[:4] not in (b"lmgg", b"ggml", b"GGUF"):
                    raise ValueError("ASR model sarlavhasi buzilgan")
                ready, detail = self._runtime(("whisper-cli",))
                if not ready:
                    raise ValueError(detail)
                return
            if model.id == bootstrap.MODEL_ID and sha256_file(root / "model.bin") != bootstrap.WEIGHTS_SHA256:
                raise ValueError("ASR sha256 mos emas")
            from faster_whisper import WhisperModel
            WhisperModel(str(root), device="cpu", compute_type="int8", local_files_only=True)
        elif model.task == Task.VAD:
            from lahza_engine.vad.silero_onnx import SileroOnnxVad
            path = root if root.is_file() else next(root.rglob("*.onnx"))
            if model.id == "custom:silero-v5.1.2" and sha256_file(path) != bootstrap.SILERO_SHA256:
                raise ValueError("VAD sha256 mos emas")
            SileroOnnxVad(path)
        elif model.task == Task.ALIGN:
            from lahza_engine.align.ctc_onnx import CtcAligner

            if model.id == local_aligner.MODEL_ID:
                local_aligner.verify_installation(root)
            aligner = CtcAligner.from_dir(root)
            if aligner.tok.sep is None or not aligner.tok.word_tokens("oʻzbek"):
                raise ValueError("aligner lug'ati o'zbek lotin harflarini qo'llamaydi")
        elif model.task == Task.LLM:
            from lahza_engine.editing_agent.planner import local_model

            model_id, path = local_model(self.store)
            if model_id != model.id:
                raise ValueError("LLM standart model bilan mos emas")
            with path.open("rb") as stream:
                header = stream.read(24)
            if len(header) != 24 or header[:4] != b"GGUF":
                raise ValueError("GGUF sarlavhasi buzilgan")
            version, tensors, metadata = struct.unpack("<IQQ", header[4:])
            if version not in (2, 3) or not tensors or not metadata:
                raise ValueError("GGUF metadata buzilgan")
            if model.id == local_llm.MODEL_ID:
                local_llm.verify_installation(path)

    def status(self) -> dict[str, Any]:
        with self.lock:
            if self.external:
                self._recover()
            components = []
            for task in TASKS:
                try:
                    ready, detail = self._model(self._default(task))
                except (ValueError, OSError) as exc:
                    ready, detail = False, f"Model ro‘yxati buzilgan: {exc}"
                components.append({"id": task.value, "ready": ready, "required": True,
                                   "download_bytes": 0 if ready else SIZES[task.value], "detail": detail})
            for identifier, names in (("render", ("ffmpeg", "ffprobe")),
                                      ("llm_runtime", ("llama-server",))):
                ready, detail = self._runtime(names)
                components.append({"id": identifier, "ready": ready, "required": True,
                                   "download_bytes": 0, "detail": detail})
            return {"ready": all(c["ready"] for c in components), "components": components,
                    "job": self.job.public() if self.job else None}

    def start(self, invalidate) -> Job:
        with self.lock:
            if self.external:
                self._recover()
            if self.job is not None and self.job.status not in _TERMINAL:
                # Mirror an external active lease's durable progress into this engine.
                return self.job
            lease = _lease(self.lease_path)
            if lease is None:
                self._recover()
                if self.job is None:
                    raise RuntimeError("Sozlash boshqa engine jarayonida boshlanmoqda. Qayta urining.")
                return self.job
            state = self.status()
            if state["ready"] and self.job is not None and self.job.status == "done":
                lease.close()
                return self.job
            gate = threading.Event()

            def work(job: Job) -> dict[str, Any]:
                gate.wait()
                try:
                    self._checkpoint(job, "preflight", 0)
                    for component in self.status()["components"]:
                        if component["id"] in ("render", "llm_runtime") and not component["ready"]:
                            raise RuntimeError(component["detail"])
                    # Python inference dependencies belong in the desktop sidecar too.
                    for task, module in ((Task.ASR, "faster_whisper"), (Task.VAD, "onnxruntime"),
                                         (Task.ALIGN, "onnxruntime")):
                        if self._model(self._default(task))[0]:
                            continue
                        try:
                            importlib.import_module(module)
                        except ImportError as exc:
                            raise RuntimeError(f"{module} ilova paketida yo‘q. To‘liq desktop paketini qayta o‘rnating.") from exc
                    installed = []
                    installers = ((Task.ASR, bootstrap.bootstrap), (Task.VAD, bootstrap.bootstrap_vad),
                                  (Task.ALIGN, local_aligner.install_model),
                                  (Task.LLM, local_llm.install_model))
                    steps = len(installers)
                    for index, (task, installer) in enumerate(installers):
                        self._checkpoint(job, task.value, index / steps)
                        if self._model(self._default(task))[0]:
                            continue

                        def progress(have, total, index=index, task=task, steps=steps):
                            job.meta["download_bytes"] = have
                            job.meta["download_total"] = total
                            fraction = min(1, have / total) if total else 0
                            self._checkpoint(job, task.value, (index + fraction) / steps)

                        model = installer(self.store, consent=True, progress=progress)
                        if job.cancel.is_set():
                            raise Cancelled()
                        # A missing/broken previous default may be replaced. Healthy ones were skipped.
                        self.store.set_default(task, model.id)
                        if not self._model(model)[0]:
                            raise RuntimeError(f"{task.value}: o‘rnatilgan model tekshiruvdan o‘tmadi")
                        installed.append(model.id)
                        invalidate()
                    self._checkpoint(job, "verify", 1)
                    if not self.status()["ready"]:
                        raise RuntimeError("Sozlash tekshiruvi tugamadi. Qayta urining.")
                    job.result = {"installed": installed, "ready": True}
                    job.status, job.progress = "done", 1.0
                    return job.result
                except Cancelled:
                    job.status = "cancelled"
                    raise
                except Exception as exc:
                    job.status, job.error = "failed", str(exc)
                    raise
                finally:
                    self._save(job)

            def changed(job: Job) -> None:
                self._save(job)
                if job.status in _TERMINAL:
                    lease.close()

            try:
                self.job = self.jobs.submit("install", work, on_change=changed, op="setup")
                self._save(self.job)
                return self.job
            except BaseException:
                lease.close()
                raise
            finally:
                gate.set()

    def _checkpoint(self, job: Job, stage: str, fraction: float) -> None:
        cancellation = self.store.root / "setup-cancel.json"
        if cancellation.exists():
            try:
                if json.loads(cancellation.read_text()).get("id") == job.id:
                    job.cancel.set()
            except (OSError, ValueError):
                pass
        if job.cancel.is_set():
            raise Cancelled()
        self.jobs.progress(job, stage, fraction)

    def cancel(self, job_id: str) -> None:
        with self.lock:
            if self.job is None or self.job.id != job_id:
                return
            self.job.cancel.set()
            marker = self.store.root / "setup-cancel.json"
            temporary = marker.with_suffix(".tmp")
            temporary.write_text(json.dumps({"id": job_id}), encoding="utf-8")
            temporary.replace(marker)
