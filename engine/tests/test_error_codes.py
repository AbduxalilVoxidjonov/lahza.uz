"""Barqaror xato kodlari (core/errors.py): vazifa meta'si va tahlil navbati elementi."""

from __future__ import annotations

import errno
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from test_batch_queue import Lib

from lahza_engine.core import errors as E
from lahza_engine.core.batch import AnalysisQueue
from lahza_engine.core.events import EventBus
from lahza_engine.core.jobs import Job, JobManager
from lahza_engine.core.services import MissingModel
from lahza_engine.media.probe import MediaError
from lahza_engine.media.tools import ToolNotFound
from lahza_engine.models.downloader import DownloadError
from lahza_engine.render.capabilities import LibassMissing


@pytest.mark.parametrize(("exc", "code", "params"), [
    (FileNotFoundError(errno.ENOENT, "No such file", "/a/b/video.mp4"), E.FILE_NOT_FOUND, {"path": "video.mp4"}),
    (OSError(errno.ENOSPC, "No space left on device"), E.DISK_FULL, {}),
    (PermissionError(errno.EACCES, "Permission denied", "/x/out.mp4"), E.PERMISSION_DENIED, {"path": "out.mp4"}),
    (MemoryError(), E.OUT_OF_MEMORY, {}),
    (RuntimeError("CUDA out of memory. Tried to allocate 2 GiB"), E.OUT_OF_MEMORY, {}),
    (TimeoutError(), E.TIMEOUT, {}),
    (subprocess.TimeoutExpired(["ffmpeg"], 5), E.TIMEOUT, {}),
    (subprocess.CalledProcessError(1, ["ffmpeg"]), E.FFMPEG_FAILED, {"rc": "1"}),
    (ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused"), E.NETWORK, {}),
    (MissingModel("ASR modeli o'rnatilmagan - Sozlamalar > Modellar"), E.MODEL_MISSING, {}),
    (ToolNotFound("'ffmpeg' topilmadi. LAHZA_BIN_DIR yoki PATH ni tekshiring."), E.TOOL_MISSING, {"tool": "ffmpeg"}),
    (LibassMissing(), E.LIBASS_MISSING, {}),
    (MediaError("ffprobe xatosi: moov atom not found"), E.MEDIA_INVALID, {}),
    (MediaError("Videoda ovoz yo'lagi topilmadi - boshqa fayl tanlang"), E.NO_AUDIO, {}),
    (MediaError("fayl topilmadi: klip.mov"), E.FILE_NOT_FOUND, {"path": "klip.mov"}),
    (DownloadError("HTTP 503: https://x"), E.DOWNLOAD_FAILED, {}),
    (DownloadError("diskda joy yetarli emas"), E.DISK_FULL, {}),
    (RuntimeError("render xatosi (ffmpeg 187): Invalid argument"), E.FFMPEG_FAILED, {"rc": "187"}),
    (E.CodedError(E.FFMPEG_FAILED, "stderr...", rc=1), E.FFMPEG_FAILED, {"rc": "1"}),
])
def test_classify_known(exc: BaseException, code: str, params: dict[str, str]) -> None:
    assert E.classify(exc) == (code, params)


def test_classify_unknown_and_own_code() -> None:
    assert E.classify(RuntimeError("yiqildi")) is None
    assert E.classify(ValueError()) is None
    assert E.classify_message(None) is None

    class Own(RuntimeError):
        code = "unsupported_codec"
        params = {"codec": "av1", "label": "AV1"}

    assert E.classify(Own("x")) == ("unsupported_codec", {"codec": "av1", "label": "AV1"})


def _run_job(fn) -> Job:
    jobs = JobManager(EventBus())
    try:
        job = jobs.submit("export", fn)
        end = time.time() + 5
        while job.status not in ("done", "failed", "cancelled") and time.time() < end:
            time.sleep(0.01)
        return job
    finally:
        jobs.shutdown()


def test_job_meta_gets_code_and_keeps_error_text() -> None:
    def boom(job: Job) -> dict[str, Any]:
        raise OSError(errno.ENOSPC, "No space left on device")

    job = _run_job(boom)
    assert job.status == "failed"
    assert job.error == "[Errno 28] No space left on device"  # eski matn saqlanadi
    assert job.meta["error_code"] == "disk_full" and job.meta["error_params"] == {}
    pub = job.public()
    assert pub["meta"]["error_code"] == "disk_full"


def test_job_meta_unknown_error_has_no_code() -> None:
    def boom(job: Job) -> dict[str, Any]:
        raise RuntimeError("kutilmagan narsa")

    job = _run_job(boom)
    assert job.status == "failed" and job.error == "kutilmagan narsa"
    assert "error_code" not in job.meta


def test_job_meta_preset_code_not_overwritten() -> None:
    def boom(job: Job) -> dict[str, Any]:
        job.meta["error_code"] = "unsupported_codec"
        raise FileNotFoundError("x")

    assert _run_job(boom).meta["error_code"] == "unsupported_codec"


# ---- tahlil navbati -------------------------------------------------------------------------

def _wait(pred, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return
        time.sleep(0.01)
    raise TimeoutError


def test_queue_item_exposes_error_code(tmp_path: Path) -> None:
    lib = Lib(tmp_path)
    jobs = JobManager(EventBus())

    def starter(item: dict[str, Any], on_change) -> Job:
        path = item["path"]
        if path == "yoq.mp4":
            raise E.CodedError(E.FILE_NOT_FOUND, f"fayl topilmadi: /a/{path}", path=path)

        def work(job: Job) -> dict[str, Any]:
            if path == "full.mp4":
                raise OSError(errno.ENOSPC, "No space left on device")
            raise RuntimeError("noma'lum")

        return jobs.submit("analyze", work, on_change=on_change)

    try:
        q = AnalysisQueue(lib, jobs, starter)
        q.add("s1", ["yoq.mp4", "full.mp4", "x.mp4"])
        _wait(lambda: all(x["status"] == "failed" for x in q.list()))
        st = {x["path"]: x for x in q.list()}
        assert st["yoq.mp4"]["error_code"] == "file_not_found"
        assert st["yoq.mp4"]["error_params"] == {"path": "yoq.mp4"}
        assert st["yoq.mp4"]["error"] == "fayl topilmadi: /a/yoq.mp4"
        assert st["full.mp4"]["error_code"] == "disk_full"
        assert st["x.mp4"]["error_code"] is None and st["x.mp4"]["error"] == "noma'lum"

        # Engine qayta ishga tushgandan keyin (xotiradagi kodlar yo'q) - matndan tiklanadi.
        q2 = AnalysisQueue(lib, jobs, starter)
        st2 = {x["path"]: x for x in q2.list()}
        assert st2["yoq.mp4"]["error_code"] == "file_not_found"
        assert st2["yoq.mp4"]["error_params"] == {"path": "yoq.mp4"}
        assert st2["full.mp4"]["error_code"] == "disk_full"

        # Qayta urinishda kod tozalanadi.
        item = q.retry(st["x.mp4"]["id"])
        assert item["error_code"] is None and item["error_params"] is None
    finally:
        jobs.shutdown()
