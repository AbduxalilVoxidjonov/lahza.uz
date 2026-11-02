from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from lahza_engine.core import llama_server as module


@pytest.fixture
def child(monkeypatch):
    proc = Mock()
    proc.poll.return_value = None
    monkeypatch.setattr(module, "free_port", lambda: 12345)
    monkeypatch.setattr(module, "find_tool", lambda name: Path("/fake/llama-server"))
    monkeypatch.setattr(module.subprocess, "Popen", Mock(return_value=proc))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return proc


def test_success_preserves_user_context_and_stops(child, monkeypatch):
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    server = module.LlamaServer(Path("model.gguf"), ctx_size=2048, gpu_layers=3)
    with server as url:
        assert url == "http://127.0.0.1:12345"
        args = module.subprocess.Popen.call_args.args[0]
        assert args[args.index("--host") + 1] == "127.0.0.1"
        assert args[args.index("--parallel") + 1] == "1"
        assert args[args.index("-c") + 1] == "2048"
        assert args[args.index("-ngl") + 1] == "3"
        assert "--reasoning-budget" not in args
    child.terminate.assert_called_once()
    child.wait.assert_called_once_with(timeout=10)
    assert server.proc is None


def test_parallel_slots_and_thinking_off_flags(child, monkeypatch):
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    server = module.LlamaServer(Path("model.gguf"), ctx_size=16384, parallel=2, thinking=False)
    with server:
        args = module.subprocess.Popen.call_args.args[0]
        assert args[args.index("--parallel") + 1] == "2"
        assert args[args.index("-c") + 1] == "16384"
        assert args[args.index("--reasoning-budget") + 1] == "0"
    child.terminate.assert_called_once()
    child.wait.assert_called_once_with(timeout=10)
    assert server.proc is None


@pytest.mark.parametrize("error", [RuntimeError("bad health"), KeyboardInterrupt(), SystemExit(2)])
def test_all_startup_errors_cleanup(child, monkeypatch, error):
    monkeypatch.setattr(module.httpx, "get", Mock(side_effect=error))
    server = module.LlamaServer(Path("model"))
    with pytest.raises(type(error)):
        server.__enter__()
    child.terminate.assert_called_once()
    child.wait.assert_called_once()
    assert server.proc is None


