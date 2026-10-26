"""Ishlayotgan Lahza engine'ga ulanish (discovery `engine.json` + token, faqat 127.0.0.1).

MCP server engine ichida ishlamaydi: har chaqiruvda tirik engine `find_live_engine` orqali topiladi
(natija keshlanadi; ulanish uzilsa yoki token rad etilsa - qayta qidiriladi).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

log = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 16 * 1024 * 1024  # timeline JSON katta bo'lishi mumkin; undan kattasi rad etiladi
DEFAULT_TIMEOUT_S = 30.0

NOT_RUNNING_MSG = ("Lahza engine topilmadi (ishlamayapti). Lahza Studio'ni oching yoki "
                   "`lahza-engine install-service` qiling. / Lahza engine is not running: open Lahza Studio "
                   "or run `lahza-engine install-service`.")


class EngineNotRunning(RuntimeError):
    def __init__(self, msg: str = NOT_RUNNING_MSG) -> None:
        super().__init__(msg)


class EngineHTTPError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def seg(value: str) -> str:
    """URL yo'l bo'lagi (id'lar) - `/`, `..`, `?` va boshqalar kodlanadi."""
    return quote(str(value), safe="")


def _detail(raw: bytes) -> str:
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return raw.decode("utf-8", "replace")[:500] or "javob yo'q"
    d = data.get("detail", data) if isinstance(data, dict) else data
    if isinstance(d, dict) and "message" in d:
        d = d["message"]
    if isinstance(d, list):  # FastAPI validatsiya xatolari
        d = "; ".join(f"{'.'.join(str(x) for x in e.get('loc', []))}: {e.get('msg')}"
                      if isinstance(e, dict) else str(e) for e in d[:10])
    return str(d)[:1000]


Locator = Callable[[], dict[str, Any] | None]


def default_locator(data_dir: Path | None = None) -> Locator:
    def locate() -> dict[str, Any] | None:
        from lahza_engine.config import default_data_dir
        from lahza_engine.service.runtime import find_live_engine

        return find_live_engine(Path(data_dir) if data_dir else default_data_dir(), attempts=1)

    return locate


class EngineClient:
    def __init__(self, locator: Locator | None = None, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._locate = locator or default_locator()
        self._info: dict[str, Any] | None = None
        self.timeout_s = timeout_s

    def info(self, refresh: bool = False) -> dict[str, Any]:
        if refresh or self._info is None:
            self._info = None
            found = self._locate()
            if not found:
                raise EngineNotRunning()
            self._info = found
        return self._info

    def request(self, method: str, path: str, body: Any = None, timeout_s: float | None = None
                ) -> tuple[bytes, str]:
        """Qaytaradi: (javob baytlari, content-type). Ulanish uzilsa bir marta qayta topadi."""
        for attempt in (0, 1):
            info = self.info(refresh=attempt == 1)
            port, token = int(info["port"]), str(info["token"])
            data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Content-Type": "application/json"})
            # Tizim proksisi lokal so'rovni hech qachon olmasin.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(req, timeout=timeout_s or self.timeout_s) as r:
                    raw = r.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise EngineHTTPError(r.status, "javob juda katta / response too large")
                    return raw, r.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                raw = e.read(64 * 1024) if e.fp else b""
                if e.code == 401 and attempt == 0:
                    continue  # engine qayta ishga tushgan (yangi token) - qayta topamiz
                raise EngineHTTPError(e.code, _detail(raw)) from None
            except (urllib.error.URLError, OSError) as e:
                reason = getattr(e, "reason", e)
                if isinstance(reason, TimeoutError) or "timed out" in str(reason):
                    # So'rov engine'ga yetgan bo'lishi mumkin - takrorlamaymiz (ikki marta eksport bo'lmasin).
                    raise RuntimeError("engine javob bermadi (timeout) / engine timed out") from None
                if attempt == 0 and isinstance(reason, ConnectionRefusedError):
                    continue  # engine boshqa portda qayta ishga tushgan bo'lishi mumkin
                raise EngineNotRunning() from None
        raise EngineNotRunning()  # pragma: no cover

    def json(self, method: str, path: str, body: Any = None, timeout_s: float | None = None) -> Any:
        raw, _ = self.request(method, path, body, timeout_s)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as e:
            raise RuntimeError("engine JSON bo'lmagan javob qaytardi") from e

    def get(self, path: str) -> Any:
        return self.json("GET", path)

    def post(self, path: str, body: Any = None, timeout_s: float | None = None) -> Any:
        return self.json("POST", path, body if body is not None else {}, timeout_s)

    def put(self, path: str, body: Any) -> Any:
        return self.json("PUT", path, body)
