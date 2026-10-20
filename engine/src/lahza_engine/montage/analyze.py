"""Montaj manbasini tahlil qilish (docs/11 6.2): kadrlar (shot), sifat, harakat, ovoz energiyasi, nutq.

Natija - `SourceAnalysis`: rejalashtiruvchi (`montage/planner.py`) faqat shu ma'lumot bilan ishlaydi,
o'zi fayl o'qimaydi. Hisoblash arzon va oflayn: FFmpeg (`scdet`, kichik kadrlar, 16 kHz WAV) + numpy.

* keskinlik - kichik kulrang kadrda laplasian dispersiyasi (xira kadr - past);
* harakat - ketma-ket kadrlar farqi (o'rtacha absolyut, 0..1);
* energiya - audio RMS (dBFS -> 0..1);
* nutq - energiya VAD (zaxira; Silero ixtiyoriy, bu yerda shart emas).

Ballar boshlang'ich muhandislik qiymatlari (R0/UzMontaj-Eval'da sozlanadi). Yuz soni hozircha 0
(detektor ixtiyoriy - keyingi bosqich).

Natija `cache_dir/analysis-<xesh>.json` da keshlanadi (fayl xeshi + tahlil versiyasi bo'yicha).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from lahza_engine.config import Settings
from lahza_engine.media.probe import MediaError, _fps, fast_hash
from lahza_engine.media.tools import find_tool, run
from lahza_engine.montage.model import MediaRef
from lahza_engine.types import Sentence

ANALYSIS_VERSION = 1
"""Tahlil algoritmi o'zgarsa oshiriladi (eski kesh yaroqsiz bo'ladi)."""

CURVE_STEP_MS = 500
"""Faollik egri chizig'i qadami (2 fps kadr tahliliga mos)."""
ANALYSIS_FPS = 2.0
ANALYSIS_WIDTH = 320
MIN_SHOT_MS = 200
"""Bundan qisqa shot (chaqnash) qo'shnisiga qo'shiladi."""


class AnalysisCancelled(RuntimeError):
    """Tahlil foydalanuvchi tomonidan bekor qilindi."""


@dataclass
class Shot:
    """Bitta kadr (kamera kesimlari orasidagi bo'lak), manba vaqtida."""

    start_ms: int
    end_ms: int
    score: float = 0.5  # umumiy sifat/qiziqarlilik 0..1 (yomon sifat - past)
    sharpness: float = 0.0  # 0..1
    motion: float = 0.0  # 0..1 (o'rtacha kadrlar farqi)
    energy: float = 0.0  # 0..1 (audio)
    has_speech: bool = False
    faces: int = 0

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass
class HighlightSeg:
    """Highlight oralig'i (epizod klipi yoki tashqi tahlil), manba vaqtida. `score` 0..1."""

    start_ms: int
    end_ms: int
    score: float = 0.5
    title: str = ""
    clip_id: str | None = None


