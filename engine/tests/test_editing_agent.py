"""Editing agent contract, isolated executor, and mocked local inference."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from lahza_engine.api.app import create_app
from lahza_engine.api.state import State
from lahza_engine.config import Settings
from lahza_engine.editing_agent import planner
from lahza_engine.editing_agent.executor import StalePlan, preview, revision
from lahza_engine.editing_agent.model import EditPlan, PlanIn
from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel, ModelStore, Registry
from lahza_engine.montage.model import MediaRef, MontageTimeline, VideoItem


@pytest.fixture
def timeline():
    return MontageTimeline(media={"m": MediaRef(id="m", path="/private/source.mp4", duration_ms=10000,
                            width=1920, height=1080, fps=30)},
                           video=[VideoItem(id="v", media="m", src_in_ms=0, src_out_ms=10000)])


def edit(tl, commands, selected=None, unresolved=None):
    return EditPlan.model_validate({"schema": "lahza.edit-plan/1", "base_revision": revision(tl, selected),
                                   "commands": commands, "unresolved": unresolved or []})


def command(tool, **args):
    return {"tool": tool, "args": args}


def test_real_executor(timeline):
    original = timeline.to_json()
    plan = edit(timeline, [command("set_format", profile="youtube_video"),
                          command("set_captions", enabled=True, font_size=80),
                          command("add_caption", text="Salom", start_ms=0, end_ms=2000),
                          command("set_color", preset="warm"),
                          command("freeze_clip", clip_id="v", at_ms=1500, duration_ms=500)])
    result = preview(timeline, plan, None)
    assert timeline.to_json() == original
    assert result.timeline.format.w == 1920
    assert result.timeline.captions.style.font_size == 80
    assert result.timeline.text[0].text == "Salom"
    assert result.timeline.video[0].fx[0].at_ms == 1500
    assert len(result.changes) == 5


@pytest.mark.parametrize("bad", [command("delete", clip_id="v"),
    command("set_color", preset="lut"), command("set_captions", enabled=1),
    command("freeze_clip", clip_id="v", at_ms=1.2, duration_ms=500),
    command("set_format", profile="youtube_video", path="/tmp/a"),
    command("add_caption", text="{\\an8}bad", start_ms=0, end_ms=100)])
def test_strict_commands(timeline, bad):
    with pytest.raises(ValidationError):
        edit(timeline, [bad])


@pytest.mark.parametrize("bad", [command("freeze_clip", clip_id="missing", at_ms=0, duration_ms=500),
    command("freeze_clip", clip_id="v", at_ms=9900, duration_ms=500),
    command("add_caption", text="Bad", start_ms=200, end_ms=100),
    command("add_caption", text="Bad", start_ms=0, end_ms=10001)])
def test_atomic_failure(timeline, bad):
    before = timeline.to_json()
    with pytest.raises(ValueError):
        preview(timeline, edit(timeline, [command("set_color", preset="cool"), bad]), None)
    assert timeline.to_json() == before


def test_stale_full_input_and_selection(timeline):
    plan = edit(timeline, [])
    with pytest.raises(StalePlan):
        preview(timeline, plan, "v")
    timeline.media["m"].path = "/another/path.mp4"
    with pytest.raises(StalePlan):
        preview(timeline, plan, None)


def test_refusal_and_unknown_fields(timeline):
    with pytest.raises(ValueError, match="Unresolved"):
        preview(timeline, edit(timeline, [], unresolved=["Cannot split"]), None)
    data = edit(timeline, []).model_dump(by_alias=True)
    data["script"] = "x"
    with pytest.raises(ValidationError):
        EditPlan.model_validate(data)
    with pytest.raises(ValidationError):
        edit(timeline, [command("set_color", preset="cool")] * 13)


@pytest.fixture
def store(tmp_path):
    store = ModelStore(tmp_path / "Models")
    path = store.root / "llm" / "test.gguf"
    path.parent.mkdir()
    path.write_bytes(b"GGUFtest")
    store._save(Registry(models=[InstalledModel(id="test", task=Task.LLM, version="1", path=str(path))],
                         defaults={"llm": "test"}))
    return store


@pytest.fixture(autouse=True)
def cold_planner():
    """Issiq server testlar orasida o'tib ketmasin."""
    planner.shutdown()
    yield
    planner.shutdown()


