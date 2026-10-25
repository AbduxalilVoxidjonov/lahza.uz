"""Raw beginner API -> offline ASR -> saved caption words, without project import."""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import pytest
from _api_helpers import make_client, wait_job
from conftest import requires_ffmpeg

from lahza_engine.core.runner import Cancelled
from lahza_engine.core.services import Services
from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel
from lahza_engine.montage import analyze as analysis
from lahza_engine.montage import raw_asr
from lahza_engine.montage.analyze import Shot, SourceAnalysis
from lahza_engine.montage.model import MediaRef, MontageTimeline
from lahza_engine.subtitle.ass import build_srt
from lahza_engine.timeline import Timeline
from lahza_engine.types import Word

REAL_ANALYZE_FILE = analysis.analyze_file


class FakeAsr:
    def __init__(self, model_id):
        self.model_id = model_id
        self.calls = []
        self.cancel = None

    def transcribe_chunk(self, wav, offset_ms, opts):
        assert Path(wav).is_file() and opts.language == "uz"
        self.calls.append(offset_ms)
        if self.cancel is not None:
            self.cancel.set()
        return [Word(text="Salom", start_ms=offset_ms + 300, end_ms=offset_ms + 600),
                Word(text="dunyo.", start_ms=offset_ms + 700, end_ms=offset_ms + 1000)]


@pytest.fixture
def raw_case(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)
    path = tmp_path / "raw.mp4"
    path.write_bytes(b"raw source fixture")
    model_path = state.store.root / "asr-model"
    model_path.write_bytes(b"model")
    model = InstalledModel(id="fake:asr", task=Task.ASR, version="1", path=str(model_path))
    state.store.register([model])
    backend = FakeAsr(model.id)
    state._services = Services(asr=backend, asr_model_id=model.id,
                               vad=lambda pcm, rate: [(0, 6000)])

    def visual(path, media_id, cache_dir, settings, **kwargs):
        return SourceAnalysis(media=MediaRef(id=media_id, path=str(path), duration_ms=6000,
                                            width=160, height=120, fps=10),
                              shots=[Shot(0, 6000)], speech=[(0, 6000)])

    monkeypatch.setattr(analysis, "analyze_file", visual)
    # Real chunking and ASR are exercised; fast unit fixture substitutes only audio I/O.
    def extract(src, dest):
        from _api_helpers import write_wav
        write_wav(dest, 6000)
        return dest

    monkeypatch.setattr(raw_asr, "extract_wav", extract)
    return client, state, backend, path, visual


def create(client, state, path, template="uz.lahza.tpl.course-announce"):
    response = client.post("/v1/montages", json={"template_id": template,
                           "sources": [{"kind": "file", "path": str(path)}],
                           "overrides": {"target_duration_ms": 6000}})
    assert response.status_code == 200, response.text
    body = response.json()
    job = wait_job(state, body["job"]["id"])
    assert job.status == "done", job.error
    detail = client.get(f'/v1/montages/{body["montage_id"]}').json()
    return body["montage_id"], detail, MontageTimeline.model_validate(detail["timeline"])


@requires_ffmpeg
@pytest.mark.parametrize("template,enabled", [("uz.lahza.tpl.course-announce", True),
                                              ("uz.lahza.tpl.daily-story", False)])
def test_raw_api_caption_words_persist_without_import(raw_case, template, enabled):
    client, state, backend, path, _ = raw_case
    with client:
        mid, detail, timeline = create(client, state, path, template)
        assert timeline.captions.enabled is enabled
        assert [w.text for w in timeline.captions.words] == ["Salom", "dunyo."]
        assert len(backend.calls) == 1
        stored = json.loads(state.lib("SELECT timeline_json FROM montages WHERE id=?", (mid,))[0][0])
        assert stored["captions"]["words"]
        assert not state.lib("SELECT * FROM episodes")
        # Turning captions on later preserves the already mapped real ASR words.
        timeline.captions.enabled = True
        assert "Salom dunyo." in build_srt(timeline.captions.words, Timeline(0, timeline.duration_ms))
        assert not any("transkript yo'q" in warning for warning in timeline.provenance.notes)


@requires_ffmpeg
def test_shared_cache_reused_but_not_for_another_model(raw_case):
    client, state, backend, path, _ = raw_case
    with client:
        create(client, state, path)
        create(client, state, path)
        assert len(backend.calls) == 1
        second = InstalledModel(id="fake:other", task=Task.ASR, version="2",
                                path=state.store.default_for(Task.ASR).path)
        state.store.register([second])
        state.store.set_default(Task.ASR, second.id)
        other = FakeAsr(second.id)
        state._services = Services(asr=other, asr_model_id=second.id, vad=lambda p, r: [(0, 6000)])
        create(client, state, path)
        assert len(other.calls) == 1
        assert len(list((state.settings.data_dir / "Cache/raw-asr").glob("*.json"))) == 2


