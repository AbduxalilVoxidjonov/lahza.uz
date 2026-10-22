"""Fayl-asosidagi IPC (`lahza.ipc/1`) - Adobe plaginlari uchun tarmoqsiz zaxira transport (docs/04).

Plagin tomoni: `adobe/premiere/src/transport.ts` (`fileIpcFetch`). Protokol:

* papkalar `<data_dir>/ipc/requests/` va `<data_dir>/ipc/responses/` (0700);
* plagin `requests/<id>.json.tmp` yozib `requests/<id>.json` ga rename qiladi:
  `{"v":1,"id","method","path":"/v1/...","headers":{"Authorization":"Bearer ..."},"body":JSON|null,"created_at"}`;
* engine faylni o'qiydi, o'chiradi va mavjud FastAPI ilovasini ichki ASGI chaqiruvi bilan bajaradi
  (`httpx.ASGITransport`, server event loop'ida) - token, validatsiya, xatolar oddiy HTTP bilan aynan bir xil;
* javob `responses/<id>.json.tmp` -> rename `responses/<id>.json`: `{"v":1,"id","status","body"}`.

Qoidalar: id faqat `[A-Za-z0-9-]{8,64}` (boshqa nomli fayllar javobsiz o'chiriladi - yo'l injeksiyasi yo'q);
`.tmp` e'tiborsiz; so'rov fayli <= 1 MB (katta - 413 javob); 5 daqiqadan eski fayllar tozalanadi;
javob JSON bo'lmasa (JPEG preview, video proksi) - 502 va o'zbekcha `detail`.
Faqat `serve --discovery` yoki `LAHZA_IPC=1` da yoqiladi. Oddiy polling sikli (150 ms).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

IPC_SCHEMA = "lahza.ipc/1"
ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
MAX_REQUEST_BYTES = 1024 * 1024
MAX_AGE_S = 300.0
POLL_S = 0.15
CLEANUP_EVERY_S = 10.0
MAX_PARALLEL = 8
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


def ipc_enabled(discovery: bool = False) -> bool:
    return discovery or os.environ.get("LAHZA_IPC", "").strip().lower() in ("1", "true", "yes")


def ipc_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "ipc"


def _private_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sys.platform != "win32":
        os.chmod(p, 0o700)


def _write_atomic(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


class IpcServer:
    def __init__(self, app, data_dir: Path, poll_s: float = POLL_S) -> None:
        self.app = app
        self.root = ipc_dir(data_dir)
        self.req_dir = self.root / "requests"
        self.res_dir = self.root / "responses"
        self.poll_s = poll_s
        self._busy: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._last_cleanup = 0.0
        self._sem: asyncio.Semaphore | None = None

    def prepare(self) -> None:
        for d in (self.root, self.req_dir, self.res_dir):
            _private_dir(d)

    # --- Asosiy sikl ------------------------------------------------------------------------------

    async def run(self) -> None:
        """Server event loop'ida ishlaydigan polling sikli (lifespan bekor qilguncha)."""
        self.prepare()
        try:
            while True:
                await self.tick()
                await asyncio.sleep(self.poll_s)
        finally:
            for t in list(self._tasks):
                t.cancel()

    async def tick(self) -> list[asyncio.Task]:
        """Bir marta: eski fayllarni tozalash va yangi so'rovlarni ishga tushirish (testda ham)."""
        if self._sem is None:
            self._sem = asyncio.Semaphore(MAX_PARALLEL)
        now = time.time()
        if now - self._last_cleanup >= CLEANUP_EVERY_S:
            self.cleanup(now)
            self._last_cleanup = now
        started: list[asyncio.Task] = []
        try:
            entries = list(os.scandir(self.req_dir))
        except FileNotFoundError:
            self.prepare()
            return started
        for e in entries:
            name = e.name
            if name.endswith(".tmp") or name in self._busy:
                continue
            rid = name[:-5] if name.endswith(".json") else ""
            if not ID_RE.match(rid):
                log.warning("IPC: yaroqsiz so'rov fayli nomi rad etildi")
                with contextlib.suppress(OSError):
                    os.unlink(e.path)
                continue
            self._busy.add(name)
            task = asyncio.create_task(self._handle(Path(e.path), rid))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            started.append(task)
        return started

    def cleanup(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        removed = 0
        for d in (self.req_dir, self.res_dir):
            try:
                entries = list(os.scandir(d))
            except FileNotFoundError:
                continue
            for e in entries:
                if e.name in self._busy:
                    continue
                with contextlib.suppress(OSError):
                    if now - e.stat().st_mtime > MAX_AGE_S:
                        os.unlink(e.path)
                        removed += 1
        return removed

    # --- Bitta so'rov ---------------------------------------------------------------------------

    async def _handle(self, path: Path, rid: str) -> None:
        assert self._sem is not None
        try:
            async with self._sem:
                status, body = await self._process(path, rid)
                _write_atomic(self.res_dir / f"{rid}.json",
                              {"v": 1, "id": rid, "status": status, "body": body})
        except Exception as e:  # noqa: BLE001 - bitta so'rov xatosi siklni to'xtatmasin
            log.warning("IPC so'rovi bajarilmadi: %s", type(e).__name__)
        finally:
            self._busy.discard(path.name)

    async def _process(self, path: Path, rid: str) -> tuple[int, Any]:
        try:
            size = path.stat().st_size
            if size > MAX_REQUEST_BYTES:
                return 413, {"detail": "IPC so'rovi juda katta (1 MB dan oshmasin)"}
            raw = path.read_bytes()
        except FileNotFoundError:
            return 400, {"detail": "IPC so'rov fayli topilmadi"}
        finally:
            with contextlib.suppress(OSError):
                path.unlink()
        try:
            req = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return 400, {"detail": "IPC so'rovi JSON emas"}
        if not isinstance(req, dict) or req.get("v") != 1:
            return 400, {"detail": "IPC protokoli versiyasi mos emas (lahza.ipc/1 kutilgan)"}
        if req.get("id") != rid:
            return 400, {"detail": "IPC so'rovi id fayl nomiga mos emas"}
        method = str(req.get("method", "GET")).upper()
        target = req.get("path")
        if method not in METHODS:
            return 405, {"detail": "IPC: metodga ruxsat yo'q"}
        if not isinstance(target, str) or not target.startswith("/v1/") or "\\" in target:
            return 400, {"detail": "IPC: yo'l /v1/ bilan boshlanishi kerak"}
        headers = req.get("headers") or {}
        if not isinstance(headers, dict):
            return 400, {"detail": "IPC: headers obyekt bo'lishi kerak"}
        return await self.call(method, target, headers, req.get("body"))

    async def call(self, method: str, target: str, headers: dict, body: Any) -> tuple[int, Any]:
        """Ilovani ichki ASGI orqali chaqiradi (tarmoqsiz, lifespan ishga tushirilmaydi)."""
        import httpx

        send_headers = {}
        for k, v in headers.items():
            if isinstance(k, str) and k.lower() == "authorization" and isinstance(v, str):
                send_headers["Authorization"] = v
        content = None
        if body is not None and method != "GET":
            content = json.dumps(body, ensure_ascii=False).encode("utf-8")
            send_headers["Content-Type"] = "application/json"
        # Ilova ichidagi kutilmagan xato - 500 javob (plagin timeout kutib qolmasin).
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False,
                                        client=("127.0.0.1", 0))
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1",
                                     timeout=None) as client:
            r = await client.request(method, target, content=content, headers=send_headers)
        if not r.content:
            return r.status_code, None
        try:
            return r.status_code, r.json()
        except ValueError:
            return 502, {"detail": "javob JSON emas - bu endpoint fayl-IPC orqali ishlamaydi (HTTP kerak)"}