@pytest.fixture
def inference(monkeypatch, store, timeline):
    events = []

    class Server:
        def __init__(self, *a, **kw):
            events.append("init")
            self.proc = None

        def __enter__(self):
            events.append("enter")
            self.proc = Mock(**{"poll.return_value": None})
            return "http://127.0.0.1:12345"

        def __exit__(self, *a):
            events.append("exit")
            self.proc = None

    monkeypatch.setattr(planner, "LlamaServer", Server)
    monkeypatch.setattr(planner, "find_tool", lambda name: "/local/llama-server")
    monkeypatch.setattr(planner.EditingClient, "close", lambda self: events.append("close"))
    monkeypatch.setattr(planner.EditingClient, "complete_json",
                        lambda self, prompt, schema: '{"commands":[],"unresolved":[]}')
    return events


def test_planning_context_and_cleanup(store, timeline, inference, monkeypatch):
    def complete(self, prompt, schema):
        assert "/private/" not in prompt
        assert prompt.endswith("/no_think")
        assert schema["additionalProperties"] is False
        return '{"commands":[{"tool":"set_color","args":{"preset":"film"}}],"unresolved":[]}'
    monkeypatch.setattr(planner.EditingClient, "complete_json", complete)
    result = planner.plan(PlanIn(prompt="film color", timeline=timeline), store)
    assert result.model_id == "test"
    assert result.plan.commands[0].tool == "set_color"
    # Muvaffaqiyatli so'rovdan keyin server issiq qoladi; shutdown uni yopadi.
    assert "close" in inference and "exit" not in inference and planner.WARM.running
    assert not planner.INFERENCE_LOCK.locked()
    planner.shutdown()
    assert inference[-1] == "exit" and not planner.WARM.running


@pytest.mark.parametrize("raw", ["not json", '{}', '{"unknown":true}',
    '{"schema":"lahza.edit-plan/1","base_revision":"' + "0" * 64 + '","commands":[],"unresolved":[]}'])
def test_malformed_completion(store, timeline, inference, monkeypatch, raw):
    monkeypatch.setattr(planner.EditingClient, "complete_json", lambda *a: raw)
    with pytest.raises(ValueError):
        planner.plan(PlanIn(prompt="change", timeline=timeline), store)
    # Yaroqsiz javob server nosozligi emas: issiq server qoladi.
    assert "close" in inference and "exit" not in inference
    assert not planner.INFERENCE_LOCK.locked()


def test_busy(store, timeline):
    with planner.INFERENCE_LOCK, pytest.raises(planner.Busy):
        planner.plan(PlanIn(prompt="change", timeline=timeline), store)


def test_loopback_enforced(store, timeline, inference, monkeypatch):
    monkeypatch.setattr(planner.LlamaServer, "__enter__", lambda self: "http://example.com")
    with pytest.raises(planner.Unavailable, match="loopback"):
        planner.plan(PlanIn(prompt="change", timeline=timeline), store)
    assert "exit" in inference


@pytest.mark.parametrize("path", ["https://example.com/m.gguf", "/outside/models.gguf"])
def test_managed_models_only(store, path):
    reg = store.load()
    reg.models[0].path = path
    store._save(reg)
    with pytest.raises(planner.Unavailable):
        planner.local_model(store)


