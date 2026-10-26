"""Servis va desktop sidecar'ining bitta engine'ni bo'lishishi (ADB-7).

**Ikki nusxaning oldini olish.** Bitta `data_dir` (library.db, Models, ipc/) bilan ikki engine
ishlamasligi kerak:

* `serve --service` - tirik va javob beruvchi engine (`engine.json` -> pid tirik + `/v1/health` 200)
  topilsa, ikkinchisini ko'tarmaydi va 0 kod bilan chiqadi (launchd/Task Scheduler qayta ishga tushirmaydi).
* Desktop sidecar'i (`serve --port 0`, `LAHZA_TOKEN` bilan) - tirik discovery engine'ini topsa,
  o'z engine'ini ko'tarmaydi: "ulanish" (attach) rejimi. Tauri o'z tokenini yaratadi va uni
  o'zgartira olmaydi, shuning uchun sidecar shu tokenni servisga **taxallus** (alias) sifatida
  ro'yxatdan o'tkazadi: `<data_dir>/engine.clients/<pid>.json` (papka 0700, fayl 0600,
  `{"pid", "token"}`). Discovery engine'i `TokenAliasMiddleware` orqali tirik pid'li taxallus
  tokenini asosiy tokenga almashtiradi - auth kodi (`api/app.py`) o'zgarmaydi. So'ng sidecar
  `LAHZA_READY port=<servis porti>` yozadi va ota jarayon (Tauri) yoki servis o'lguncha kutadi;
  chiqishda taxallusni o'chiradi. Servis o'lsa sidecar 3 kod bilan chiqadi - Tauri uni qayta
  ishga tushiradi va endi o'z engine'i ko'tariladi.

  Xavfsizlik: taxallus yozish uchun `data_dir` ga yozish huquqi kerak - bu `engine.json` ni
  o'qish huquqi bilan bir xil chegara (o'sha foydalanuvchi). Token hech qachon logga yozilmaydi.

**Qulash cheklovi.** `<data_dir>/service/starts.json` - oxirgi ishga tushish vaqtlari. `WINDOW_S`
ichida `MAX_STARTS` dan ko'p start bo'lsa, servis xato logini yozib 0 kod bilan chiqadi (launchd
`KeepAlive.SuccessfulExit=false` / Task Scheduler `RestartOnFailure` uni boshqa ko'tarmaydi) - keyingi
kirishda yoki `lahza install-service` / `launchctl kickstart` dan keyin yana urinadi.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode

from lahza_engine.core.discovery import discovery_path, pid_alive, read_discovery
from lahza_engine.service import SERVICE_DIR

log = logging.getLogger(__name__)

ALIAS_DIR = "engine.clients"
STARTS_FILE = "starts.json"
MAX_STARTS = 5
WINDOW_S = 300.0
ATTACH_EXIT_SERVICE_GONE = 3

HealthFn = Callable[[int, str], bool]


# ---- Tirik engine'ni topish ------------------------------------------------------------------

def http_health(port: int, token: str, timeout: float = 1.5) -> bool:
    req = urllib.request.Request(f"http://127.0.0.1:{int(port)}/v1/health",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - faqat 127.0.0.1
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def find_live_engine(data_dir: Path, health: HealthFn | None = None, attempts: int = 3,
                     delay_s: float = 0.5) -> dict[str, Any] | None:
    """`engine.json` dagi engine tirik va token bilan javob bersa - uning ma'lumoti, aks holda None.
    Engine endigina ishga tushayotgan bo'lishi mumkin - health bir necha marta so'raladi."""
    health = health or http_health
    data = read_discovery(discovery_path(data_dir))
    if not data:
        return None
    port, token, pid = data.get("port"), data.get("token"), data.get("pid")
    if not (isinstance(port, int) and isinstance(token, str) and token and isinstance(pid, int)):
        return None
    if pid == os.getpid() or not pid_alive(pid):
        return None
    for i in range(max(1, attempts)):
        if health(port, token):
            return data
        if i + 1 < attempts:
            time.sleep(delay_s)
    return None


# ---- Token taxalluslari ----------------------------------------------------------------------

def alias_dir(data_dir: Path) -> Path:
    return Path(data_dir) / ALIAS_DIR


def register_alias(data_dir: Path, token: str, pid: int | None = None) -> Path:
    d = alias_dir(data_dir)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sys.platform != "win32":
        os.chmod(d, 0o700)
    pid = os.getpid() if pid is None else pid
    path = d / f"{pid}.json"
    tmp = d / f".{pid}.json.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pid": pid, "token": token}, f)
    os.replace(tmp, path)
    return path


def remove_alias(path: Path) -> None:
    with contextlib.suppress(OSError):
        Path(path).unlink()


def live_aliases(data_dir: Path, prune: bool = True) -> list[str]:
    """Tirik pid'li taxallus tokenlari; o'lik pid fayllari (SIGKILL'dan qolgan) o'chiriladi."""
    d = alias_dir(data_dir)
    out: list[str] = []
    try:
        files = list(d.glob("*.json"))
    except OSError:
        return out
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid, tok = data.get("pid"), data.get("token")
        if not (isinstance(pid, int) and isinstance(tok, str) and tok):
            continue
        if pid_alive(pid):
            out.append(tok)
        elif prune:
            remove_alias(p)
    return out


class TokenAliasMiddleware:
    """ASGI: taxallus tokenini (sarlavha yoki `?t=`) asosiy tokenga almashtiradi. Boshqa barcha
    so'rovlar o'zgarmasdan o'tadi; noto'g'ri token baribir 401 oladi (auth `api/app.py` da)."""

    def __init__(self, app, data_dir: Path, token: str, ttl_s: float = 1.0) -> None:
        self.app = app
        self.data_dir = Path(data_dir)
        self.token = token
        self.ttl_s = ttl_s
        self._cache: tuple[float, list[str]] = (0.0, [])

    def _aliases(self) -> list[str]:
        now = time.monotonic()
        if now - self._cache[0] > self.ttl_s:
            self._cache = (now, live_aliases(self.data_dir))
        return self._cache[1]

    def _is_alias(self, given: str) -> bool:
        if not given or secrets.compare_digest(given, self.token):
            return False
        return any(secrets.compare_digest(given, a) for a in self._aliases())

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") in ("http", "websocket"):
            scope = self._rewrite(scope)
        await self.app(scope, receive, send)

    def _rewrite(self, scope: dict[str, Any]) -> dict[str, Any]:
        headers = list(scope.get("headers") or [])
        changed = False
        for i, (k, v) in enumerate(headers):
            if k.lower() == b"authorization":
                val = v.decode("latin-1")
                if val.startswith("Bearer ") and self._is_alias(val[7:].strip()):
                    headers[i] = (k, f"Bearer {self.token}".encode("latin-1"))
                    changed = True
        qs = scope.get("query_string") or b""
        new_qs = qs
        if b"t=" in qs:
            pairs = parse_qsl(qs.decode("latin-1"), keep_blank_values=True)
            if any(k == "t" and self._is_alias(v) for k, v in pairs):
                pairs = [(k, self.token if k == "t" and self._is_alias(v) else v) for k, v in pairs]
                new_qs = urlencode(pairs).encode("latin-1")
                changed = True
        if not changed:
            return scope
        return {**scope, "headers": headers, "query_string": new_qs}


# ---- Attach rejimi (desktop sidecar) --------------------------------------------------------

def attach_allowed(environ: dict[str, str] | None = None) -> bool:
    """Ulanish o'chirilgan holatlar: `LAHZA_ATTACH=0`; dev desktop (`LAHZA_CORS_ORIGINS` - Vite
    origin'i servisning CORS ro'yxatida yo'q, webview so'rovlari bloklanardi)."""
    env = os.environ if environ is None else environ
    if env.get("LAHZA_ATTACH", "1").strip().lower() in ("0", "false", "no"):
        return False
    return not env.get("LAHZA_CORS_ORIGINS", "").strip()


class AttachWaiter:
    """`cmd_serve` watchdog'i `server.should_exit = True` qiladi - shu obyekt server o'rnida turadi."""

    should_exit = False


def run_attached(data_dir: Path, live: dict[str, Any], token: str, waiter: AttachWaiter,
                 health: HealthFn | None = None, poll_s: float = 1.0,
                 emit: Callable[[str], None] | None = None) -> int | None:
    """Mavjud engine'ga ulanish. Qaytaradi: chiqish kodi; None - ulanib bo'lmadi (taxallus ishlamadi,
    masalan eski engine) - chaqiruvchi o'z engine'ini ko'taradi."""
    import signal

    health = health or http_health
    alias = register_alias(data_dir, token)
    try:
        if not health(live["port"], token):
            log.warning("mavjud engine (pid %s) taxallus tokenini qabul qilmadi - o'z engine'imiz",
                        live["pid"])
            return None

        def on_signal(_signum, _frame) -> None:
            waiter.should_exit = True

        for name in ("SIGTERM", "SIGINT", "SIGHUP"):
            sig = getattr(signal, name, None)
            if sig is not None:
                with contextlib.suppress(ValueError, OSError):  # asosiy oqim emas
                    signal.signal(sig, on_signal)
        log.info("mavjud engine'ga ulanildi (pid %s, port %s) - ikkinchi engine ishga tushmaydi",
                 live["pid"], live["port"])
        (emit or (lambda s: print(s, flush=True)))(f"LAHZA_READY port={live['port']}")
        while not waiter.should_exit:
            if not pid_alive(live["pid"]):
                log.warning("ulangan engine (pid %s) to'xtadi", live["pid"])
                return ATTACH_EXIT_SERVICE_GONE
            time.sleep(poll_s)
        return 0
    finally:
        remove_alias(alias)


# ---- Servis rejimi: qulash cheklovi va env fayli --------------------------------------------

def record_start(data_dir: Path, now: float | None = None, max_starts: int = MAX_STARTS,
                 window_s: float = WINDOW_S) -> bool:
    """Startni jurnalga yozadi. Qaytaradi: davom etish mumkinmi (oyna ichida <= max_starts)."""
    now = time.time() if now is None else now
    path = Path(data_dir) / SERVICE_DIR / STARTS_FILE
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        starts = [float(t) for t in old if isinstance(t, (int, float))] if isinstance(old, list) else []
    except (OSError, ValueError):
        starts = []
    starts = [t for t in starts if now - t < window_s] + [now]
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(starts[-(max_starts + 1):]), encoding="utf-8")
    return len(starts) <= max_starts


def load_env_file(path: Path, environ: dict[str, str] | None = None) -> list[str]:
    """Windows vazifasi uchun muhit (Task Scheduler `Exec` env bera olmaydi). Faqat ruxsat etilgan
    kalitlar; mavjud qiymat ustiga yozilmaydi. Qaytaradi: o'rnatilgan kalitlar."""
    from lahza_engine.service.spec import PASS_ENV

    env = os.environ if environ is None else environ
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    done = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in PASS_ENV and isinstance(v, str) and v and not env.get(k):
                env[k] = v
                done.append(k)
    return done