@dataclass
class SourceAnalysis:
    media: MediaRef
    shots: list[Shot] = field(default_factory=list)
    speech: list[tuple[int, int]] = field(default_factory=list)
    sentences: list[Sentence] = field(default_factory=list)
    highlights: list[HighlightSeg] = field(default_factory=list)
    emphasis_ms: list[int] = field(default_factory=list)
    speaker_changes_ms: list[int] = field(default_factory=list)
    # Shartnomadan tashqari qo'shimchalar (ixtiyoriy):
    curve: list[float] = field(default_factory=list)  # har CURVE_STEP_MS uchun faollik 0..1
    curve_step_ms: int = CURVE_STEP_MS
    recorded_at: str | None = None  # konteyner creation_time (ISO), "xronologik" tartib uchun
    # Ruxsat etilgan manba oraliqlari (klip manbasi: klip oralig'i, kesimlar chiqarilgan). None - butun fayl.
    # Berilmasa va media.origin "clip:" bilan boshlansa, rejalashtiruvchi highlight oraliqlarini oladi.
    allowed: list[tuple[int, int]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": ANALYSIS_VERSION,
            "media": self.media.model_dump(mode="json"),
            "shots": [dataclasses.asdict(s) for s in self.shots],
            "speech": [list(x) for x in self.speech],
            "sentences": [s.model_dump(mode="json") for s in self.sentences],
            "highlights": [dataclasses.asdict(h) for h in self.highlights],
            "emphasis_ms": list(self.emphasis_ms),
            "speaker_changes_ms": list(self.speaker_changes_ms),
            "curve": list(self.curve),
            "curve_step_ms": self.curve_step_ms,
            "recorded_at": self.recorded_at,
            "allowed": [list(x) for x in self.allowed] if self.allowed is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SourceAnalysis:
        return cls(
            media=MediaRef.model_validate(d["media"]),
            shots=[Shot(**s) for s in d.get("shots", [])],
            speech=[(int(a), int(b)) for a, b in d.get("speech", [])],
            sentences=[Sentence.model_validate(s) for s in d.get("sentences", [])],
            highlights=[HighlightSeg(**h) for h in d.get("highlights", [])],
            emphasis_ms=[int(x) for x in d.get("emphasis_ms", [])],
            speaker_changes_ms=[int(x) for x in d.get("speaker_changes_ms", [])],
            curve=[float(x) for x in d.get("curve", [])],
            curve_step_ms=int(d.get("curve_step_ms", CURVE_STEP_MS)),
            recorded_at=d.get("recorded_at"),
            allowed=[(int(a), int(b)) for a, b in d["allowed"]] if d.get("allowed") is not None else None,
        )


# --- metadata --------------------------------------------------------------------------------


@dataclass
class _Probe:
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool
    has_video: bool
    creation_time: str | None


def probe_media(path: str | os.PathLike[str]) -> _Probe:
    """Yumshoq ffprobe: ovozsiz video ham, faqat audio (musiqa) fayl ham qabul qilinadi."""
    ffprobe = find_tool("ffprobe")
    r = run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    if r.returncode != 0:
        raise MediaError(f"ffprobe xatosi: {r.stderr.strip()[:500]}")
    data = json.loads(r.stdout)
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not (s.get("disposition") or {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None and a is None:
        raise MediaError("faylda video ham, audio ham topilmadi")
    fmt = data.get("format", {})
    dur = float(fmt.get("duration") or (v or a or {}).get("duration") or 0.0)
    tags = fmt.get("tags") or {}
    return _Probe(
        duration_ms=int(round(dur * 1000)),
        width=int(v.get("width", 0)) if v else 0,
        height=int(v.get("height", 0)) if v else 0,
        fps=_fps(v.get("avg_frame_rate") or v.get("r_frame_rate")) if v else 0.0,
        has_audio=a is not None,
        has_video=v is not None,
        creation_time=tags.get("creation_time"),
    )


# --- kadr va audio o'lchovlari (sof funksiyalar, testlanadi) ---------------------------------


_GRAY = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def to_gray(rgb: np.ndarray) -> np.ndarray:
    return (rgb.astype(np.float32) @ _GRAY).astype(np.float32)


def laplacian_var(gray: np.ndarray) -> float:
    """4-qo'shnili laplasian dispersiyasi (keskinlik o'lchovi)."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    g = gray
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]) - 4.0 * g[1:-1, 1:-1]
    return float(lap.var())


def sharpness_norm(var: float) -> float:
    """Laplasian dispersiyasi -> 0..1 (log shkala: ~10 xira, ~1000 juda keskin; 320px kadr uchun)."""
    return float(np.clip((np.log10(var + 1.0) - 1.0) / 2.0, 0.0, 1.0))


def exposure_norm(mean_luma: float) -> float:
    """O'rtacha yorug'lik 0..255 -> 0..1 (juda qorong'i/oq kadr - past)."""
    return float(np.clip(1.0 - max(0.0, abs(mean_luma - 128.0) - 60.0) / 68.0, 0.0, 1.0))


def energy_norm(db: float) -> float:
    """RMS dBFS -> 0..1 (-60 dB sukut, -10 dB baland)."""
    return float(np.clip((db + 60.0) / 50.0, 0.0, 1.0))


def motion_pref(motion: float) -> float:
    """Harakatdan foydalilik: o'rtacha harakat yaxshi, haddan tashqari (silkinish) - yomon."""
    if motion <= 0.06:
        return float(np.clip(0.4 + motion / 0.06 * 0.6, 0.0, 1.0))
    return float(np.clip(1.0 - (motion - 0.06) / 0.2, 0.0, 1.0))


def shot_score(sharp: float, exposure: float, energy: float, motion: float, dur_ms: int) -> float:
    s = 0.45 * sharp + 0.2 * exposure + 0.2 * energy + 0.15 * motion_pref(motion)
    if dur_ms < 800:
        s *= 0.7
    return round(float(np.clip(s, 0.0, 1.0)), 4)


def shots_from_cuts(cuts: Sequence[int], duration_ms: int, min_ms: int = MIN_SHOT_MS) -> list[tuple[int, int]]:
    """Kesim nuqtalari -> [boshi, oxiri) oraliqlar; juda qisqalari oldingisiga qo'shiladi."""
    bounds = [0, *sorted(c for c in cuts if 0 < c < duration_ms), duration_ms]
    spans: list[tuple[int, int]] = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        if b <= a:
            continue
        if spans and (b - a < min_ms or spans[-1][1] - spans[-1][0] < min_ms):
            spans[-1] = (spans[-1][0], b)
        else:
            spans.append((a, b))
    return spans


def _overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


# --- asosiy funksiya -------------------------------------------------------------------------


def _cache_path(cache_dir: Path, file_hash: str) -> Path:
    safe = file_hash.replace(":", "-")
    return cache_dir / f"analysis-{safe}-v{ANALYSIS_VERSION}.json"


def analyze_file(
    path: Path,
    media_id: str,
    cache_dir: Path,
    settings: Settings | None = None,
    cancel: threading.Event | None = None,
    on_progress: Callable[[float], None] | None = None,
    *,
    origin: str = "file",
    scene_threshold: float | None = None,
) -> SourceAnalysis:
    """Manba faylni tahlil qiladi (kesh bo'lsa - keshdan). `cancel` o'rnatilsa `AnalysisCancelled`."""
    from lahza_engine.media.frames import iter_frames
    from lahza_engine.media.probe import extract_wav, read_wav_mono
    from lahza_engine.media.scenes import DEFAULT_THRESHOLD, detect_scene_cuts
    from lahza_engine.vad.energy import energy_vad

    del settings  # hozircha tahlil sozlamalari yo'q (R0 qiymatlari modul konstantalarida)
    path = Path(path)
    if not path.is_file():
        raise MediaError(f"fayl topilmadi: {path.name}")

    def progress(x: float) -> None:
        if on_progress is not None:
            on_progress(float(np.clip(x, 0.0, 1.0)))

    def check() -> None:
        if cancel is not None and cancel.is_set():
            raise AnalysisCancelled("tahlil bekor qilindi")

    file_hash = fast_hash(path)
    cache_dir = Path(cache_dir)
    cp = _cache_path(cache_dir, file_hash)
    if cp.is_file():
        try:
            sa = SourceAnalysis.from_dict(json.loads(cp.read_text(encoding="utf-8")))
            sa.media = sa.media.model_copy(update={"id": media_id, "path": str(path), "origin": origin})
            progress(1.0)
            return sa
        except (ValueError, KeyError, TypeError):
            pass  # buzilgan kesh - qayta hisoblaymiz

    check()
    info = probe_media(path)
    if not info.has_video:
        raise MediaError("faylda video yo'lagi yo'q")
    dur = info.duration_ms
    if dur <= 0:
        raise MediaError("video davomiyligi aniqlanmadi")
    progress(0.02)

    # 1) Sahna kesimlari -> shotlar.
    check()
    thr = DEFAULT_THRESHOLD if scene_threshold is None else scene_threshold
    spans = shots_from_cuts(detect_scene_cuts(path, 0, dur, threshold=thr), dur)
    progress(0.25)

    # 2) Audio: RMS egri chizig'i va nutq oraliqlari.
    check()
    n_steps = max(1, -(-dur // CURVE_STEP_MS))
    energy_steps = np.zeros(n_steps, dtype=np.float32)
    speech: list[tuple[int, int]] = []
    if info.has_audio:
        with tempfile.TemporaryDirectory(prefix="lahza-an-") as td:
            wav = Path(td) / "a.wav"
            try:
                extract_wav(path, wav)
                pcm, rate = read_wav_mono(wav)
            except MediaError:
                pcm, rate = np.zeros(0, dtype=np.float32), 16_000
        if len(pcm):
            hop = int(rate * CURVE_STEP_MS / 1000)
            n = min(n_steps, len(pcm) // hop + (1 if len(pcm) % hop else 0))
            for i in range(n):
                seg = pcm[i * hop:(i + 1) * hop]
                rms = float(np.sqrt(np.mean(seg.astype(np.float32) ** 2) + 1e-12))
                energy_steps[i] = energy_norm(20.0 * np.log10(rms + 1e-12))
            speech = [(int(a), int(b)) for a, b in energy_vad(pcm, rate)]
    progress(0.4)

    # 3) Kadrlar: keskinlik, yorug'lik, harakat (2 fps, 320px).
    sharp_steps = np.full(n_steps, np.nan, dtype=np.float32)
    frame_t: list[int] = []
    frame_sharp: list[float] = []
    frame_luma: list[float] = []
    frame_motion: list[float] = []
    prev: np.ndarray | None = None
    prev_shot = -1
    src_w = info.width or 1920
    src_h = info.height or 1080
    shot_idx = 0
    for t, rgb in iter_frames(path, 0, dur, fps=ANALYSIS_FPS, width=ANALYSIS_WIDTH, src_w=src_w, src_h=src_h):
        check()
        g = to_gray(rgb)
        while shot_idx + 1 < len(spans) and t >= spans[shot_idx][1]:
            shot_idx += 1
        sv = laplacian_var(g)
        frame_t.append(t)
        frame_sharp.append(sv)
        frame_luma.append(float(g.mean()))
        if prev is not None and prev_shot == shot_idx and prev.shape == g.shape:
            frame_motion.append(float(np.abs(g - prev).mean() / 255.0))
        else:
            frame_motion.append(float("nan"))
        prev, prev_shot = g, shot_idx
        k = min(n_steps - 1, t // CURVE_STEP_MS)
        sharp_steps[k] = sharpness_norm(sv)
        progress(0.4 + 0.55 * min(1.0, t / dur))

    # 4) Shotlar bo'yicha yig'ish.
    ft = np.asarray(frame_t, dtype=np.int64)
    fs = np.asarray(frame_sharp, dtype=np.float64)
    fl = np.asarray(frame_luma, dtype=np.float64)
    fm = np.asarray(frame_motion, dtype=np.float64)
    shots: list[Shot] = []
    for a, b in spans:
        mask = (ft >= a) & (ft < b) if len(ft) else np.zeros(0, dtype=bool)
        sharp = sharpness_norm(float(np.median(fs[mask]))) if mask.any() else 0.0
        luma = float(fl[mask].mean()) if mask.any() else 128.0
        mvals = fm[mask] if mask.any() else np.zeros(0)
        mvals = mvals[~np.isnan(mvals)]
        motion = float(np.clip(mvals.mean(), 0.0, 1.0)) if len(mvals) else 0.0
        ea, eb = a // CURVE_STEP_MS, max(a // CURVE_STEP_MS + 1, -(-b // CURVE_STEP_MS))
        energy = float(energy_steps[ea:eb].mean()) if eb > ea else 0.0
        sp = sum(_overlap(a, b, s0, s1) for s0, s1 in speech)
        has_speech = sp >= min(1000, 0.3 * (b - a))
        shots.append(Shot(
            start_ms=int(a), end_ms=int(b),
            score=shot_score(sharp, exposure_norm(luma), energy, motion, b - a),
            sharpness=round(sharp, 4), motion=round(motion, 4), energy=round(energy, 4),
            has_speech=bool(has_speech), faces=0,
        ))

    # Faollik egri chizig'i: kadr keskinligi (bo'lmasa - qo'shni qiymat) + energiya.
    if np.isnan(sharp_steps).all():
        sharp_fill = np.zeros(n_steps, dtype=np.float32)
    else:
        idx = np.arange(n_steps)
        ok = ~np.isnan(sharp_steps)
        sharp_fill = np.interp(idx, idx[ok], sharp_steps[ok]).astype(np.float32)
    curve = [round(float(x), 4) for x in (0.5 * sharp_fill + 0.5 * energy_steps)]

    media = MediaRef(
        id=media_id, path=str(path), hash=file_hash, duration_ms=dur, width=info.width,
        height=info.height, fps=info.fps, has_audio=info.has_audio, origin=origin,
    )
    sa = SourceAnalysis(media=media, shots=shots, speech=speech, curve=curve,
                        curve_step_ms=CURVE_STEP_MS, recorded_at=info.creation_time)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cp.with_name(cp.name + ".tmp")
        tmp.write_text(json.dumps(sa.to_dict(), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, cp)
    except OSError:
        pass  # kesh yozilmasa ham natija to'g'ri
    progress(1.0)
    return sa


# --- epizod manbalari: transkript bilan to'ldirish -------------------------------------------


_NUM_RE = re.compile(r"[+\-]?\d[\d.,:/%\-]*")


def _is_number(token: str) -> bool:
    """So'z raqammi ("2026", "15%", "3,5", "10:30")."""
    return _NUM_RE.fullmatch(token.strip(".,!?;:\"'«»()…")) is not None


def _emphasis_point(s: Sentence) -> int:
    """Gap ichidagi urg'u nuqtasi: birinchi raqam, bo'lmasa gap boshi."""
    for w in s.words:
        if _is_number(w.text):
            return w.start_ms
    return s.words[0].start_ms if s.words else s.start_ms


def enrich_with_transcript(
    sa: SourceAnalysis,
    sentences: Sequence[Sentence],
    clips: Sequence[Any] = (),
    signals: Any | None = None,
    *,
    strong_score: float = 70.0,
) -> SourceAnalysis:
    """Epizod manbasini transkript, kliplar (highlight) va signallar bilan to'ldiradi (yangi obyekt).

    * `clips` - `types.Clip` (yoki shunga o'xshash: start_ms, end_ms, score, title, id, hook_sentence_id);
    * emphasis - savol, undov yoki raqamli gaplar, signal bali `strong_score` dan yuqori gaplar, klip hook gapi;
    * speaker_changes - spiker almashgan gap boshi.
    """
    from lahza_engine.highlight.rules import is_question

    sents = sorted(sentences, key=lambda s: (s.start_ms, s.id))
    dur = sa.media.duration_ms
    by_id = signals.by_id() if signals is not None else {}
    hook_ids = {getattr(c, "hook_sentence_id", None) for c in clips} - {None}

    emphasis: set[int] = set()
    changes: list[int] = []
    prev_speaker: str | None = None
    for s in sents:
        text = s.text.strip()
        strong = False
        sig = by_id.get(s.id)
        if sig is not None and float(sig.score()) >= strong_score:
            strong = True
        has_number = any(_is_number(w.text) for w in s.words)
        if text.endswith("!") or is_question(text) or has_number or s.id in hook_ids:
            strong = True
        if strong:
            emphasis.add(int(_emphasis_point(s)))
        if s.speaker is not None:
            if prev_speaker is not None and s.speaker != prev_speaker:
                changes.append(int(s.start_ms))
            prev_speaker = s.speaker

    highlights: list[HighlightSeg] = []
    for c in clips:
        a, b = max(0, int(c.start_ms)), min(dur, int(c.end_ms))
        if b <= a:
            continue
        score = float(getattr(c, "score", 0.5) or 0.0)
        if score > 1.0:
            score = score / 100.0
        highlights.append(HighlightSeg(start_ms=a, end_ms=b, score=round(float(np.clip(score, 0, 1)), 4),
                                       title=str(getattr(c, "title", "") or ""),
                                       clip_id=getattr(c, "id", None)))

    speech = list(sa.speech) or [(s.start_ms, s.end_ms) for s in sents]
    return dataclasses.replace(
        sa, sentences=list(sents), highlights=highlights or list(sa.highlights),
        emphasis_ms=sorted(emphasis), speaker_changes_ms=changes, speech=speech,
    )