def test_api_auth_missing_model_no_asr(tmp_path, timeline, monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("ASR services must not load")
    monkeypatch.setattr(State, "services", forbidden)
    app = create_app(Settings(data_dir=tmp_path), token="test")
    with TestClient(app) as client:
        assert client.get("/v1/editing-agent/status").status_code == 401
        client.headers["Authorization"] = "Bearer test"
        status = client.get("/v1/editing-agent/status")
        assert status.status_code == 200 and status.json()["available"] is False
        assert client.post("/v1/editing-agent:plan", json={"prompt": "color", "timeline": timeline.to_json()}).status_code == 503
        plan = edit(timeline, [command("set_color", preset="warm")])
        body = {"timeline": timeline.to_json(), "plan": plan.model_dump(by_alias=True)}
        assert client.post("/v1/editing-agent:preview", json=body).status_code == 200
        body["selected_video_id"] = "v"
        assert client.post("/v1/editing-agent:preview", json=body).status_code == 409
        body["plan"]["commands"][0]["args"]["evil"] = True
        assert client.post("/v1/editing-agent:preview", json=body).status_code == 422


def test_invalid_existing_fx_and_profile_atomic(timeline):
    from lahza_engine.montage.model import FxRef
    timeline.video[0].fx.append(FxRef(plugin="uz.lahza.speed.freeze", at_ms=0,
                                     params={"dur_ms": 99999}))
    before = timeline.to_json()
    with pytest.raises(ValueError):
        preview(timeline, edit(timeline, []), None)
    assert timeline.to_json() == before
    timeline.video[0].fx.clear()
    timeline.media["m"].duration_ms = 200000
    timeline.video[0].src_out_ms = 200000
    with pytest.raises(ValueError, match="180"):
        preview(timeline, edit(timeline, [command("set_format", profile="youtube_shorts")]), None)
    assert timeline.target_platform == "custom"


def test_preserve_legacy_overlays_words_lut(timeline):
    from lahza_engine.montage.model import FxRef, TextItem
    from lahza_engine.types import Word
    timeline.text.append(TextItem(id="old", text="Legacy", start_ms=9500, end_ms=14000))
    timeline.captions.words.append(Word(text="Legacy", start_ms=10000, end_ms=12000))
    timeline.color = FxRef(plugin="uz.lahza.color.lut", params={"file": "/existing/look.cube"})
    result = preview(timeline, edit(timeline, [command("set_captions", enabled=True)]), None)
    assert result.timeline.to_json()["color"] == timeline.to_json()["color"]
    assert result.timeline.text[0].end_ms == 14000
    assert result.timeline.captions.words[0].end_ms == 12000


def test_freeze_overlap_and_adjacent(timeline):
    first = preview(timeline, edit(timeline, [command("freeze_clip", clip_id="v", at_ms=0,
                                                    duration_ms=500)]), None).timeline
    assert first.video[0].user_edited
    before = first.to_json()
    for at_ms in (0, 100, 499):
        with pytest.raises(ValueError, match="overlap"):
            preview(first, edit(first, [command("freeze_clip", clip_id="v", at_ms=at_ms,
                                              duration_ms=500)]), None)
        assert first.to_json() == before
    adjacent = preview(first, edit(first, [command("freeze_clip", clip_id="v", at_ms=500,
                                                   duration_ms=500)]), None)
    assert len(adjacent.timeline.video[0].fx) == 2


def test_context_budget(timeline):
    import json

    from lahza_engine.types import Word
    timeline.video = [timeline.video[0].model_copy(update={"id": f"clip-{i}"}) for i in range(1000)]
    timeline.captions.words = [Word(text="word" * 100, start_ms=i, end_ms=i + 1) for i in range(1000)]
    context = planner.compact_context(PlanIn(prompt="color", timeline=timeline))
    assert len(json.dumps(context, ensure_ascii=False)) <= planner.CONTEXT_BUDGET
    assert context["omitted_clips"] > 0 and context["omitted_words"] > 0
    assert "/private" not in json.dumps(context)


def test_status_does_not_start_model(store, monkeypatch):
    monkeypatch.setattr(planner, "find_tool", lambda *a: "/local/llama-server")
    monkeypatch.setattr(planner, "LlamaServer", lambda *a, **kw: pytest.fail("status loaded model"))
    assert planner.status(store).available


def test_startup_failure_cleanup(store, timeline, inference, monkeypatch):
    def fail(self):
        raise RuntimeError("not enough memory")
    monkeypatch.setattr(planner.LlamaServer, "__enter__", fail)
    with pytest.raises(planner.Unavailable, match="memory"):
        planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert "exit" in inference
    assert not planner.INFERENCE_LOCK.locked()


def test_completion_timeout_cleanup(store, timeline, inference, monkeypatch):
    import httpx

    def fail(*a):
        raise httpx.ReadTimeout("completion deadline")
    monkeypatch.setattr(planner.EditingClient, "complete_json", fail)
    with pytest.raises(planner.Unavailable, match="deadline"):
        planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert "close" in inference and "exit" in inference
    assert not planner.INFERENCE_LOCK.locked()


@pytest.mark.parametrize("raw", [
    '{"commands":[{"tool":"delete","args":{}}],"unresolved":[]}',
    '{"commands":[{"tool":"set_color","args":{"preset":"warm","path":"x"}}],"unresolved":[]}',
    '{"commands":[{"tool":"add_caption","args":{"text":"x","start_ms":0,"end_ms":10001}}],"unresolved":[]}',
])
def test_invalid_proposal_rejected(store, timeline, inference, monkeypatch, raw):
    before = timeline.to_json()
    monkeypatch.setattr(planner.EditingClient, "complete_json", lambda *a: raw)
    with pytest.raises(ValueError):
        planner.plan(PlanIn(prompt="edit", timeline=timeline), store)
    assert timeline.to_json() == before


def test_valid_refusal(store, timeline, inference, monkeypatch):
    monkeypatch.setattr(planner.EditingClient, "complete_json",
                        lambda *a: '{"commands":[],"unresolved":["Splitting is unsupported"]}')
    result = planner.plan(PlanIn(prompt="split", timeline=timeline), store)
    assert result.plan.base_revision == revision(timeline, None)
    assert result.changes == []
    with pytest.raises(ValueError, match="Unresolved"):
        preview(timeline, result.plan, None)


def test_client_request_limits(monkeypatch):
    import httpx

    captured = {}
    def respond(request):
        import json
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content":
                              '{"commands":[],"unresolved":[]}'}, "finish_reason": "stop"}]})
    client = planner.EditingClient("http://127.0.0.1:12345", "test", timeout_s=90)
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(respond), trust_env=False)
    try:
        client.complete_json("edit /no_think", {})
    finally:
        client.close()
    assert captured["max_tokens"] == 2048
    assert captured["cache_prompt"] is True
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_real_ass_format_caption_integration(timeline):
    from lahza_engine.render.montage_render import _ass_doc
    from lahza_engine.types import Word
    timeline.captions.words = [Word(text="Dunyo", start_ms=100, end_ms=900)]
    result = preview(timeline, edit(timeline, [command("set_format", profile="youtube_video"),
        command("set_captions", enabled=True, font_size=80),
        command("add_caption", text="Salom", start_ms=0, end_ms=1000)]), None)
    ass = _ass_doc(result.timeline, Settings())
    assert "PlayResX: 1920" in ass and "PlayResY: 1080" in ass
    assert "Salom" in ass and "Dunyo" in ass
    assert "Inter,80," in ass


