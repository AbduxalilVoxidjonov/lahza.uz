"""Bounded local llama.cpp inference. Status never starts or downloads a model."""
import json
import logging
import threading
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from lahza_engine.config import Settings
from lahza_engine.core.llama_server import LlamaServer, LlamaServerBusy, WarmLlamaServer
from lahza_engine.editing_agent.executor import preview, revision, validate_timeline
from lahza_engine.editing_agent.model import OPERATIONS, EditPlan, PlanIn, PlanOut, Proposal, Status
from lahza_engine.editing_agent.prompts import SYSTEM_PROMPT, build_prompt
from lahza_engine.fx.registry import COLOR_PRESETS, get_plugin
from lahza_engine.highlight.llm import LlamaServerClient
from lahza_engine.media.tools import find_tool
from lahza_engine.models.catalog import Task
from lahza_engine.models.store import ModelStore, sniff_custom_file

log = logging.getLogger(__name__)

INFERENCE_LOCK = threading.Lock()
CONTEXT_BUDGET = 12_000
# Eng yomon holat ~10k token: system+misollar ~1.9k, kontekst <= CONTEXT_BUDGET belgi (~5k),
# so'rov <= 2000 belgi, javob <= 2048. 16k issiq serverda 16 GB'li noutbukda RAM yetmay qolardi
# (o'lchov: 12k - 5.8 GB cho'qqi). q8_0 KV 0.8 GB tejaydi, lekin CPU'da prompt 1.5x sekin - kerak emas.
CTX_SIZE = 12288
# Prefiksni qayta ishlatishga bitta slotning o'z KV keshi yetadi; llama.cpp standarti (RAM'da
# 8 GiB gacha qo'shimcha prompt keshi) uzoq issiq turadigan server uchun ortiqcha.
CACHE_RAM_MIB = 256
# Issiq server: yuklash (~5 s) va system prompt + misollar KV keshi so'rovlar orasida saqlanadi.
WARM = WarmLlamaServer()


class Unavailable(RuntimeError):
    pass


class Busy(RuntimeError):
    pass


def local_model(store: ModelStore) -> tuple[str, Path]:
    model = store.default_for(Task.LLM)
    if model is None or model.task != Task.LLM:
        raise Unavailable("No default local LLM installed; install and select a managed GGUF model")
    if "://" in model.path:
        raise Unavailable("Only local managed GGUF models are supported; remote URLs are forbidden")
    path = Path(model.path).resolve()
    if not path.is_relative_to(store.root.resolve()):
        raise Unavailable("LLM must be inside the managed models directory")
    if path.is_dir():
        candidates = sorted(path.rglob("*.gguf"))
        if len(candidates) != 1:
            raise Unavailable("Managed LLM directory must contain exactly one GGUF file")
        path = candidates[0].resolve()
    if (not path.is_relative_to(store.root.resolve()) or not path.is_file()
            or path.suffix.lower() != ".gguf" or sniff_custom_file(path) != "gguf"):
        raise Unavailable("Default LLM is not a valid local managed GGUF file")
    return model.id, path


def status(store: ModelStore) -> Status:
    model_id = None
    try:
        model_id, _ = local_model(store)
        find_tool("llama-server")
    except (Unavailable, ValueError, OSError, RuntimeError) as exc:
        return Status(available=False, reason=str(exc), model_id=model_id,
                      supported_operations=OPERATIONS)
    return Status(available=True, reason=None, model_id=model_id, supported_operations=OPERATIONS)


def compact_context(body: PlanIn) -> dict:
    tl = body.timeline
    colors = {f"uz.lahza.color.{preset}": preset for preset in COLOR_PRESETS}
    context = {"selected_video_id": body.selected_video_id, "duration_ms": tl.duration_ms,
               "target_platform": tl.target_platform, "format": tl.format.model_dump(),
               "captions": {"enabled": tl.captions.enabled, "font_size": tl.captions.style.font_size,
                            "position": tl.captions.style.position,
                            "bold": tl.captions.style.bold, "animation": tl.captions.style.animation,
                            "max_words": tl.captions.style.max_words,
                            "max_lines": tl.captions.style.max_lines},
               "color_preset": colors.get(tl.color.plugin) if tl.color else None,
               "clips": [], "words": [], "omitted_clips": 0, "omitted_words": 0}
    # Only explicit allowlisted values: no media paths, origins, brand paths or provenance.
    clips = zip(tl.video, tl.item_starts(), strict=True)
    for clip, start_ms in sorted(clips, key=lambda pair: pair[0].id != body.selected_video_id):
        effects = []
        for ref in clip.fx[:16]:
            manifest = get_plugin(ref.plugin)
            duration_ms = ref.dur_ms
            if duration_ms is None:
                duration_ms = (ref.params.get("dur_ms", 800) if manifest.backend == "speed"
                               else clip.out_duration_ms - ref.at_ms)
            effects.append({"plugin": manifest.id, "at_ms": ref.at_ms, "dur_ms": duration_ms})
        transition = clip.transition_in
        item = {"id": clip.id, "start_ms": start_ms, "duration_ms": clip.out_duration_ms,
                "speed": clip.speed, "effects": effects,
                "omitted_effects": max(0, len(clip.fx) - len(effects)),
                "transition_in": ({"plugin": get_plugin(transition.plugin).id,
                                   "dur_ms": transition.dur_ms} if transition else None)}
        context["clips"].append(item)
        if len(json.dumps(context, ensure_ascii=False)) > CONTEXT_BUDGET - 1000:
            context["clips"].pop()
            break
    context["omitted_clips"] = len(tl.video) - len(context["clips"])
    for word in tl.captions.words[:200]:
        item = {"text": word.text[:80], "start_ms": word.start_ms, "end_ms": word.end_ms}
        context["words"].append(item)
        if len(json.dumps(context, ensure_ascii=False)) > CONTEXT_BUDGET - 100:
            context["words"].pop()
            break
    context["omitted_words"] = len(tl.captions.words) - len(context["words"])
    if len(json.dumps(context, ensure_ascii=False)) > CONTEXT_BUDGET:
        raise ValueError("Timeline identifiers exceed the context budget")
    return context


