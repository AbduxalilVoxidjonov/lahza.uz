"""`lahza mcp` - stdio MCP server: protokol, tool'lar (soxta va jonli HTTP engine), xavfsizlik."""

from __future__ import annotations

import base64
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from lahza_engine.editing_agent.executor import revision
from lahza_engine.mcp_server import LahzaTools, MCPServer, serve
from lahza_engine.mcp_server.engine_client import EngineClient, EngineHTTPError, EngineNotRunning
from lahza_engine.mcp_server.schema import validate
from lahza_engine.montage.model import MediaRef, MontageTimeline, VideoItem

SRC = Path(__file__).resolve().parents[1] / "src"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def rpc(server: MCPServer, method: str, params: dict | None = None, mid: int = 1) -> dict:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    return server.handle_line(json.dumps(msg))


def call(server: MCPServer, name: str, args: dict | None = None) -> tuple[Any, bool]:
    res = rpc(server, "tools/call", {"name": name, "arguments": args or {}})["result"]
    text = res["content"][0]["text"]
    try:
        return json.loads(text), res["isError"]
    except ValueError:
        return text, res["isError"]


def make_timeline() -> MontageTimeline:
    return MontageTimeline(media={"m": MediaRef(id="m", path="/private/source.mp4", duration_ms=10000,
                                                width=1920, height=1080, fps=30)},
                           video=[VideoItem(id="v", media="m", src_in_ms=0, src_out_ms=10000)])


# ---- Soxta engine (HTTP'siz) ------------------------------------------------------------------

class FakeClient:
    """`EngineClient` o'rnini bosuvchi: marshrut -> javob. Chaqiruvlar yoziladi."""

    def __init__(self, routes: dict[tuple[str, str], Any] | None = None, running: bool = True) -> None:
        self.routes = routes or {}
        self.running = running
        self.calls: list[tuple[str, str, Any]] = []

    def info(self, refresh: bool = False) -> dict[str, Any]:
        if not self.running:
            raise EngineNotRunning()
        return {"port": 47600, "pid": 1, "token": "secret-token"}

    def request(self, method: str, path: str, body: Any = None, timeout_s: float | None = None):
        self.info()
        self.calls.append((method, path, body))
        out = self.routes.get((method, path))
        if out is None:
            raise EngineHTTPError(404, "topilmadi")
        if callable(out):
            out = out(body)
        if isinstance(out, Exception):
            raise out
        if isinstance(out, bytes):
            return out, "image/jpeg"
        return json.dumps(out).encode(), "application/json"

    def json(self, method, path, body=None, timeout_s=None):
        return json.loads(self.request(method, path, body, timeout_s)[0])

    def get(self, path):
        return self.json("GET", path)

    def post(self, path, body=None, timeout_s=None):
        return self.json("POST", path, body if body is not None else {}, timeout_s)

    def put(self, path, body):
        return self.json("PUT", path, body)


def fake_server(routes=None, running=True) -> tuple[MCPServer, FakeClient]:
    client = FakeClient(routes, running)
    return MCPServer(LahzaTools(client), version="test"), client  # type: ignore[arg-type]


# ---- Protokol ---------------------------------------------------------------------------------

@pytest.mark.parametrize(("asked", "got"), [("2025-06-18", "2025-06-18"), ("2025-03-26", "2025-03-26"),
                                             ("2099-01-01", "2025-06-18"), (None, "2025-06-18")])