def test_custom_safe_zone_settings(timeline):
    from lahza_engine.config import SubtitleSafeZone
    from lahza_engine.montage.model import StickerItem
    timeline.stickers.append(StickerItem(id="s", path="/existing/sticker.png", start_ms=0,
                                         end_ms=1000, x=.2, y=.5, width=.1, height=.1))
    settings = Settings(safe_zone=SubtitleSafeZone(side_pct=.3))
    result = preview(timeline, edit(timeline, []), None, settings)
    assert any("safe guide" in warning for warning in result.warnings)
    assert not any("safe guide" in warning for warning in preview(timeline, edit(timeline, []), None).warnings)


def test_render_edited_caption_frame(timeline, tmp_path):
    import json
    import subprocess

    from conftest import HAS_FFMPEG, ffmpeg_filters

    from lahza_engine.render.montage_render import render_montage_frame
    if not HAS_FFMPEG or "ass" not in ffmpeg_filters():
        pytest.skip("ffmpeg with libass required")
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=s=320x180:r=30:d=1", "-c:v", "mpeg4", str(source)], check=True)
    timeline.media["m"].path = str(source)
    timeline.media["m"].duration_ms = 1000
    timeline.media["m"].has_audio = False
    timeline.media["m"].width = 320
    timeline.media["m"].height = 180
    timeline.video[0].src_out_ms = 1000
    timeline.video[0].reframe = "center"
    result = preview(timeline, edit(timeline, [command("set_format", profile="youtube_video"),
        command("add_caption", text="Salom", start_ms=0, end_ms=1000)]), None)
    image = render_montage_frame(result.timeline, 500, tmp_path / "frame.jpg", Settings())
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                            "-of", "json", str(image)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)["streams"][0]
    assert (stream["width"], stream["height"]) == (1920, 1080)