def test_no_asr_keeps_raw_editing_and_existing_caption_warning(raw_case):
    client, state, backend, path, _ = raw_case
    state.store.remove("fake:asr")
    with client:
        _, _, timeline = create(client, state, path)
        assert not timeline.captions.words and not backend.calls
        assert any("transkript yo'q" in warning for warning in timeline.provenance.notes)


def test_audio_less_skips_services_and_extraction(raw_case, monkeypatch):
    client, state, backend, path, visual = raw_case

    def silent(*args, **kwargs):
        source = visual(*args, **kwargs)
        source.media.has_audio = False
        return source

    monkeypatch.setattr(analysis, "analyze_file", silent)
    monkeypatch.setattr(state, "services", lambda: pytest.fail("services for silent video"))
    monkeypatch.setattr(raw_asr, "extract_wav", lambda *a: pytest.fail("silent extraction"))
    with client:
        _, _, timeline = create(client, state, path)
        assert not timeline.captions.words and not backend.calls


@requires_ffmpeg
def test_cancel_after_inference_does_not_publish_transcript(raw_case):
    client, state, backend, path, _ = raw_case
    cancellation = threading.Event()
    backend.cancel = cancellation
    source = SourceAnalysis(media=MediaRef(id="raw", path=str(path), duration_ms=6000,
                                          width=160, height=120, fps=10))
    with pytest.raises(Cancelled):
        raw_asr.transcribe_source(source, state.store, state.services,
                                 state.settings.data_dir / "Cache/raw-asr", cancellation)
    assert not source.sentences
    assert not list((state.settings.data_dir / "Cache/raw-asr").glob("*.json"))
    state.jobs.shutdown()


@requires_ffmpeg
def test_real_video_api_extraction_with_fake_asr(raw_case, tmp_path, monkeypatch):
    client, state, backend, _, _ = raw_case
    from lahza_engine.media.probe import extract_wav
    monkeypatch.setattr(raw_asr, "extract_wav", extract_wav)
    # Restore real visual analysis as well: this exercises the complete raw-file API path.
    monkeypatch.setattr(analysis, "analyze_file", REAL_ANALYZE_FILE)
    video = tmp_path / "real.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=160x120:rate=10:duration=6", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=16000:duration=6", "-c:v", "mpeg4",
                    "-c:a", "aac", "-shortest", str(video)], check=True, capture_output=True, timeout=30)
    with client:
        _, _, timeline = create(client, state, video)
        assert backend.calls and timeline.captions.words
        from lahza_engine.config import Settings
        from lahza_engine.montage.model import Format
        from lahza_engine.render import montage_render as render
        from lahza_engine.render.encoders import EncoderChoice

        timeline.format = Format(aspect="16:9", w=160, h=90, fps=10)
        timeline.text = []  # isolate subtitle visibility from unrelated template overlays
        timeline.captions.enabled = False
        compose = render.build_compose_graph
        modes = []

        def record_graph(*args, **kwargs):
            modes.append(kwargs["ass"])
            return compose(*args, **kwargs)

        monkeypatch.setattr(render, "build_compose_graph", record_graph)
        encoder = EncoderChoice("mpeg4", ("-c:v", "mpeg4", "-q:v", "5"), False)
        disabled = render.render_montage(timeline, tmp_path / "off.mp4", tmp_path / "off-work",
                                         encoder, Settings())
        assert disabled.video.is_file() and disabled.srt is None
        assert not (tmp_path / "off.srt").exists() and modes == [False]
        assert json.loads(disabled.edl.read_text())["render"]["text_drawn"] is False
        timeline.captions.enabled = True
        enabled = render.render_montage(timeline, tmp_path / "on.mp4", tmp_path / "on-work",
                                        encoder, Settings(), allow_no_subs=True)
        assert enabled.srt is not None and "Salom dunyo." in enabled.srt.read_text()


@requires_ffmpeg
def test_api_cancel_during_raw_inference(raw_case, monkeypatch):
    client, state, backend, path, _ = raw_case
    entered, release = threading.Event(), threading.Event()
    original = backend.transcribe_chunk

    def blocking(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(backend, "transcribe_chunk", blocking)
    with client:
        response = client.post("/v1/montages", json={"template_id": "uz.lahza.tpl.course-announce",
                               "sources": [{"kind": "file", "path": str(path)}]})
        body = response.json()
        try:
            assert entered.wait(5)
            client.post(f'/v1/jobs/{body["job"]["id"]}:cancel')
        finally:
            release.set()
        assert wait_job(state, body["job"]["id"]).status == "cancelled"
        row = state.lib("SELECT timeline_json FROM montages WHERE id=?", (body["montage_id"],))[0]
        assert not row[0]
        assert not list((state.settings.data_dir / "Cache/raw-asr").glob("*.json"))