def test_initialize_negotiates_version(asked, got):
    s, _ = fake_server()
    r = rpc(s, "initialize", {"protocolVersion": asked, "capabilities": {},
                              "clientInfo": {"name": "claude-code", "version": "1"}})
    assert r["id"] == 1 and r["result"]["protocolVersion"] == got
    assert r["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert r["result"]["serverInfo"]["name"] == "lahza"
    assert s.client_info == {"name": "claude-code", "version": "1"}


def test_notifications_and_ping():
    s, _ = fake_server()
    assert s.handle_line('{"jsonrpc":"2.0","method":"notifications/initialized"}') is None
    assert s.handle_line('{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":1}}') is None
    assert rpc(s, "ping", mid="p1") == {"jsonrpc": "2.0", "id": "p1", "result": {}}
    assert s.handle_line("   \n") is None
    assert s.handle_line('{"jsonrpc":"2.0","id":5,"result":{}}') is None  # mijoz javobi


def test_errors():
    s, _ = fake_server()
    assert rpc(s, "resources/read")["error"]["code"] == -32601
    assert s.handle_line("{buzuq json")["error"] == {"code": -32700, "message": "Parse error"}
    assert s.handle_line("{buzuq json")["id"] is None
    assert s.handle_line('[{"jsonrpc":"2.0","id":1,"method":"ping"}]')["error"]["code"] == -32600
    assert s.handle_line('{"id":1,"method":"ping"}')["error"]["code"] == -32600
    assert s.handle_line('{"jsonrpc":"2.0","id":1,"method":"ping","params":[1]}')["error"]["code"] == -32602
    assert rpc(s, "tools/call", {"name": "rm_rf", "arguments": {}})["error"]["code"] == -32602
    r = rpc(s, "tools/call", {"name": "list_episodes", "arguments": {"project_id": 5, "x": 1}})["result"]
    assert r["isError"] and "noma'lum maydon" in r["content"][0]["text"]


def test_tools_list_schemas_and_annotations():
    s, _ = fake_server()
    tools = {t["name"]: t for t in rpc(s, "tools/list")["result"]["tools"]}
    assert {"lahza_status", "list_projects", "list_episodes", "list_clips", "get_transcript", "get_timeline",
            "propose_edit_plan", "apply_edit_plan", "undo_last_edit", "render_preview",
            "export_clip"} <= set(tools)
    for t in tools.values():
        assert t["inputSchema"]["type"] == "object" and t["inputSchema"]["additionalProperties"] is False
        assert " / " in t["description"]  # o'zbekcha + inglizcha
        # Hech bir tool ixtiyoriy fayl yo'lini qabul qilmaydi.
        assert not {"path", "out_dir", "out", "file", "filename"} & set(t["inputSchema"]["properties"])
    for name in ("lahza_status", "list_projects", "list_clips", "get_transcript", "get_timeline",
                 "propose_edit_plan"):
        assert tools[name]["annotations"]["readOnlyHint"] is True
    assert tools["export_clip"]["annotations"]["destructiveHint"] is True
    assert tools["export_clip"]["inputSchema"]["required"] == ["confirm"]
    assert tools["apply_edit_plan"]["annotations"]["readOnlyHint"] is False


def test_schema_validator():
    sch = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 3},
                                            "s": {"type": "string", "enum": ["a"]}},
           "required": ["n"], "additionalProperties": False}
    assert validate({"n": 2, "s": "a"}, sch) == []
    assert validate({"n": True}, sch)  # bool integer emas
    assert len(validate({"n": 9, "s": "b", "z": 1}, sch)) == 3
    assert validate({}, sch) == ["arguments.n: majburiy maydon"]


# ---- Tool'lar (soxta engine) ------------------------------------------------------------------

def test_engine_not_running_message():
    s, _ = fake_server(running=False)
    for name, args in (("lahza_status", {}), ("list_projects", {}), ("get_timeline", {"montage_id": "m"})):
        text, err = call(s, name, args)
        assert err and "Lahza Studio'ni oching" in text and "lahza-engine install-service" in text


