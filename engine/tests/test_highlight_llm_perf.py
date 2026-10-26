"""M3-PERF-2: LLM highlight tezligi - thinking o'chirilgan, chiqish chegaralangan, parallel oynalar."""

import json
import re
import threading
import time

import httpx
import pytest
from conftest import make_sentences

from lahza_engine.config import HighlightConfig
from lahza_engine.highlight.llm import LlamaServerClient, make_windows, propose_candidates
from lahza_engine.highlight.schema import (
    LLM_MAX_HASHTAGS,
    LLM_TEXT_LIMITS,
    LlmResponse,
    json_schema,
)

_LINE = re.compile(r"^(\d+) \| ", re.M)


def _cand(start: int, end: int) -> dict:
    return {"start_id": start, "end_id": end, "hook_id": start, "turi": "maslahat",
            "mustaqil": True,
            "ballar": {"hook": 8, "mustaqillik": 8, "hissiyot": 6, "foyda": 7, "aniqlik": 8},
            "sarlavha": f"Nomzod {start}", "sabab": "aniq fikr", "izoh_matni": "izoh",
            "heshteglar": ["podkast"]}


def test_llm_schema_caps_free_text_and_candidates() -> None:
    s = json_schema(4)
    cand = s["$defs"]["LlmCandidate"]["properties"]
    for name, limit in LLM_TEXT_LIMITS.items():
        assert cand[name]["maxLength"] == limit
    assert cand["heshteglar"]["maxItems"] == LLM_MAX_HASHTAGS
    assert cand["heshteglar"]["items"]["maxLength"] > 0
    assert s["properties"]["nomzodlar"]["maxItems"] == 4
    # Pydantic modeli o'zgarmaydi: sxema chegarasidagi javob qat'iy tekshiruvdan o'tadi.
    raw = {"nomzodlar": [_cand(0, 3) | {"sabab": "x" * LLM_TEXT_LIMITS["sabab"],
                                        "izoh_matni": "y" * LLM_TEXT_LIMITS["izoh_matni"]}]}
    assert len(LlmResponse.model_validate(raw).nomzodlar) == 1


def test_request_body_disables_thinking_and_caps_output() -> None:
    c = LlamaServerClient("http://x", "m", max_tokens=1536, dry_multiplier=0.8)
    body = c.request_body("p", {"type": "object"})
    c.close()
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["max_tokens"] == 1536
    assert body["dry_multiplier"] == 0.8
    assert body["cache_prompt"] is True
    assert body["response_format"]["json_schema"]["strict"] is True
    plain = LlamaServerClient("http://x", "m").request_body("p", {})
    assert "max_tokens" not in plain and "dry_multiplier" not in plain


def test_complete_json_reads_content_with_timings() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"nomzodlar": []}'}, "finish_reason": "length"}],
            "timings": {"prompt_n": 10, "prompt_per_second": 900.0, "predicted_n": 5,
                        "predicted_per_second": 35.0}})

    c = LlamaServerClient("http://x", "m", max_tokens=8)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    assert c.complete_json("p", {}) == '{"nomzodlar": []}'
    assert seen["chat_template_kwargs"]["enable_thinking"] is False


class _SlowClient:
    """Oynalarni har xil kechikish bilan qaytaradi; bir vaqtdagi so'rovlarni sanaydi."""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()
        self.schemas: list[dict] = []

    def complete_json(self, prompt: str, schema: dict, temperature: float = 0.2) -> str:
        ids = [int(m) for m in _LINE.findall(prompt)]
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.schemas.append(schema)
        # Birinchi oyna eng sekin - natija tartibi baribir oynalar tartibida qolishi kerak.
        time.sleep(0.05 if ids[0] == 0 else 0.01)
        with self.lock:
            self.active -= 1
        return json.dumps({"nomzodlar": [_cand(ids[0], ids[0] + 2)]})


def test_propose_candidates_parallel_keeps_window_order() -> None:
    sents = make_sentences(200, dur_ms=6000)
    cfg = HighlightConfig(llm_window_ms=120_000, llm_window_overlap_ms=30_000, llm_parallel=3)
    windows = make_windows(sents, cfg)
    assert len(windows) > 3
    client = _SlowClient()
    progress: list[float] = []
    out = propose_candidates(client, sents, cfg, on_progress=progress.append)  # type: ignore[arg-type]
    assert [c.start_id for c in out] == [w.first_id for w in windows]
    assert 1 < client.peak <= 3
    assert progress[-1] == 1.0 and progress == sorted(progress)
    assert all(s["properties"]["nomzodlar"]["maxItems"] == cfg.llm_max_candidates
               for s in client.schemas)


def test_propose_candidates_sequential_when_parallel_is_one() -> None:
    sents = make_sentences(200, dur_ms=6000)
    cfg = HighlightConfig(llm_window_ms=120_000, llm_window_overlap_ms=30_000, llm_parallel=1)
    client = _SlowClient()
    out = propose_candidates(client, sents, cfg)  # type: ignore[arg-type]
    assert client.peak == 1 and len(out) == len(make_windows(sents, cfg))
    assert propose_candidates(client, [], cfg) == []  # type: ignore[arg-type]


def test_propose_candidates_propagates_errors() -> None:
    class Boom(_SlowClient):
        def complete_json(self, prompt: str, schema: dict, temperature: float = 0.2) -> str:
            raise httpx.ConnectError("down")

    sents = make_sentences(200, dur_ms=6000)
    cfg = HighlightConfig(llm_window_ms=120_000, llm_window_overlap_ms=30_000)
    with pytest.raises(httpx.ConnectError):
        propose_candidates(Boom(), sents, cfg)  # type: ignore[arg-type]