def test_relative_edit_context_timing_and_no_paths(timeline):
    import json

    from lahza_engine.montage.model import FxRef, TransitionRef
    timeline.captions.enabled = True
    timeline.captions.style.font_size = 96
    timeline.captions.style.position = "upper"
    timeline.captions.style.logo_path = "/private/style-logo.png"
    timeline.brand.logo_path = "/private/brand-logo.png"
    timeline.color = FxRef(plugin="uz.lahza.color.warm")
    timeline.video[0].speed = 2
    timeline.video[0].fx = [FxRef(plugin="uz.lahza.speed.freeze", at_ms=500,
                                 params={"dur_ms": 700}),
                           FxRef(plugin="uz.lahza.color.lut", at_ms=1000, dur_ms=1000,
                                 params={"file": "/private/look.cube"})]
    second = timeline.video[0].model_copy(deep=True)
    second.id = "second"
    second.fx = []
    second.transition_in = TransitionRef(plugin="uz.lahza.tr.dissolve", dur_ms=400)
    timeline.video.append(second)
    body = PlanIn(prompt="captionni kattaroq qil", timeline=timeline, selected_video_id="second")
    before = timeline.to_json()
    context = planner.compact_context(body)
    assert context["captions"]["enabled"] is True
    assert context["captions"]["font_size"] == 96
    assert context["captions"]["position"] == "upper"
    assert context["color_preset"] == "warm"
    assert context["clips"][0]["id"] == "second"
    assert context["clips"][0]["start_ms"] == 4600
    assert context["clips"][0]["transition_in"]["dur_ms"] == 400
    first = context["clips"][1]
    assert (first["start_ms"], first["duration_ms"], first["speed"]) == (0, 5000, 2)
    assert first["effects"][0] == {"plugin": "uz.lahza.speed.freeze", "at_ms": 500, "dur_ms": 700}
    encoded = json.dumps(context, ensure_ascii=False)
    assert "/private" not in encoded and "params" not in encoded
    assert "src_in_ms" not in encoded and "src_out_ms" not in encoded
    assert len(encoded) <= planner.CONTEXT_BUDGET
    assert timeline.to_json() == before
    timeline.color = FxRef(plugin="uz.lahza.color.lut", params={"file": "/private/global.cube"})
    assert planner.compact_context(body)["color_preset"] is None


def test_context_bounds_effect_summaries_and_prioritizes_selection(timeline):
    import json

    from lahza_engine.montage.model import FxRef
    timeline.video = [timeline.video[0].model_copy(deep=True, update={"id": f"clip-{i}"})
                      for i in range(1000)]
    timeline.video[-1].fx = [FxRef(plugin="uz.lahza.speed.freeze", at_ms=i, dur_ms=100)
                             for i in range(1000)]
    context = planner.compact_context(PlanIn(prompt="freeze", timeline=timeline,
                                            selected_video_id="clip-999"))
    selected = context["clips"][0]
    assert selected["id"] == "clip-999" and selected["start_ms"] == 9990000
    assert len(selected["effects"]) == 16 and selected["omitted_effects"] == 984
    assert context["omitted_clips"] > 0
    assert len(json.dumps(context, ensure_ascii=False)) <= planner.CONTEXT_BUDGET


@pytest.mark.parametrize("profile", ["youtube_video", "youtube_shorts", "instagram_reels"])
def test_format_preset_preserves_96k_audio(timeline, profile):
    timeline.format.audio_hz = 96000
    timeline.format.fps = 60
    before = timeline.to_json()
    result = preview(timeline, edit(timeline, [command("set_format", profile=profile)]), None)
    assert result.timeline.format.audio_hz == 96000
    assert result.timeline.format.fps == 30
    assert result.timeline.target_platform == profile
    assert (result.timeline.format.w, result.timeline.format.h) == (
        (1920, 1080) if profile == "youtube_video" else (1080, 1920))
    assert timeline.to_json() == before


