"""ADB-7: mustaqil Lahza Engine servisi - plist/XML generatsiyasi, dry-run, ikki nusxa oldini olish,
uninstall tozaligi, desktop sidecar'ining servisga ulanishi (attach). `launchctl`/`schtasks` hech
qachon haqiqiy chaqirilmaydi: `subprocess.run` va runner almashtiriladi."""

from __future__ import annotations

import json
import plistlib
import signal
import stat
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lahza_engine.core import discovery as d
from lahza_engine.service import (
    SERVICE_LABEL,
    WINDOWS_TASK_NAME,
    launchd,
    manager,
    runtime,
    winsched,
)
from lahza_engine.service.spec import ServiceSpec, build_spec

REPO = Path(__file__).resolve().parents[2]
NS = {"t": winsched.TASK_NS}


@pytest.fixture(autouse=True)
def _no_real_side_effects(monkeypatch):
    """Haqiqiy launchctl/schtasks yo'q; signal ishlovchilari va fayl logi test jarayonini buzmasin."""
    from lahza_engine.core import logs

    def forbidden(*a, **k):
        raise AssertionError(f"haqiqiy tashqi buyruq chaqirildi: {a}")

    monkeypatch.setattr(manager, "default_runner", forbidden)
    monkeypatch.setattr(logs, "setup_file_logging", lambda *_a, **_k: None)
    saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None))
             if s is not None}
    yield
    for s, h in saved.items():
        signal.signal(s, h)


class FakeRunner:
    def __init__(self, fail: set[str] | None = None, stdout: str = "") -> None:
        self.calls: list[list[str]] = []
        self.fail = fail or set()
        self.stdout = stdout

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        rc = 1 if any(w in cmd for w in self.fail) else 0
        return subprocess.CompletedProcess(cmd, rc, stdout=self.stdout, stderr="xato" if rc else "")


def _spec(tmp_path, env=None) -> ServiceSpec:
    return ServiceSpec(program=["/Applications/Lahza Studio.app/Contents/MacOS/lahza-engine"],
                       data_dir=tmp_path / "data", env=env or {})


@pytest.fixture
def live_pid():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    yield p
    p.kill()
    p.wait()


def _write_engine_json(data_dir: Path, pid: int, port: int = 47600, token: str = "svc-token") -> None:
    d.write_discovery(d.discovery_path(data_dir), port, token, "9.9.9", pid=pid)


# ---- Identifikator ----------------------------------------------------------------------------

def test_label_derived_from_app_identifier():
    conf = json.loads((REPO / "app" / "src-tauri" / "tauri.conf.json").read_text())
    from lahza_engine.service import APP_IDENTIFIER

    assert conf["identifier"] == APP_IDENTIFIER
    assert SERVICE_LABEL == "uz.lahza.engine" and SERVICE_LABEL.startswith(APP_IDENTIFIER.rsplit(".", 1)[0] + ".")
    assert launchd.plist_path(Path("/h")) == Path("/h/Library/LaunchAgents/uz.lahza.engine.plist")


# ---- macOS plist ------------------------------------------------------------------------------

def test_plist_generation_parses(tmp_path):
    spec = build_spec(tmp_path / "data", program="/opt/lahza-engine",
                      environ={"LAHZA_BIN_DIR": "/res/bin", "LAHZA_TOKEN": "secret", "HOME": "/h", "LAHZA_CATALOG": ""})
    pl = plistlib.loads(launchd.render_plist(spec))
    assert pl["Label"] == "uz.lahza.engine"
    assert pl["ProgramArguments"] == ["/opt/lahza-engine", "serve", "--service"]
    assert pl["RunAtLoad"] is True and pl["KeepAlive"] == {"SuccessfulExit": False}
    assert pl["ThrottleInterval"] >= 10 and pl["LimitLoadToSessionType"] == "Aqua"
    assert pl["StandardOutPath"] == str(tmp_path / "data" / "Logs" / "engine-service.out.log")
    assert pl["StandardErrorPath"] == str(tmp_path / "data" / "Logs" / "engine-service.err.log")
    # Token hech qachon plist'ga tushmaydi; bo'sh qiymatlar va begona o'zgaruvchilar ham.
    assert pl["EnvironmentVariables"] == {"LAHZA_BIN_DIR": "/res/bin"}
    raw = launchd.render_plist(spec).decode()
    assert "secret" not in raw and "--host" not in raw and "0.0.0.0" not in raw


