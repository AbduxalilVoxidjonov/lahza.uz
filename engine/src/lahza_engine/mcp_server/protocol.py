"""MCP JSON-RPC 2.0 (stdio, qatorma-qator JSON) - bog'liqliksiz minimal server.

Qo'llanadigan metodlar: `initialize`, `notifications/initialized`, `ping`, `tools/list`,
`tools/call`. Protokol versiyalari: 2025-06-18 (asosiy) va 2025-03-26 - mijoz boshqa versiya
so'rasa, eng yangisi taklif qilinadi (mijoz rad etishi mumkin).

stdout faqat protokol xabarlari uchun: `serve_stdio` ishga tushganda `sys.stdout` stderr'ga
yo'naltiriladi, shuning uchun tasodifiy `print` ham oqimni buzmaydi.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import IO, Any

from lahza_engine.mcp_server.tools import LahzaTools

log = logging.getLogger("lahza_engine.mcp")

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26")
LATEST = SUPPORTED_VERSIONS[0]
MAX_LINE_BYTES = 4 * 1024 * 1024

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

INSTRUCTIONS = (
    "Lahza Studio montaj tool'lari. Tartib: list_projects/list_montages -> get_timeline (base_revision) -> "
    "propose_edit_plan -> foydalanuvchi bilan kelishib apply_edit_plan -> render_preview. "
    "Xato bo'lsa undo_last_edit. Eksport faqat foydalanuvchi aniq rozilik bergandan keyin confirm=true bilan. "
    "Edit flow: get_timeline -> propose_edit_plan -> apply_edit_plan; export_clip needs explicit user consent."
)


def _err(mid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _ok(mid: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


class MCPServer:
    def __init__(self, tools: LahzaTools | None = None, version: str | None = None) -> None:
        self._tools = tools
        self.protocol_version: str | None = None
        self.client_info: dict[str, Any] | None = None
        if version is None:
            from lahza_engine import __version__ as version
        self.version = version

    @property
    def tools(self) -> LahzaTools:
        if self._tools is None:
            self._tools = LahzaTools()
        return self._tools

    # ---- Xabarlar -----------------------------------------------------------------------
    def handle_line(self, line: str | bytes) -> dict[str, Any] | None:
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        if not line.strip():
            return None
        try:
            msg = json.loads(line)
        except ValueError:
            return _err(None, PARSE_ERROR, "Parse error")
        return self.handle(msg)

    def handle(self, msg: Any) -> dict[str, Any] | None:
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return _err(msg.get("id") if isinstance(msg, dict) else None, INVALID_REQUEST, "Invalid Request")
        method = msg.get("method")
        has_id = "id" in msg
        mid = msg.get("id")
        if method is None:
            # Mijozning javobi (biz so'rov yubormaymiz) - e'tiborsiz.
            if has_id and ("result" in msg or "error" in msg):
                return None
            return _err(mid, INVALID_REQUEST, "Invalid Request")
        if not isinstance(method, str) or (has_id and not isinstance(mid, (str, int))) or isinstance(mid, bool):
            return _err(mid if isinstance(mid, (str, int)) else None, INVALID_REQUEST, "Invalid Request")
        params = msg.get("params")
        if params is not None and not isinstance(params, dict):
            return None if not has_id else _err(mid, INVALID_PARAMS, "params must be an object")
        params = params or {}
        if not has_id:  # bildirishnoma - javob yo'q
            if method == "notifications/initialized":
                log.info("mijoz tayyor")
            elif method == "notifications/cancelled":
                log.info("bekor qilish so'rovi (sinxron server - e'tiborsiz)")
            return None
        try:
            if method == "initialize":
                return _ok(mid, self._initialize(params))
            if method == "ping":
                return _ok(mid, {})
            if method == "tools/list":
                return _ok(mid, {"tools": self.tools.list()})
            if method == "tools/call":
                name = params.get("name")
                args = params.get("arguments")
                if not isinstance(name, str) or name not in self.tools.tools:
                    return _err(mid, INVALID_PARAMS, f"Unknown tool: {name}")
                if args is not None and not isinstance(args, dict):
                    return _err(mid, INVALID_PARAMS, "arguments must be an object")
                return _ok(mid, self.tools.call(name, args))
            return _err(mid, METHOD_NOT_FOUND, f"Method not found: {method}")
        except Exception as e:  # noqa: BLE001 - server hech qachon yiqilmasin
            log.exception("ichki xato: %s", method)
            return _err(mid, INTERNAL_ERROR, f"Internal error: {type(e).__name__}")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        asked = params.get("protocolVersion")
        self.protocol_version = asked if asked in SUPPORTED_VERSIONS else LATEST
        info = params.get("clientInfo")
        self.client_info = info if isinstance(info, dict) else None
        log.info("initialize: mijoz %s, protokol %s (so'ralgan %s)",
                 (self.client_info or {}).get("name"), self.protocol_version, asked)
        server_info: dict[str, Any] = {"name": "lahza", "version": self.version}
        if self.protocol_version >= "2025-06-18":
            server_info["title"] = "Lahza Studio"
        return {"protocolVersion": self.protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": server_info, "instructions": INSTRUCTIONS}


def serve(server: MCPServer, stdin: IO[bytes], stdout: IO[bytes]) -> int:
    """Asosiy sikl: stdin EOF bo'lguncha. Har javob - bitta qator."""
    while True:
        line = stdin.readline(MAX_LINE_BYTES + 1)
        if not line:
            return 0
        if len(line) > MAX_LINE_BYTES and not line.endswith(b"\n"):
            while True:  # qatorning qolganini tashlab yuboramiz
                rest = stdin.readline(MAX_LINE_BYTES)
                if not rest or rest.endswith(b"\n"):
                    break
            resp: dict[str, Any] | None = _err(None, INVALID_REQUEST, "Request too large")
        else:
            resp = server.handle_line(line)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
            stdout.flush()


def serve_stdio(data_dir: str | None = None) -> int:
    from pathlib import Path

    from lahza_engine.mcp_server.engine_client import EngineClient, default_locator

    out = sys.stdout.buffer
    stdin = sys.stdin.buffer
    sys.stdout = sys.stderr  # protokoldan tashqari har qanday chiqish - stderr'ga
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s lahza-mcp %(levelname)s %(message)s")
    log.info("Lahza MCP server (stdio) ishga tushdi")
    tools = LahzaTools(EngineClient(default_locator(Path(data_dir) if data_dir else None)))
    try:
        return serve(MCPServer(tools), stdin, out)
    except KeyboardInterrupt:
        return 0
    except BrokenPipeError:
        return 0