def test_timeout_cleanup_and_bounded_health(child, monkeypatch):
    clock = iter([0.0, 0.1, 0.2, 1.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    get = Mock(side_effect=httpx.ConnectError("not ready"))
    monkeypatch.setattr(module.httpx, "get", get)
    server = module.LlamaServer(Path("model"), startup_timeout_s=0.3)
    with pytest.raises(TimeoutError):
        server.__enter__()
    assert get.call_args.kwargs["timeout"] <= 0.3
    child.terminate.assert_called_once()
    child.wait.assert_called_once()
    assert server.proc is None


def test_early_exit_reaped(child):
    child.poll.return_value = 1
    server = module.LlamaServer(Path("model"))
    with pytest.raises(RuntimeError):
        server.__enter__()
    child.wait.assert_called_once_with()
    child.terminate.assert_not_called()
    assert server.proc is None


def test_kill_is_followed_by_wait(child, monkeypatch):
    child.wait.side_effect = [module.subprocess.TimeoutExpired("server", 10), None]
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    server = module.LlamaServer(Path("model"))
    with pytest.raises(ValueError, match="body"), server:
        raise ValueError("body")
    child.kill.assert_called_once()
    assert child.wait.call_count == 2
    assert child.wait.call_args_list[0].kwargs == {"timeout": 10}
    assert child.wait.call_args_list[1].kwargs == {}
    assert server.proc is None


def test_terminate_race_reaped(child):
    child.terminate.side_effect = ProcessLookupError()
    server = module.LlamaServer(Path("model"))
    server.proc = child
    server.__exit__()
    child.wait.assert_called_once_with()
    server.__exit__()  # idempotent


def test_kill_race_still_reaped(child, monkeypatch):
    child.wait.side_effect = [module.subprocess.TimeoutExpired("server", 10), None]
    child.kill.side_effect = ProcessLookupError()
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    with module.LlamaServer(Path("model")):
        pass
    assert child.wait.call_count == 2


def test_two_instances_share_nonblocking_slot_and_only_owner_releases(child, monkeypatch):
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    first = module.LlamaServer(Path("first.gguf"))
    second = module.LlamaServer(Path("second.gguf"))
    with first:
        with pytest.raises(module.LlamaServerBusy, match="retry"):
            second.__enter__()
        second.__exit__()  # Failed acquisition must not release the first instance's slot.
        with pytest.raises(module.LlamaServerBusy):
            second.__enter__()
        assert module.subprocess.Popen.call_count == 1
        assert first._owns_llm_lock and not second._owns_llm_lock
    with second:
        # Late/idempotent cleanup by the former owner must not release the new owner's slot.
        first.__exit__()
        with pytest.raises(module.LlamaServerBusy):
            first.__enter__()
    assert module.subprocess.Popen.call_count == 2
    assert not module._LLM_LOCK.locked()


@pytest.mark.parametrize("failure_stage", ["free_port", "find_tool", "Popen", "health"])
def test_every_startup_failure_releases_shared_slot(child, monkeypatch, failure_stage):
    healthy = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(module.httpx, "get", healthy)
    with monkeypatch.context() as failing:
        failure = Mock(side_effect=OSError("startup failure"))
        if failure_stage == "Popen":
            failing.setattr(module.subprocess, "Popen", failure)
        elif failure_stage == "health":
            failing.setattr(module.httpx, "get", failure)
        else:
            failing.setattr(module, failure_stage, failure)
        server = module.LlamaServer(Path("failed.gguf"))
        with pytest.raises(OSError, match="startup failure"):
            server.__enter__()
        assert not server._owns_llm_lock and server.proc is None
        assert not module._LLM_LOCK.locked()
    with module.LlamaServer(Path("next.gguf")):
        pass
    assert not module._LLM_LOCK.locked()


def test_context_body_failure_releases_shared_slot(child, monkeypatch):
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    with pytest.raises(ValueError, match="body"), module.LlamaServer(Path("first.gguf")):
        raise ValueError("body")
    with module.LlamaServer(Path("next.gguf")):
        pass
    assert not module._LLM_LOCK.locked()


# ---- Issiq server (montaj rejasi) ---------------------------------------------------------

class FakeServer:
    """Jarayonsiz LlamaServer o'rnini bosuvchi: `_LLM_LOCK` ni haqiqiy server kabi ushlaydi."""

    def __init__(self, log, name="s"):
        self.log, self.name, self.proc = log, name, None

    def __enter__(self):
        if not module._LLM_LOCK.acquire(blocking=False):
            raise module.LlamaServerBusy("busy")
        self.proc = Mock(**{"poll.return_value": None})
        self.log.append(("start", self.name))
        return f"http://127.0.0.1:1/{self.name}"

    def __exit__(self, *exc):
        if self.proc is not None:
            self.proc = None
            module._LLM_LOCK.release()
            self.log.append(("stop", self.name))


@pytest.fixture
def warm():
    pool = module.WarmLlamaServer(idle_s=lambda: 60.0)
    yield pool
    pool.stop()
    assert not module._LLM_LOCK.locked()


def test_warm_reuse_and_busy(warm):
    log = []
    with warm.lease("k", lambda: FakeServer(log)) as url:
        assert url.endswith("/s")
        with pytest.raises(module.LlamaServerBusy), warm.lease("k", lambda: FakeServer(log)):
            pass
    with warm.lease("k", lambda: FakeServer(log, "other")) as url:
        assert url.endswith("/s")  # qayta ishga tushmadi
    assert log == [("start", "s")] and warm.running and module._LLM_LOCK.locked()
    warm.stop()
    assert log[-1] == ("stop", "s") and not warm.running


def test_warm_idle_expiry(monkeypatch):
    import threading
    log = []
    stopped = threading.Event()
    pool = module.WarmLlamaServer(idle_s=lambda: 0.05)
    original = pool._expire
    monkeypatch.setattr(pool, "_expire", lambda token: (original(token), stopped.set()))
    with pool.lease("k", lambda: FakeServer(log)):
        pass
    assert stopped.wait(5)
    assert log == [("start", "s"), ("stop", "s")] and not pool.running
    assert not module._LLM_LOCK.locked()


def test_warm_new_lease_cancels_idle_timer(warm):
    log = []
    with warm.lease("k", lambda: FakeServer(log)):
        pass
    token = warm._timer_token
    with warm.lease("k", lambda: FakeServer(log)):
        warm._expire(token)  # eski taymer kech ishlasa ham server o'chmaydi
    assert log == [("start", "s")] and warm.running


def test_warm_restart_on_death_and_key_change(warm):
    log = []
    with warm.lease("a", lambda: FakeServer(log, "1")):
        pass
    warm._server.proc.poll.return_value = 1  # jarayon o'ldi
    with warm.lease("a", lambda: FakeServer(log, "2")) as url:
        assert url.endswith("/2")
    with warm.lease("b", lambda: FakeServer(log, "3")) as url:
        assert url.endswith("/3")
    assert log == [("start", "1"), ("stop", "1"), ("start", "2"), ("stop", "2"), ("start", "3")]


def test_warm_error_discards_but_value_error_keeps(warm):
    log = []
    with pytest.raises(ValueError), warm.lease("k", lambda: FakeServer(log, "1")):
        raise ValueError("bad model JSON")
    assert warm.running
    with pytest.raises(httpx.ReadTimeout), warm.lease("k", lambda: FakeServer(log, "x")):
        raise httpx.ReadTimeout("deadline")
    assert not warm.running and log == [("start", "1"), ("stop", "1")]
    assert not module._LLM_LOCK.locked()


def test_warm_startup_failure_cleans_up(warm):
    log = []

    class Broken(FakeServer):
        def __enter__(self):
            super().__enter__()
            raise TimeoutError("not ready")
    with pytest.raises(TimeoutError), warm.lease("k", lambda: Broken(log)):
        pass
    assert log == [("start", "s"), ("stop", "s")] and not warm.running
    with warm.lease("k", lambda: FakeServer(log, "2")):
        pass  # keyingi so'rov odatdagidek ishlaydi


def test_warm_stop_during_lease_closes_at_end(warm):
    log = []
    with warm.lease("k", lambda: FakeServer(log)):
        warm.stop()  # engine to'xtamoqda; so'rov tugashini kutamiz
        assert log == [("start", "s")]
    assert log[-1] == ("stop", "s") and not warm.running
    with warm.lease("k", lambda: FakeServer(log, "2")):
        pass  # stop() doimiy yopmaydi (testlar/qayta ishga tushish)
    assert warm.running


def test_stop_warm_servers_hook(warm):
    log = []
    with warm.lease("k", lambda: FakeServer(log)):
        pass
    module.stop_warm_servers()
    assert log[-1] == ("stop", "s") and not module._LLM_LOCK.locked()


def test_highlight_server_evicts_idle_warm_server(child, monkeypatch, warm):
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    log = []
    # Ijara davom etayotganda highlight kutadi (avvalgi semantika).
    with warm.lease("k", lambda: FakeServer(log)), pytest.raises(module.LlamaServerBusy):
        module.LlamaServer(Path("highlight.gguf")).__enter__()
    with module.LlamaServer(Path("highlight.gguf")) as url:
        assert url == "http://127.0.0.1:12345"
        assert log[-1] == ("stop", "s") and not warm.running
    assert not module._LLM_LOCK.locked()


def test_cache_ram_flag_and_live_tracking(child, monkeypatch):
    monkeypatch.setattr(module.httpx, "get", Mock(return_value=Mock(status_code=200)))
    with module.LlamaServer(Path("model.gguf"), cache_ram_mib=256):
        args = module.subprocess.Popen.call_args.args[0]
        assert args[args.index("--cache-ram") + 1] == "256"
        assert child in module._LIVE
        module.kill_all()
        child.kill.assert_called_once()
    assert child not in module._LIVE


@pytest.mark.parametrize(("raw", "expected"), [(None, 300.0), ("", 300.0), ("12.5", 12.5),
                                               ("0", 0.0), ("-3", 0.0), ("abc", 300.0),
                                               ("nan", 300.0)])
def test_idle_timeout_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("LAHZA_LLM_IDLE_S", raising=False)
    else:
        monkeypatch.setenv("LAHZA_LLM_IDLE_S", raw)
    assert module.idle_timeout_s() == expected

