"""Aktiv spikerni aniqlash (ASD): LR-ASD / Light-ASD ONNX backend (TZ 8-bo'lim, R0-VIS-2).

Model (MIT, ~3 MB) kirishi:
* audio - MFCC [1, 4T, 13]: 16 kHz, 25 ms oyna, 10 ms qadam (100 kadr/s = video kadriga 4 ta);
* vizual - kulrang yuz kesimlari [1, T, 112, 112], 25 fps, 0..255 (normallashtirish model ichida).
Chiqish - har video kadri uchun "shu yuz gapiryapti" bali; ehtimolga (0..1) o'giriladi.

Ikki ko'rinish qo'llanadi: bitta birlashgan ONNX (`asd.onnx` / `lrasd*.onnx`) yoki DeepTalk-ASD
uslubidagi uchta fayl (audio frontend, vizual frontend, AV backend). Model fayllari Task.VISION
to'plami papkasidan olinadi (`catalog.json`: `vision-blazeface-lrasd`, hozircha `candidate`).
Model yo'q / yuklanmasa - `load_asd_backend` None qaytaradi va reframe heuristikaga o'tadi
(eng katta yuz + diarizatsiya, `reframe/active_speaker.py`).

R0: tensor nomlari/shakllari, normallashtirish va chiqish turi haqiqiy eksport bilan tasdiqlanadi.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from lahza_engine.reframe.faces import Box

log = logging.getLogger(__name__)

ASD_VIDEO_FPS = 25  # LR-ASD o'qitilgan chastota (model kontrakti, R0 emas)
ASD_AUDIO_SR = 16_000
ASD_MFCC_PER_FRAME = 4  # 100 MFCC kadr/s / 25 fps
ASD_FACE_SIZE = 112
ASD_CHUNK_FRAMES = 250
"""R0: uzun trek shu uzunlikdagi bo'laklarda baholanadi (10 s); Reframe-Eval'da tanlanadi."""

COMBINED_NAMES = ("asd.onnx", "lrasd.onnx", "lr_asd.onnx", "light_asd.onnx")
SPLIT_NAMES = ("asd_audio_frontend.onnx", "asd_visual_frontend.onnx", "asd_av_backend.onnx")


class AsdBackend(Protocol):
    def score(self, faces: np.ndarray, mfcc: np.ndarray) -> np.ndarray:
        """faces [T, 112, 112] (kulrang), mfcc [4T, 13] -> [T] ehtimol (0..1)."""
        ...


# --- Oldindan ishlov berish -------------------------------------------------------------------


def _hz_to_mel(hz: np.ndarray | float) -> np.ndarray:
    return 2595 * np.log10(1 + np.asarray(hz, dtype=np.float64) / 700.0)


def _mel_to_hz(mel: np.ndarray) -> np.ndarray:
    return 700 * (10 ** (mel / 2595.0) - 1)


def _mel_filterbank(n_filt: int, nfft: int, sr: int) -> np.ndarray:
    mels = np.linspace(_hz_to_mel(0), _hz_to_mel(sr / 2), n_filt + 2)
    bins = np.floor((nfft + 1) * _mel_to_hz(mels) / sr).astype(int)
    fb = np.zeros((n_filt, nfft // 2 + 1))
    for j in range(n_filt):
        a, b, c = bins[j], bins[j + 1], bins[j + 2]
        for i in range(a, b):
            fb[j, i] = (i - a) / max(1, b - a)
        for i in range(b, c):
            fb[j, i] = (c - i) / max(1, c - b)
    return fb


def mfcc(
    audio: np.ndarray, sr: int = ASD_AUDIO_SR, numcep: int = 13, winlen: float = 0.025,
    winstep: float = 0.010, nfilt: int = 26, nfft: int = 512, preemph: float = 0.97,
    ceplifter: int = 22,
) -> np.ndarray:
    """`python_speech_features.mfcc` ga teng (LR-ASD shu bilan o'qitilgan): [N, numcep].

    c0 o'rniga kadr energiyasi logarifmi (appendEnergy=True).
    """
    # Shkala o'zgartirilmaydi: asl kod int16 qiymatlar bilan ishlaydi (R0: float audio -> *32768).
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    x =np.append(x[:1], x[1:] - preemph * x[:-1]) if len(x) else x
    flen, fstep = int(round(winlen * sr)), int(round(winstep * sr))
    n = 1 if len(x) <= flen else 1 + int(np.ceil((len(x) - flen) / fstep))
    pad = np.zeros((n - 1) * fstep + flen)
    pad[: len(x)] = x
    idx = np.arange(flen)[None, :] + fstep * np.arange(n)[:, None]
    frames = pad[idx]
    pspec = np.abs(np.fft.rfft(frames, nfft)) ** 2 / nfft
    energy = np.where(pspec.sum(1) == 0, np.finfo(float).eps, pspec.sum(1))
    feat = pspec @ _mel_filterbank(nfilt, nfft, sr).T
    feat = np.log(np.where(feat == 0, np.finfo(float).eps, feat))
    # DCT-II (ortho)
    k = np.arange(nfilt)
    basis = np.cos(np.pi * np.arange(numcep)[:, None] * (2 * k[None, :] + 1) / (2 * nfilt))
    cep = feat @ basis.T * np.sqrt(2.0 / nfilt)
    cep[:, 0] /= np.sqrt(2.0)
    lift = 1 + (ceplifter / 2.0) * np.sin(np.pi * np.arange(numcep) / ceplifter)
    cep *= lift
    cep[:, 0] = np.log(energy)
    return cep.astype(np.float32)


def face_crop(frame_rgb: np.ndarray, box: Box, size: int = ASD_FACE_SIZE,
              crop_scale: float = 0.4) -> np.ndarray:
    """LR-ASD demo uslubida yuz kesimi: kvadrat (yuz + 40% chegara) -> 2*size -> markaz size x size,
    kulrang, float32 0..255. Kadrdan tashqari qism qora bilan to'ldiriladi."""
    h, w = frame_rgb.shape[:2]
    bs = max(box.w * w, box.h * h) / 2
    cx, cy = box.cx * w, box.cy * h
    half_x = bs * (1 + crop_scale)
    y0, y1 = cy - bs, cy + bs * (1 + 2 * crop_scale)
    x0, x1 = cx - half_x, cx + half_x
    big = 2 * size
    ys = np.floor(y0 + (np.arange(big) + 0.5) * (y1 - y0) / big).astype(np.int64)
    xs = np.floor(x0 + (np.arange(big) + 0.5) * (x1 - x0) / big).astype(np.int64)
    gray = frame_rgb[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    valid = (ys[:, None] >= 0) & (ys[:, None] < h) & (xs[None, :] >= 0) & (xs[None, :] < w)
    out = gray[np.clip(ys, 0, h - 1)][:, np.clip(xs, 0, w - 1)] * valid
    q = size // 2
    return out[size - q : size + q, size - q : size + q].astype(np.float32)


def to_probability(raw: Any, mode: str = "auto", frames: int | None = None) -> np.ndarray:
    """Model chiqishi -> [T] ehtimol. [T, 2] - softmax[:, 1]; [T] - logit (sigmoid) yoki ehtimol.

    mode: "auto" (qiymatlar 0..1 ichida bo'lsa ehtimol deb olinadi), "logit", "prob".
    frames (T) ma'lum bo'lsa [1, 2] kabi noaniq shakl hajm bo'yicha ajratiladi.
    """
    a = np.asarray(raw, dtype=np.float64)
    two_class = a.ndim >= 2 and a.shape[-1] == 2
    if frames is not None:
        two_class = two_class and a.size == 2 * frames
    if two_class:
        a = a.reshape(-1, 2)
        e = np.exp(a - a.max(axis=1, keepdims=True))
        return (e[:, 1] / e.sum(axis=1)).astype(np.float32)
    a = a.reshape(-1)
    if mode == "prob" or (mode == "auto" and a.size and a.min() >= 0 and a.max() <= 1):
        return np.clip(a, 0, 1).astype(np.float32)
    return (1 / (1 + np.exp(-np.clip(a, -60, 60)))).astype(np.float32)


# --- ONNX backend -----------------------------------------------------------------------------


def _session(path: Path) -> Any:
    import onnxruntime as ort

    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def _split_av_inputs(session: Any) -> tuple[str, str]:
    """(audio, vizual) kirish nomlari: avval nom bo'yicha, keyin rang (4D - vizual), keyin tartib."""
    inputs = session.get_inputs()
    if len(inputs) < 2:
        raise ValueError("ASD modeli ikki kirish (audio, vizual) kutadi")
    names = [i.name for i in inputs]
    aud = next((n for n in names if "aud" in n.lower()), None)
    vis = next((n for n in names if any(k in n.lower() for k in ("vis", "video", "face"))), None)
    if aud is None or vis is None or aud == vis:
        ranks = [len(i.shape) if i.shape is not None else 0 for i in inputs]
        if 4 in ranks and ranks.count(4) == 1:
            vis = names[ranks.index(4)]
            aud = next(n for n in names if n != vis)
        else:
            aud, vis = names[0], names[1]
    return aud, vis


class LrAsdOnnx:
    """LR-ASD ONNX: bitta birlashgan sessiya (`session`) yoki uchtasi (`audio`, `visual`, `backend`).

    Sessiyalar tashqaridan berilishi mumkin (testlarda soxta sessiya).
    """

    def __init__(self, session: Any = None, audio: Any = None, visual: Any = None,
                 backend: Any = None, output: str = "auto",
                 visual_normalize: bool = False) -> None:
        if session is None and not (audio and visual and backend):
            raise ValueError("ASD: birlashgan sessiya yoki uchta (audio/vizual/backend) kerak")
        self.session, self.audio, self.visual, self.backend = session, audio, visual, backend
        self.output = output
        # R0: normallashtirish (x/255 - 0.4161)/0.1688 model ichidami - eksportda tasdiqlanadi.
        self.visual_normalize = visual_normalize

    @classmethod
    def from_dir(cls, root: Path) -> LrAsdOnnx:
        files = find_asd_files(root)
        if files is None:
            raise FileNotFoundError(f"ASD ONNX fayllari topilmadi: {root}")
        if len(files) == 1:
            return cls(session=_session(files[0]))
        a, v, b = files
        return cls(audio=_session(a), visual=_session(v), backend=_session(b))

    def _prep(self, faces: np.ndarray, mfcc_feats: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
        t = min(len(faces), len(mfcc_feats) // ASD_MFCC_PER_FRAME)
        v = np.asarray(faces[:t], dtype=np.float32)
        if self.visual_normalize:
            v = (v / 255.0 - 0.4161) / 0.1688
        a = np.asarray(mfcc_feats[: t * ASD_MFCC_PER_FRAME], dtype=np.float32)
        return a[None], v[None], t

    def _run(self, a: np.ndarray, v: np.ndarray) -> np.ndarray:
        if self.session is not None:
            aud, vis = _split_av_inputs(self.session)
            out = self.session.run(None, {aud: a, vis: v})[0]
        else:
            a_emb = self.audio.run(None, {self.audio.get_inputs()[0].name: a})[0]
            v_emb = self.visual.run(None, {self.visual.get_inputs()[0].name: v})[0]
            aud, vis = _split_av_inputs(self.backend)
            out = self.backend.run(None, {aud: a_emb, vis: v_emb})[0]
        return to_probability(out, self.output, frames=v.shape[1])

    def score(self, faces: np.ndarray, mfcc: np.ndarray) -> np.ndarray:  # noqa: D102
        a, v, t = self._prep(faces, mfcc)
        if t == 0:
            return np.zeros(0, dtype=np.float32)
        out = np.zeros(t, dtype=np.float32)
        for s in range(0, t, ASD_CHUNK_FRAMES):
            e = min(t, s + ASD_CHUNK_FRAMES)
            p = self._run(a[:, s * ASD_MFCC_PER_FRAME : e * ASD_MFCC_PER_FRAME], v[:, s:e])
            n = min(len(p), e - s)
            out[s : s + n] = p[:n]
            if n < e - s and n:
                out[s + n : e] = p[n - 1]
        return out


def find_asd_files(root: Path) -> list[Path] | None:
    """Birlashgan fayl ([1 ta]) yoki uchta bo'lingan fayl ([audio, vizual, backend]); yo'q - None."""
    if root.is_file():
        return [root] if root.suffix == ".onnx" and "asd" in root.name.lower() else None
    if not root.is_dir():
        return None
    files = {p.name.lower(): p for p in root.rglob("*.onnx")}
    split = [files.get(n) for n in SPLIT_NAMES]
    if all(split):
        return [p for p in split if p is not None]
    for n in COMBINED_NAMES:
        if n in files:
            return [files[n]]
    return None


def load_asd_backend(root: Path | None) -> LrAsdOnnx | None:
    """Model papkasidan backend; model/onnxruntime yo'q yoki buzuq bo'lsa - None (xatosiz)."""
    if root is None:
        return None
    try:
        if find_asd_files(Path(root)) is None:
            log.info("ASD modeli yo'q - reframe heuristikada (eng katta yuz + diarizatsiya)")
            return None
        return LrAsdOnnx.from_dir(Path(root))
    except Exception as e:  # noqa: BLE001 - ixtiyoriy backend
        log.warning("LR-ASD ONNX yuklanmadi, heuristikaga o'tiladi: %s", e)
        return None


def load_asd_from_store(store: Any) -> LrAsdOnnx | None:
    """Task.VISION standart to'plamidan (`ModelStore.default_for`) ASD fayllarini yuklaydi."""
    from lahza_engine.models.catalog import Task

    try:
        m = store.default_for(Task.VISION)
    except Exception as e:  # noqa: BLE001
        log.warning("model ombori o'qilmadi: %s", e)
        return None
    return load_asd_backend(Path(m.path)) if m is not None else None


# --- Trek bo'yicha baholash -------------------------------------------------------------------


def score_track(
    backend: AsdBackend | None, frames: list[tuple[int, np.ndarray]], audio: np.ndarray,
    audio_start_ms: int = 0, sr: int = ASD_AUDIO_SR,
) -> list[tuple[int, float]]:
    """Bitta yuz treki: [(t_ms, yuz kesimi 112x112)] (ketma-ket, ~25 fps) + audio -> [(t_ms, ball)].

    Audio trek vaqtiga kesiladi; backend yo'q yoki xato bo'lsa - bo'sh ro'yxat (heuristika).
    """
    if backend is None or not frames:
        return []
    t0 = frames[0][0]
    s = max(0, int((t0 - audio_start_ms) * sr / 1000))
    e = s + int(len(frames) * sr / ASD_VIDEO_FPS) + int(0.025 * sr)
    try:
        feats = mfcc(np.asarray(audio)[s:e], sr)
        probs = backend.score(np.stack([f for _, f in frames]), feats)
    except Exception as ex:  # noqa: BLE001 - bitta trek xatosi butun reframe'ni to'xtatmaydi
        log.warning("ASD baholash xatosi: %s", ex)
        return []
    return [(t, float(p)) for (t, _), p in zip(frames, probs, strict=False)]


def scores_at(track_scores: dict[int, list[tuple[int, float]]], t_ms: int,
              window_ms: int = 200) -> dict[int, float]:
    """Analiz kuzatuvi vaqtidagi (5 fps) trek ballari: +-window_ms oynadagi o'rtacha (25 fps -> 5)."""
    out: dict[int, float] = {}
    for tid, seq in track_scores.items():
        vals = [p for t, p in seq if abs(t - t_ms) <= window_ms]
        if vals:
            out[tid] = float(sum(vals) / len(vals))
    return out