def test_read_tools_are_bounded():
    clips = [{"id": f"c{i}", "start_ms": i, "end_ms": i + 1, "title": "t", "score": 0.5, "status": "nomzod",
              "reason": "x" * 1000, "cuts": [[1, 2]], "hook": None, "scores": {"a": 1}} for i in range(250)]
    sentences = [{"id": i, "start_ms": i * 1000, "end_ms": i * 1000 + 900, "speaker": "S", "text": "so'z " * 100,
                  "words": [{"text": "so'z"}] * 100} for i in range(300)]
    s, _ = fake_server({
        ("GET", "/v1/health"): {"version": "9.9", "ok": True},
        ("GET", "/v1/projects"): [{"id": "p1", "name": "Shou", "created_at": "x", "extra": 1}],
        ("GET", "/v1/projects/p1/episodes"): [{"id": "e1", "title": "E", "status": "ready",
                                               "project_dir": "/secret"}],
        ("GET", "/v1/montages"): [{"id": "m1", "name": "M", "status": "ready", "duration_ms": 1}],
        ("GET", "/v1/episodes/e1/clips"): clips,
        ("GET", "/v1/episodes/e1/transcript"): {"sentences": sentences},
    })
    st, err = call(s, "lahza_status")
    assert not err and st["connected"] and st["engine_version"] == "9.9" and "token" not in json.dumps(st)
    assert call(s, "list_projects")[0] == {"projects": [{"id": "p1", "name": "Shou", "created_at": "x"}],
                                           "total": 1}
    eps = call(s, "list_episodes", {"project_id": "p1"})[0]["episodes"]
    assert eps == [{"id": "e1", "title": "E", "status": "ready"}]
    assert call(s, "list_montages")[0]["montages"][0]["id"] == "m1"
    out = call(s, "list_clips", {"episode_id": "e1"})[0]
    assert out["total"] == 250 and len(out["clips"]) == 50 and len(out["clips"][0]["reason"]) <= 201
    assert out["next_offset"] == 50 and "scores" not in out["clips"][0]
    last = call(s, "list_clips", {"episode_id": "e1", "offset": 200, "limit": 100})[0]
    assert len(last["clips"]) == 50 and last["next_offset"] is None
    tr = call(s, "get_transcript", {"episode_id": "e1", "limit": 200, "max_chars": 5000})[0]
    assert tr["total"] == 300 and 0 < len(tr["sentences"]) < 20 and "words" not in tr["sentences"][0]
    assert tr["next_offset"] == len(tr["sentences"])
    page2 = call(s, "get_transcript", {"episode_id": "e1", "offset": tr["next_offset"], "limit": 2})[0]
    assert [x["id"] for x in page2["sentences"]] == [tr["next_offset"], tr["next_offset"] + 1]
    win = call(s, "get_transcript", {"episode_id": "e1", "start_ms": 5000, "end_ms": 7000})[0]
    assert [x["id"] for x in win["sentences"]] == [5, 6]


def test_ids_are_url_encoded():
    s, c = fake_server()
    call(s, "list_episodes", {"project_id": "../../v1/license"})
    assert c.calls[-1][1] == "/v1/projects/..%2F..%2Fv1%2Flicense/episodes"


def _montage_routes(tl: MontageTimeline, store: dict) -> dict:
    from lahza_engine.editing_agent.executor import preview
    from lahza_engine.editing_agent.model import EditPlan

    store["tl"] = tl.to_json()

    def get(_):
        return {"id": "m1", "name": "M", "status": "ready", "timeline": store["tl"]}

    def prev(body):
        t = MontageTimeline.model_validate(body["timeline"])
        try:
            out = preview(t, EditPlan.model_validate(body["plan"]), body["selected_video_id"])
        except ValueError as e:
            return EngineHTTPError(409 if "changed" in str(e) else 422, str(e))
        return out.model_dump(mode="json", by_alias=True)

    def put(body):
        store["tl"] = MontageTimeline.model_validate(body).to_json()
        return {"ok": True, "timeline": store["tl"]}

    return {("GET", "/v1/montages/m1"): get, ("POST", "/v1/editing-agent:preview"): prev,
            ("PUT", "/v1/montages/m1/timeline"): put}