@pytest.mark.parametrize("tool,first,second", [
    ("set_format", {"profile": "instagram_reels"}, {"profile": "youtube_video"}),
    ("set_captions", {"enabled": False}, {"enabled": True, "font_size": 80}),
    ("set_color", {"preset": "warm"}, {"preset": "vivid"}),
])
def test_duplicate_and_conflicting_singleton_commands_atomic(timeline, tool, first, second):
    from lahza_engine.editing_agent.model import Proposal
    before = timeline.to_json()
    for final_args in (first, second):
        commands = [command(tool, **first), command(tool, **final_args)]
        with pytest.raises(ValueError, match="Ambiguous editing output"):
            Proposal.model_validate({"commands": commands, "unresolved": []})
        # Exercise the executor guard even if an internal caller bypasses validation.
        valid = edit(timeline, [commands[0]])
        other = edit(timeline, [commands[1]])
        invalid = valid.model_copy(update={"commands": [*valid.commands, *other.commands]})
        with pytest.raises(ValueError, match="Ambiguous editing output"):
            preview(timeline, invalid, None)
        assert timeline.to_json() == before


def test_ambiguous_model_completion_rejected(store, timeline, inference, monkeypatch):
    raw = ('{"commands":[{"tool":"set_captions","args":{"enabled":false}},'
           '{"tool":"set_captions","args":{"enabled":true,"font_size":80}}],"unresolved":[]}')
    monkeypatch.setattr(planner.EditingClient, "complete_json", lambda *a: raw)
    before = timeline.to_json()
    with pytest.raises(ValueError, match="Ambiguous editing output"):
        planner.plan(PlanIn(prompt="Subtitrlarni yoqib, shriftini 80 px qil.", timeline=timeline), store)
    assert timeline.to_json() == before
    assert not planner.INFERENCE_LOCK.locked()


def test_visible_tool_reference_and_strict_json_examples(timeline):
    import json

    from lahza_engine.editing_agent.model import Proposal
    from lahza_engine.editing_agent.prompts import EXAMPLES, SYSTEM_PROMPT, build_prompt
    for pair in ("warm = iliq", "cool = sovuq", "vivid = yorqin", "film = kino", "bw = oq-qora"):
        assert pair in SYSTEM_PROMPT
    assert "o'chir/o‘chir = false" in SYSTEM_PROMPT
    assert "yoq/yoqib = enabled true" in SYSTEM_PROMPT
    assert "yoq/yoqib is the imperative TURN ON (enabled true)" in SYSTEM_PROMPT
    assert "yo‘q/yo'q/yoʻq, meaning no/none" in SYSTEM_PROMPT
    assert "absolute integer pixels 24..200" in SYSTEM_PROMPT
    assert "AT MOST ONE" in SYSTEM_PROMPT
    assert "{clip_id,at_ms,duration_ms}" in SYSTEM_PROMPT
    assert "{enabled,font_size}" in SYSTEM_PROMPT
    schema = Proposal.model_json_schema()
    assert "iliq/iliqroq" in schema["$defs"]["ColorArgs"]["properties"]["preset"]["description"]
    request = "Ranglarni iliqroq qil. Boshqa qismlarni o'zgartirma."
    context = planner.compact_context(PlanIn(prompt=request, timeline=timeline))
    prompt = build_prompt(request, context)
    actual = prompt.split("Actual request and context:\n", 1)[1].removesuffix("\n/no_think")
    assert json.loads(actual) == {"request": request, "context": context}
    assert len(SYSTEM_PROMPT) + len(build_prompt("", {})) < 10000
    for example in EXAMPLES:
        payload = example["output"]
        assert set(payload) == {"commands", "unresolved"}
        Proposal.model_validate_json(json.dumps(payload))
        assert json.dumps(example, ensure_ascii=False) in prompt
    warm = EXAMPLES[0]["output"]["commands"]
    assert warm == [command("set_color", preset="warm")]


def test_client_exposes_system_semantics_to_model(monkeypatch):
    import json

    import httpx

    from lahza_engine.editing_agent.prompts import SYSTEM_PROMPT
    captured = {}
    def respond(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {
            "content": '{"commands":[],"unresolved":[]}'}, "finish_reason": "stop"}]})
    client = planner.EditingClient("http://127.0.0.1:12345", "test")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(respond))
    try:
        client.complete_json("user request /no_think", {})
    finally:
        client.close()
    assert captured["messages"] == [{"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": "user request /no_think"}]