class EditingClient(LlamaServerClient):
    """Keep the shared client unchanged while bounding editing output and thinking."""

    def __init__(self, base_url: str, model_id: str, timeout_s: float = 90) -> None:
        super().__init__(base_url, model_id, timeout_s)
        self._http.close()
        # A configured outbound proxy must never receive local inference traffic.
        self._http = httpx.Client(timeout=httpx.Timeout(timeout_s, connect=5), trust_env=False,
                                  follow_redirects=False)
        self.last_timings: dict = {}

    def complete_json(self, prompt: str, schema: dict, temperature: float = 0.2) -> str:
        # Prefiks (system prompt + misollar) har so'rovda bayt-bayt bir xil va birinchi turadi:
        # `cache_prompt` bilan issiq server faqat o'zgaruvchan qismni (kontekst, so'rov) hisoblaydi.
        response = self._http.post(f"{self.base_url}/v1/chat/completions", json={
            "model": self.model_id, "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                                  {"role": "user", "content": prompt}],
            "temperature": temperature, "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": False},
            "cache_prompt": True,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "edit_plan", "schema": schema, "strict": True}},
        })
        response.raise_for_status()
        data = response.json()
        timings = data.get("timings") if isinstance(data, dict) else None
        self.last_timings = timings if isinstance(timings, dict) else {}
        log.info("Montaj LLM: prompt=%s tok (keshdan %s), %.0f ms; chiqish=%s tok, %.0f ms",
                 self.last_timings.get("prompt_n"), self.last_timings.get("cache_n"),
                 self.last_timings.get("prompt_ms") or 0.0, self.last_timings.get("predicted_n"),
                 self.last_timings.get("predicted_ms") or 0.0)
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Local LLM output exceeded the token budget; request a smaller edit")
        message = choice["message"]
        if message.get("refusal"):
            raise ValueError("Local LLM refused this request")
        return message["content"]


def shutdown() -> None:
    """Issiq serverni yopish (engine to'xtashida `stop_warm_servers` ham shuni qiladi)."""
    WARM.stop()


def plan(body: PlanIn, store: ModelStore, settings: Settings | None = None) -> PlanOut:
    if not body.prompt.strip():
        raise ValueError("Prompt must not be blank")
    validate_timeline(body.timeline, body.selected_video_id, settings)
    if not INFERENCE_LOCK.acquire(blocking=False):
        raise Busy("Editing inference is busy; retry after the current request completes")
    try:
        model_id, path = local_model(store)
        try:
            find_tool("llama-server")
        except (OSError, RuntimeError) as exc:
            raise Unavailable("Local llama-server runtime unavailable: " + str(exc)) from exc
        context = compact_context(body)
        prompt = build_prompt(body.prompt, context)
        stat = path.stat()
        # Model fayli almashsa (yo'l, hajm yoki mtime) issiq server qayta ishga tushadi.
        key = (str(path), stat.st_size, stat.st_mtime_ns, CTX_SIZE)
        try:
            # Ishga tushish xatosida (qisman start ham) lease serverni o'zi yopadi.
            with WARM.lease(key, lambda: LlamaServer(path, ctx_size=CTX_SIZE, startup_timeout_s=90,
                                                     cache_ram_mib=CACHE_RAM_MIB)) as url:
                parsed = urlsplit(url)
                if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
                    raise Unavailable("Inference endpoint must be HTTP IPv4 loopback")
                client = EditingClient(url, model_id, timeout_s=90)
                try:
                    raw = client.complete_json(prompt, Proposal.model_json_schema(by_alias=True))
                finally:
                    client.close()
        except LlamaServerBusy as exc:
            raise Busy(str(exc)) from exc
        except (httpx.HTTPError, OSError, TimeoutError, RuntimeError) as exc:
            raise Unavailable("Local LLM inference unavailable: " + str(exc)) from exc
        if not isinstance(raw, str) or len(raw) > 32_000:
            raise ValueError("Local LLM returned invalid or oversized JSON")
        proposal = Proposal.model_validate_json(raw)
        result = EditPlan(schema="lahza.edit-plan/1",
                          base_revision=revision(body.timeline, body.selected_video_id),
                          commands=proposal.commands, unresolved=proposal.unresolved)
        if result.unresolved:
            if result.commands:
                raise ValueError("Refused/unresolved plans must not contain commands")
            return PlanOut(plan=result, changes=[], warnings=result.unresolved, model_id=model_id)
        draft = preview(body.timeline, result, body.selected_video_id, settings)
        return PlanOut(plan=result, changes=draft.changes, warnings=draft.warnings, model_id=model_id)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed local LLM response") from exc
    finally:
        INFERENCE_LOCK.release()