def test_edit_flow_with_fake_engine():
    store: dict = {}
    s, c = fake_server(_montage_routes(make_timeline(), store))
    tl, err = call(s, "get_timeline", {"montage_id": "m1"})
    assert not err and tl["base_revision"] == revision(make_timeline(), None)
    assert tl["timeline"]["clips"][0]["id"] == "v" and "/private/source.mp4" not in json.dumps(tl)
    plan = {"base_revision": tl["base_revision"],
            "commands": [{"tool": "set_color", "args": {"preset": "warm"}}]}
    # Noto'g'ri reja - xatolar ro'yxati, qo'llanmaydi.
    bad, err = call(s, "propose_edit_plan", {"montage_id": "m1", "plan": {**plan, "commands": [
        {"tool": "delete", "args": {}}]}})
    assert not err and bad["valid"] is False and bad["errors"]
    ok, err = call(s, "propose_edit_plan", {"montage_id": "m1", "plan": plan})
    assert ok["valid"] and ok["changes"] == ["Set color to warm"] and ok["applied"] is False
    assert not any(m == "PUT" for m, _, _ in c.calls)
    # Qo'llash -> saqlanadi; eski revision bilan qayta qo'llash -> 409.
    res, err = call(s, "apply_edit_plan", {"montage_id": "m1", "plan": plan})
    assert not err and res["applied"] and store["tl"]["color"]["plugin"] == "uz.lahza.color.warm"
    stale, err = call(s, "apply_edit_plan", {"montage_id": "m1", "plan": plan})
    assert err and "409" in stale
    assert call(s, "propose_edit_plan", {"montage_id": "m1", "plan": plan})[0]["valid"] is False
    # Undo -> asl timeline.
    un, err = call(s, "undo_last_edit", {})
    assert not err and un["undone"] and store["tl"] == make_timeline().to_json()
    assert call(s, "undo_last_edit", {})[1] is True


def test_apply_requires_base_revision_and_undo_refuses_foreign_change():
    store: dict = {}
    s, _ = fake_server(_montage_routes(make_timeline(), store))
    text, err = call(s, "apply_edit_plan", {"montage_id": "m1", "plan": {"commands": []}})
    assert err and "base_revision" in text
    rev = call(s, "get_timeline", {"montage_id": "m1"})[0]["base_revision"]
    plan = {"base_revision": rev, "commands": [{"tool": "set_captions", "args": {"enabled": False,
                                                                                    "font_size": None}}]}
    assert call(s, "apply_edit_plan", {"montage_id": "m1", "plan": plan})[1] is False
    store["tl"]["captions"]["enabled"] = True  # foydalanuvchi UI'da o'zgartirdi
    text, err = call(s, "undo_last_edit", {"montage_id": "m1"})
    assert err and "409" in text and store["tl"]["captions"]["enabled"] is True