def test_default_program_dev_and_frozen(monkeypatch, tmp_path):
    assert build_spec(tmp_path, environ={}).program == [sys.executable, "-m", "lahza_engine"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert build_spec(tmp_path, environ={}).program == [sys.executable]


def test_parse_launchctl_print():
    out = "gui/501/uz.lahza.engine = {\n\tstate = running\n\tpid = 4321\n\tlast exit code = (never exited)\n}"
    assert launchd.parse_print(out) == {"state": "running", "pid": 4321, "last_exit": "(never exited)"}


# ---- Windows XML ------------------------------------------------------------------------------

def test_task_xml_generation(tmp_path):
    spec = ServiceSpec(program=[r"C:\Program Files\Lahza & Co\lahza-engine.exe"], data_dir=tmp_path / "d",
                       env={"LAHZA_BIN_DIR": r"C:\Program Files\Lahza\bin"})
    xml = winsched.build_task_xml(spec, user="PC\\ali")
    root = ET.fromstring(xml.encode("utf-16"))  # schtasks UTF-16 faylni kutadi
    assert root.find("t:RegistrationInfo/t:URI", NS).text == WINDOWS_TASK_NAME
    assert root.find("t:Triggers/t:LogonTrigger/t:UserId", NS).text == "PC\\ali"
    pr = root.find("t:Principals/t:Principal", NS)
    assert pr.find("t:LogonType", NS).text == "InteractiveToken"
    assert pr.find("t:RunLevel", NS).text == "LeastPrivilege"
    st = root.find("t:Settings", NS)
    assert st.find("t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
    assert st.find("t:ExecutionTimeLimit", NS).text == "PT0S"
    assert st.find("t:RestartOnFailure/t:Count", NS).text == "3"
    ex = root.find("t:Actions/t:Exec", NS)
    assert ex.find("t:Command", NS).text == r"C:\Program Files\Lahza & Co\lahza-engine.exe"
    args = ex.find("t:Arguments", NS).text
    assert args.startswith("serve --service --env-file ") and str(winsched.env_file(spec)) in args


def test_task_xml_dev_program_and_no_env(tmp_path):
    spec = ServiceSpec(program=[r"C:\py\python.exe", "-m", "lahza_engine"], data_dir=tmp_path)
    root = ET.fromstring(winsched.build_task_xml(spec, user="u").encode("utf-16"))
    assert root.find("t:Actions/t:Exec/t:Arguments", NS).text == "-m lahza_engine serve --service"


def test_windows_commands_and_run_key(tmp_path):
    spec = _spec(tmp_path)
    cmds = winsched.install_commands(Path("x.xml"))
    assert cmds[0][:5] == ["schtasks", "/Create", "/TN", WINDOWS_TASK_NAME, "/XML"] and "/F" in cmds[0]
    assert winsched.uninstall_commands()[1] == ["schtasks", "/Delete", "/TN", WINDOWS_TASK_NAME, "/F"]
    rk = winsched.run_key_command(spec)
    assert rk[0] == "reg" and "HKCU" in rk[2] and rk[-2].endswith("serve --service")
    assert winsched.current_user({"USERNAME": "ali", "USERDOMAIN": "PC"}) == "PC\\ali"


# ---- Dry-run ----------------------------------------------------------------------------------

def test_cli_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    from lahza_engine import cli

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cli.main(["install-service", "--dry-run", "--program", "/opt/lahza-engine"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True and out["label"] == "uz.lahza.engine"
    writes = [s for s in out["plan"] if s["op"] == "write"]
    assert writes[0]["path"] == str(tmp_path / "home" / "Library" / "LaunchAgents" / "uz.lahza.engine.plist")
    assert plistlib.loads(writes[0]["content"].encode())["ProgramArguments"][-2:] == ["serve", "--service"]
    assert [s["cmd"][:2] for s in out["plan"] if s["op"] == "run"] == [["launchctl", "bootout"],
                                                                      ["launchctl", "bootstrap"]]
    assert not (tmp_path / "home").exists() and not (tmp_path / "data").exists()

    assert cli.main(["uninstall-service", "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True and {s["op"] for s in out["plan"]} == {"run", "remove"}
    assert not (tmp_path / "home").exists()


def test_windows_dry_run_plan(tmp_path):
    out = manager.install(_spec(tmp_path, env={"LAHZA_BIN_DIR": "C:\\b"}), dry_run=True, platform="win32")
    ops = [(s["op"], Path(s.get("path", "")).name) for s in out["plan"]]
    assert ("write", "service-env.json") in ops and ("write", "lahza-engine-task.xml") in ops
    xml_step = next(s for s in out["plan"] if s.get("encoding") == "utf-16")
    ET.fromstring(xml_step["content"].encode("utf-16"))
    assert [s["cmd"][1] for s in out["plan"] if s["op"] == "run"] == ["/Create", "/Run"]
    assert not (tmp_path / "data").exists()


def test_unsupported_platform(tmp_path):
    with pytest.raises(manager.ServiceError):
        manager.install(_spec(tmp_path), dry_run=True, platform="linux")


# ---- O'rnatish / o'chirish (soxta runner) -----------------------------------------------------

def test_install_and_uninstall_clean_macos(tmp_path):
    home, data = tmp_path / "home", tmp_path / "data"
    exe = tmp_path / "lahza-engine"
    exe.write_text("#!/bin/sh\n")
    spec = ServiceSpec(program=[str(exe)], data_dir=data)
    r = FakeRunner()
    res = manager.install(spec, platform="darwin", home=home, uid=501, runner=r)
    plist = home / "Library" / "LaunchAgents" / "uz.lahza.engine.plist"
    assert plistlib.loads(plist.read_bytes())["ProgramArguments"] == [str(exe), "serve", "--service"]
    assert stat.S_IMODE(plist.stat().st_mode) == 0o644
    assert r.calls == [["launchctl", "bootout", "gui/501/uz.lahza.engine"],
                       ["launchctl", "bootstrap", "gui/501", str(plist)]]
    assert (data / "Logs").is_dir() and res["dry_run"] is False

    # Servis ishlagan izlar: start jurnali, eskirgan taxallus, loglar.
    runtime.record_start(data)
    runtime.register_alias(data, "x", pid=999999)
    (data / "Logs" / "engine-service.err.log").write_text("log")
    (data / "Logs" / "engine.log").write_text("asosiy log")
    r = FakeRunner(fail={"bootout"})  # yuklanmagan bo'lsa ham uninstall davom etadi
    manager.uninstall(data, platform="darwin", home=home, uid=501, runner=r)
    assert r.calls == [["launchctl", "bootout", "gui/501/uz.lahza.engine"]]
    assert not plist.exists() and not (data / "service").exists() and not (data / "engine.clients").exists()
    assert (data / "Logs" / "engine-service.err.log").exists()  # loglar standart saqlanadi
    # Takroriy uninstall xavfsiz; --purge-logs faqat servis loglarini o'chiradi.
    manager.uninstall(data, platform="darwin", home=home, uid=501, runner=FakeRunner(), purge_logs=True)
    assert not (data / "Logs" / "engine-service.err.log").exists()
    assert (data / "Logs" / "engine.log").exists()


def test_install_failure_reported(tmp_path, monkeypatch, capsys):
    exe = tmp_path / "e"
    exe.write_text("")
    with pytest.raises(manager.ServiceError, match="bootstrap"):
        manager.install(ServiceSpec([str(exe)], tmp_path / "d"), platform="darwin", home=tmp_path / "h",
                        uid=1, runner=FakeRunner(fail={"bootstrap"}))
    with pytest.raises(manager.ServiceError, match="topilmadi"):
        manager.install(ServiceSpec([str(tmp_path / "yoq")], tmp_path / "d"), platform="darwin",
                        home=tmp_path / "h", uid=1, runner=FakeRunner())
    # CLI: xato -> 1 kod va o'zbekcha xabar; haqiqiy launchctl chaqirilmaydi (default_runner taqiqlangan).
    from lahza_engine import cli

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cli.main(["install-service", "--program", str(tmp_path / "yoq")]) == 1
    assert "topilmadi" in capsys.readouterr().err


def test_install_windows_writes_utf16_and_env(tmp_path, monkeypatch):
    monkeypatch.setattr(winsched, "current_user", lambda environ=None: "PC\\ali")
    exe = tmp_path / "lahza-engine.exe"
    exe.write_text("")
    spec = ServiceSpec([str(exe)], tmp_path / "data", env={"LAHZA_BIN_DIR": "C:\\b"})
    r = FakeRunner()
    manager.install(spec, platform="win32", runner=r)
    xml = (tmp_path / "data" / "service" / "lahza-engine-task.xml").read_bytes()
    assert xml[:2] in (b"\xff\xfe", b"\xfe\xff")  # BOM
    ET.fromstring(xml)
    assert json.loads((tmp_path / "data" / "service" / "service-env.json").read_text()) == {"LAHZA_BIN_DIR": "C:\\b"}
    assert [c[1] for c in r.calls] == ["/Create", "/Run"]
    r = FakeRunner(fail={"/End"})
    manager.uninstall(tmp_path / "data", platform="win32", runner=r)
    assert [c[1] for c in r.calls] == ["/End", "/Delete"] and not (tmp_path / "data" / "service").exists()


def test_status_macos(tmp_path, live_pid):
    data = tmp_path / "data"
    _write_engine_json(data, live_pid.pid)
    r = FakeRunner(stdout="\tstate = running\n\tpid = 77\n")
    st = manager.status(data, platform="darwin", home=tmp_path, uid=5, runner=r, health=lambda p, t: True)
    assert r.calls == [["launchctl", "print", "gui/5/uz.lahza.engine"]]
    assert st["installed"] is False and st["loaded"] is True and st["state"] == "running" and st["pid"] == 77
    assert st["engine"] == {"running": True, "pid": live_pid.pid, "port": 47600, "version": "9.9.9"}
    assert "svc-token" not in json.dumps(st)
    st = manager.status(tmp_path / "bosh", platform="darwin", home=tmp_path, uid=5,
                        runner=FakeRunner(fail={"print"}))
    assert st["loaded"] is False and st["engine"] == {"running": False}


# ---- Servis rejimi: ikki nusxa va qulash cheklovi ---------------------------------------------

@pytest.fixture
def serve_env(tmp_path, monkeypatch):
    from lahza_engine import cli

    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    for k in ("LAHZA_DISCOVERY", "LAHZA_IPC", "LAHZA_TOKEN", "LAHZA_CORS_ORIGINS", "LAHZA_ATTACH"):
        monkeypatch.delenv(k, raising=False)
    seen: dict = {}

    def fake_run(app, port, a, cleanup):
        seen.update(port=port, app=app, engine=json.loads((tmp_path / "data" / "engine.json").read_text())
                    if (tmp_path / "data" / "engine.json").exists() else None)

    monkeypatch.setattr(cli, "_run_server", fake_run)
    monkeypatch.setattr(d, "port_free", lambda p, host="127.0.0.1": True)
    return seen


def test_service_mode_starts_discovery_engine(serve_env, tmp_path):
    from lahza_engine import cli

    assert cli.main(["serve", "--service"]) == 0
    assert serve_env["port"] == 47600 and serve_env["engine"]["port"] == 47600
    tok = serve_env["engine"]["token"]
    runtime.register_alias(tmp_path / "data", "desktop-tok")  # o'z pid'imiz - tirik
    c = TestClient(serve_env["app"])
    assert c.get("/v1/health", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert c.get("/v1/health", headers={"Authorization": "Bearer desktop-tok"}).status_code == 200
    assert c.get("/v1/health", headers={"Authorization": "Bearer begona"}).status_code == 401
    assert json.loads((tmp_path / "data" / "service" / "starts.json").read_text())


def test_service_mode_refuses_second_instance(serve_env, tmp_path, monkeypatch, live_pid, capsys):
    from lahza_engine import cli

    _write_engine_json(tmp_path / "data", live_pid.pid)
    monkeypatch.setattr(runtime, "http_health", lambda port, token: token == "svc-token")
    assert cli.main(["serve", "--service"]) == 0
    assert "port" not in serve_env  # server ko'tarilmadi
    assert "allaqachon ishlayapti" in capsys.readouterr().err
    assert json.loads((tmp_path / "data" / "engine.json").read_text())["pid"] == live_pid.pid  # tegilmadi


def test_service_mode_ignores_stale_discovery(serve_env, tmp_path, monkeypatch):
    from lahza_engine import cli

    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    _write_engine_json(tmp_path / "data", p.pid)  # o'lik pid
    monkeypatch.setattr(runtime, "http_health", lambda *a: pytest.fail("o'lik pid uchun so'ralmasin"))
    assert cli.main(["serve", "--service"]) == 0
    assert serve_env["port"] == 47600


def test_crash_limit(serve_env, tmp_path, capsys):
    from lahza_engine import cli

    data = tmp_path / "data"
    now = time.time()
    for i in range(runtime.MAX_STARTS):
        assert runtime.record_start(data, now=now + i) is True
    assert runtime.record_start(data, now=now + 10) is False
    assert runtime.record_start(data, now=now + runtime.WINDOW_S + 100) is True  # oyna o'tdi
    for _ in range(runtime.MAX_STARTS + 1):
        runtime.record_start(data)
    assert cli.main(["serve", "--service"]) == 0  # 0: launchd qayta ko'tarmaydi
    assert "port" not in serve_env and "juda ko'p" in capsys.readouterr().err


def test_env_file_loading(tmp_path, monkeypatch):
    f = tmp_path / "env.json"
    f.write_text(json.dumps({"LAHZA_BIN_DIR": "/b", "LAHZA_TOKEN": "x", "PATH": "/evil", "LAHZA_CATALOG": "/c"}))
    env = {"LAHZA_CATALOG": "/mavjud"}
    assert runtime.load_env_file(f, env) == ["LAHZA_BIN_DIR"]
    assert env == {"LAHZA_CATALOG": "/mavjud", "LAHZA_BIN_DIR": "/b"}
    assert runtime.load_env_file(tmp_path / "yoq.json", env) == []


# ---- Desktop sidecar: mavjud engine'ga ulanish (attach) ---------------------------------------

def test_sidecar_attaches_instead_of_second_engine(serve_env, tmp_path, monkeypatch, live_pid, capsys):
    from lahza_engine import cli

    data = tmp_path / "data"
    _write_engine_json(data, live_pid.pid, port=47601)
    seen_alias: list = []

    def health(port, token):
        if token == "desktop-tok":  # taxallus fayli shu paytda mavjud bo'lishi kerak
            seen_alias.append(runtime.live_aliases(data, prune=False))
        return True

    monkeypatch.setattr(runtime, "http_health", health)
    monkeypatch.setenv("LAHZA_TOKEN", "desktop-tok")
    threading.Timer(0.3, lambda: (live_pid.kill(), live_pid.wait())).start()  # servis "o'ladi" -> sidecar chiqadi, Tauri qayta ishga tushiradi
    t0 = time.monotonic()
    code = cli.main(["serve", "--port", "0"])
    assert code == runtime.ATTACH_EXIT_SERVICE_GONE and time.monotonic() - t0 < 10
    assert "port" not in serve_env  # ikkinchi engine ko'tarilmadi
    assert "LAHZA_READY port=47601" in capsys.readouterr().out
    assert seen_alias == [["desktop-tok"]]
    assert list(runtime.alias_dir(data).glob("*.json")) == []  # chiqishda taxallus o'chirildi


def test_attach_exits_on_parent_signal(tmp_path, live_pid):
    data = tmp_path / "data"
    waiter = runtime.AttachWaiter()
    threading.Timer(0.2, lambda: setattr(waiter, "should_exit", True)).start()
    out: list[str] = []
    code = runtime.run_attached(data, {"pid": live_pid.pid, "port": 47600}, "tok", waiter,
                                health=lambda p, t: True, poll_s=0.05, emit=out.append)
    assert code == 0 and out == ["LAHZA_READY port=47600"]
    assert list(runtime.alias_dir(data).glob("*.json")) == []


def test_sidecar_falls_back_when_alias_rejected(serve_env, tmp_path, monkeypatch, live_pid):
    from lahza_engine import cli

    _write_engine_json(tmp_path / "data", live_pid.pid)
    # Eski engine taxallusni bilmaydi: servis tokeni bilan 200, sidecar tokeni bilan 401.
    monkeypatch.setattr(runtime, "http_health", lambda port, token: token == "svc-token")
    assert cli.main(["serve", "--port", "0", "--token", "desktop-tok"]) == 0
    assert serve_env["port"] != 47600 and serve_env["engine"]["pid"] == live_pid.pid  # o'z engine'i, discovery'siz
    assert list(runtime.alias_dir(tmp_path / "data").glob("*.json")) == []


@pytest.mark.parametrize("env", [{"LAHZA_ATTACH": "0"}, {"LAHZA_CORS_ORIGINS": "http://127.0.0.1:1420"}])
def test_attach_disabled(serve_env, tmp_path, monkeypatch, live_pid, env):
    from lahza_engine import cli

    _write_engine_json(tmp_path / "data", live_pid.pid)
    monkeypatch.setattr(runtime, "http_health", lambda *a: pytest.fail("attach o'chiq - so'ralmasin"))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert cli.main(["serve", "--port", "0", "--token", "desktop-tok"]) == 0
    assert "port" in serve_env


def test_explicit_port_never_attaches(serve_env, tmp_path, monkeypatch, live_pid):
    from lahza_engine import cli

    _write_engine_json(tmp_path / "data", live_pid.pid)
    monkeypatch.setattr(runtime, "http_health", lambda *a: pytest.fail("so'ralmasin"))
    assert cli.main(["serve", "--port", "45123", "--token", "t"]) == 0
    assert serve_env["port"] == 45123


# ---- Taxallus middleware ----------------------------------------------------------------------

def test_alias_middleware_header_query_ws_and_dead_pid(tmp_path):
    from lahza_engine.api.app import create_app
    from lahza_engine.config import Settings

    data = tmp_path / "data"
    app = create_app(Settings(data_dir=data), token="asosiy")
    app.add_middleware(runtime.TokenAliasMiddleware, data_dir=data, token="asosiy", ttl_s=0)
    alias = runtime.register_alias(data, "alias-tok")
    if sys.platform != "win32":
        assert stat.S_IMODE(alias.stat().st_mode) == 0o600
        assert stat.S_IMODE(alias.parent.stat().st_mode) == 0o700
    c = TestClient(app)
    assert c.get("/v1/health", headers={"Authorization": "Bearer alias-tok"}).status_code == 200
    assert c.get("/v1/health", params={"t": "alias-tok"}).status_code == 200
    assert c.get("/v1/health", params={"t": "boshqa"}).status_code == 401
    with c.websocket_connect("/v1/events?t=alias-tok") as ws:
        ws.close()
    # Ota jarayoni o'lgan taxallus qabul qilinmaydi va fayli tozalanadi.
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    runtime.remove_alias(alias)
    stale = runtime.register_alias(data, "eski-tok", pid=dead.pid)
    assert c.get("/v1/health", headers={"Authorization": "Bearer eski-tok"}).status_code == 401
    assert not stale.exists()
