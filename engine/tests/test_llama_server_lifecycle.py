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