def test_render_preview_returns_image_and_controlled_path(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    s, c = fake_server({("POST", "/v1/montages/m1:preview"): JPEG,
                        ("POST", "/v1/episodes/e1/clips/c1:preview"): JPEG})
    res = rpc(s, "tools/call", {"name": "render_preview", "arguments": {"montage_id": "m1", "t_ms": 1500}})
    content = res["result"]["content"]
    meta = json.loads(content[0]["text"])
    assert Path(meta["preview_path"]).read_bytes() == JPEG
    assert Path(meta["preview_path"]).parent == tmp_path / "lahza-mcp" / "previews"
    assert content[1] == {"type": "image", "data": base64.b64encode(JPEG).decode(), "mimeType": "image/jpeg"}
    assert c.calls[-1][2] == {"t_ms": 1500}
    res = rpc(s, "tools/call", {"name": "render_preview", "arguments": {"episode_id": "e1", "clip_id": "c1",
                                                                        "include_image": False}})
    assert len(res["result"]["content"]) == 1
    assert call(s, "render_preview", {})[1] is True


def test_export_requires_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("LAHZA_MCP_EXPORT_DIR", str(tmp_path / "out"))
    job = {"id": "j1", "kind": "export", "status": "queued", "progress": 0, "meta": {"x": 1}}
    s, c = fake_server({("POST", "/v1/episodes/e1/clips/c1:export"): job,
                        ("POST", "/v1/montages/m1:render"): job,
                        ("GET", "/v1/jobs/j1"): {**job, "status": "done", "result": {"video": "/o.mp4",
                                                                                       "big": [1, 2]}}})
    for args in ({"episode_id": "e1", "clip_id": "c1", "confirm": False},):
        text, err = call(s, "export_clip", args)
        assert err and "confirm" in text
    text, err = call(s, "export_clip", {"episode_id": "e1", "clip_id": "c1"})
    assert err and "confirm" in text
    assert c.calls == []  # engine'ga umuman murojaat yo'q
    # out_dir Claude'dan olinmaydi (sxema rad etadi).
    assert call(s, "export_clip", {"montage_id": "m1", "confirm": True, "out_dir": "/etc"})[1] is True
    out, err = call(s, "export_clip", {"episode_id": "e1", "clip_id": "c1", "confirm": True,
                                       "platform": "youtube_shorts"})
    assert not err and out["job"]["id"] == "j1"
    assert c.calls[-1][2] == {"out_dir": str(tmp_path / "out"), "platform": "youtube_shorts"}
    assert call(s, "export_clip", {"montage_id": "m1", "confirm": True})[1] is False
    assert c.calls[-1][2] == {"out_dir": str(tmp_path / "out")}
    js = call(s, "job_status", {"job_id": "j1"})[0]
    assert js["status"] == "done" and js["result"] == {"video": "/o.mp4"}


def test_tool_exception_does_not_kill_server():
    s, _ = fake_server({("GET", "/v1/projects"): lambda _: ZeroDivisionError("x")})
    s.tools.tools["list_projects"].handler = lambda a: 1 / 0
    text, err = call(s, "list_projects")
    assert err and "ZeroDivisionError" in text
    assert rpc(s, "ping")["result"] == {}


def test_long_output_truncated():
    s, _ = fake_server({("GET", "/v1/projects"): [{"id": str(i), "name": "x" * 1000} for i in range(150)]})
    text, err = call(s, "list_projects")
    assert not err and isinstance(text, str) and text.endswith("truncated]") and len(text) < 61_000


def test_serve_loop_only_protocol_on_stdout(capsys):
    s, _ = fake_server(running=False)
    lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2025-03-26"}}),
             json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
             "not json",
             json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                         "params": {"name": "lahza_status", "arguments": {}}})]
    out = io.BytesIO()
    assert serve(s, io.BytesIO(("\n".join(lines) + "\n").encode()), out) == 0
    resp = [json.loads(x) for x in out.getvalue().decode().splitlines()]
    assert [r.get("id") for r in resp] == [1, None, 2]
    assert resp[1]["error"]["code"] == -32700


def test_cli_subprocess_stdout_is_pure_protocol(tmp_path):
    """`lahza mcp` jarayon sifatida: stdout'dagi har qator JSON-RPC, loglar - stderr'da."""
    env = {**os.environ, "PYTHONPATH": str(SRC), "LAHZA_DATA_DIR": str(tmp_path / "data")}
    inp = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "t", "version": "0"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "list_projects", "arguments": {}}}),
        json.dumps({"jsonrpc": "2.0", "id": 4, "method": "nope"}),
    ]) + "\n"
    p = subprocess.run([sys.executable, "-m", "lahza_engine", "mcp"], input=inp.encode(), env=env,
                       capture_output=True, timeout=60)
    assert p.returncode == 0
    resp = [json.loads(x) for x in p.stdout.decode().splitlines()]
    assert [r["id"] for r in resp] == [1, 2, 3, 4]
    assert all(r["jsonrpc"] == "2.0" for r in resp)
    assert resp[2]["result"]["isError"] and "Lahza Studio'ni oching" in resp[2]["result"]["content"][0]["text"]
    assert resp[3]["error"]["code"] == -32601
    assert b"lahza-mcp" in p.stderr  # loglar stderr'da


# ---- Jonli integratsiya: haqiqiy engine (uvicorn) + discovery fayli ---------------------------

def _free_port() -> int:
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


@pytest.fixture
def live_engine(tmp_path, monkeypatch):
    import uvicorn

    from lahza_engine.api.app import create_app
    from lahza_engine.config import Settings
    from lahza_engine.core import discovery as d
    from lahza_engine.core.services import Services

    monkeypatch.setenv("LAHZA_DEV", "1")
    data = tmp_path / "data"
    token = "live-token"
    app = create_app(Settings(data_dir=data), token=token)
    st = app.state.lahza
    st._services = Services()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error",
                                           lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started
    # find_live_engine o'z pid'imizni rad etadi - discovery'da tirik bola jarayon pid'i.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    d.write_discovery(d.discovery_path(data), port, token, "live", pid=child.pid)
    yield {"st": st, "data": data, "port": port, "token": token}
    child.kill()
    child.wait()
    server.should_exit = True
    th.join(timeout=5)