def test_highlight_shared_llm_slot_maps_to_editing_409(tmp_path, store, timeline, inference, monkeypatch):
    from lahza_engine.core import llama_server
    app = create_app(Settings(data_dir=tmp_path / "api"), token="test")
    app.state.lahza.store = store
    # Use the actual shared lifecycle and lock, without starting a real process.
    monkeypatch.setattr(planner, "LlamaServer", llama_server.LlamaServer)
    before = timeline.to_json()
    with llama_server._LLM_LOCK, TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test"
        response = client.post("/v1/editing-agent:plan", json={"prompt": "color",
                                                             "timeline": timeline.to_json()})
        assert response.status_code == 409
        assert "busy" in response.json()["detail"] and "retry" in response.json()["detail"]
        assert llama_server._LLM_LOCK.locked()
    assert timeline.to_json() == before
    assert not planner.INFERENCE_LOCK.locked()


def test_warm_server_reused_between_plans(store, timeline, inference):
    for _ in range(3):
        planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert inference.count("init") == 1 and inference.count("enter") == 1
    assert inference.count("close") == 3 and "exit" not in inference


def test_warm_server_restarts_after_death_and_model_change(store, timeline, inference, monkeypatch):
    servers = []
    original = planner.LlamaServer

    def factory(*a, **kw):
        servers.append(original(*a, **kw))
        return servers[-1]
    monkeypatch.setattr(planner, "LlamaServer", factory)
    planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    servers[0].proc.poll.return_value = 1  # jarayon o'z-o'zidan o'ldi
    planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert len(servers) == 2 and inference.count("exit") == 1
    _, path = planner.local_model(store)
    path.write_bytes(b"GGUFtest-new-model")  # hajm/mtime o'zgardi
    planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert len(servers) == 3 and inference.count("exit") == 2
    assert planner.WARM.running


def test_warm_server_discarded_after_inference_error(store, timeline, inference, monkeypatch):
    import httpx

    def fail(*a):
        raise httpx.ConnectError("server died mid-request")
    monkeypatch.setattr(planner.EditingClient, "complete_json", fail)
    with pytest.raises(planner.Unavailable):
        planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert inference[-1] == "exit" and not planner.WARM.running


def test_engine_shutdown_stops_warm_server(tmp_path, store, timeline, inference):
    app = create_app(Settings(data_dir=tmp_path / "api"), token="test")
    app.state.lahza.store = store
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test"
        response = client.post("/v1/editing-agent:plan", json={"prompt": "color",
                                                             "timeline": timeline.to_json()})
        assert response.status_code == 200
        assert planner.WARM.running and "exit" not in inference
    assert inference[-1] == "exit" and not planner.WARM.running


def test_idle_timeout_env(store, timeline, inference, monkeypatch):
    monkeypatch.setenv("LAHZA_LLM_IDLE_S", "0")  # 0 - issiq server o'chiq, avvalgi xatti-harakat
    planner.plan(PlanIn(prompt="color", timeline=timeline), store)
    assert inference[-1] == "exit" and not planner.WARM.running


def test_prompt_cache_prefix_is_byte_identical(timeline):
    from lahza_engine.editing_agent.prompts import build_prompt
    first = build_prompt("Ranglarni iliqroq qil", planner.compact_context(
        PlanIn(prompt="x", timeline=timeline)))
    timeline.captions.enabled = not timeline.captions.enabled
    second = build_prompt("Subtitrlarni o'chir", planner.compact_context(
        PlanIn(prompt="y", timeline=timeline)))
    marker = "\nActual request and context:\n"
    prefix = first[:first.index(marker) + len(marker)]
    # O'zgaruvchan qism (so'rov, kontekst) faqat keshlanadigan prefiksdan keyin keladi.
    assert second.startswith(prefix) and first != second
    assert build_prompt("Subtitrlarni o'chir", planner.compact_context(
        PlanIn(prompt="y", timeline=timeline))) == second  # deterministik, nonce yo'q
    assert prefix.count("{") > 10  # misollar prefiks ichida
    # Tartib ataylab "request, context": "context, request" tezroq (timeline ham keshlanadi), lekin
    # o'lchovda qo'shma buyruqda freeze_clip'ni har safar tushirib qoldirdi (8/10 vs 10/10).