def test_live_engine_integration(live_engine, tmp_path, monkeypatch):
    from lahza_engine.mcp_server.engine_client import default_locator

    st = live_engine["st"]
    st.lib_write("INSERT INTO shows(id, name) VALUES ('p1', 'Shou')")
    tl = make_timeline()
    st.lib_write("INSERT INTO montages(id, project_id, name, template_id, sources_json, timeline_json,"
                 " duration_ms, status) VALUES ('m1','p1','Montaj','t','[]',?,?, 'ready')",
                 (json.dumps(tl.to_json()), tl.duration_ms))

    def fake_frame(timeline, t_ms, out, settings, detector=None):
        Path(out).write_bytes(JPEG)
        return out

    monkeypatch.setattr("lahza_engine.render.montage_render.render_montage_frame", fake_frame)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    s = MCPServer(LahzaTools(EngineClient(default_locator(live_engine["data"]))), version="t")

    status, err = call(s, "lahza_status")
    assert not err and status["port"] == live_engine["port"] and live_engine["token"] not in json.dumps(status)
    assert call(s, "list_projects")[0]["projects"][0]["id"] == "p1"
    assert call(s, "list_montages", {"project_id": "p1"})[0]["montages"][0]["id"] == "m1"
    timeline, err = call(s, "get_timeline", {"montage_id": "m1", "selected_video_id": "v"})
    assert not err
    plan = {"base_revision": timeline["base_revision"], "commands": [
        {"tool": "freeze_clip", "args": {"clip_id": "v", "at_ms": 1000, "duration_ms": 500}},
        {"tool": "set_color", "args": {"preset": "cool"}}]}
    args = {"montage_id": "m1", "plan": plan, "selected_video_id": "v"}
    prop, err = call(s, "propose_edit_plan", args)
    assert not err and prop["valid"], prop
    applied, err = call(s, "apply_edit_plan", args)
    assert not err and applied["applied"], applied
    saved = MontageTimeline.model_validate(json.loads(
        st.lib("SELECT timeline_json FROM montages WHERE id='m1'")[0]["timeline_json"]))
    assert saved.color.plugin == "uz.lahza.color.cool" and saved.video[0].fx[0].at_ms == 1000
    text, err = call(s, "apply_edit_plan", args)  # endi eskirgan
    assert err and "409" in text
    bad, err = call(s, "propose_edit_plan", {"montage_id": "m1", "selected_video_id": "v", "plan": {
        "base_revision": applied["base_revision"],
        "commands": [{"tool": "freeze_clip", "args": {"clip_id": "v", "at_ms": 9900, "duration_ms": 500}}]}})
    assert not err and bad["valid"] is False and bad["errors"]
    res = rpc(s, "tools/call", {"name": "render_preview", "arguments": {"montage_id": "m1", "t_ms": 100}})
    assert res["result"]["content"][1]["mimeType"] == "image/jpeg"
    un, err = call(s, "undo_last_edit", {"montage_id": "m1"})
    assert not err and un["undone"]
    restored = json.loads(st.lib("SELECT timeline_json FROM montages WHERE id='m1'")[0]["timeline_json"])
    assert MontageTimeline.model_validate(restored).to_json() == tl.to_json()
    text, err = call(s, "get_timeline", {"montage_id": "yoq"})
    assert err and "404" in text
    text, err = call(s, "export_clip", {"montage_id": "m1"})
    assert err and "confirm" in text


def test_live_engine_gone(live_engine, tmp_path):
    from lahza_engine.core import discovery as d
    from lahza_engine.mcp_server.engine_client import default_locator

    d.discovery_path(live_engine["data"]).unlink()
    s = MCPServer(LahzaTools(EngineClient(default_locator(live_engine["data"]))), version="t")
    text, err = call(s, "list_projects")
    assert err and "lahza-engine install-service" in text
