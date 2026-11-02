"""Yuz aniqlash va treking (TZ 8-bo'lim).

* Detektor: MediaPipe BlazeFace (Apache-2.0). Asosiy yo'l - ONNX (`OnnxBlazeFaceDetector`,
  onnxruntime, torch/mediapipe'siz); `mediapipe` paketi - zaxira ("vision" extra).
  Core ML porti R0'da isbotlanadi (docs/02-yol-xaritasi.md, R0-VIS-1).
* Treker: IoU assotsiatsiya + markaz uchun doimiy tezlikli Kalman filtr (SORT uslubi).
  Biometrik yuz tanish ishlatilmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Box:
    """Normallashgan koordinatalar (0..1)."""

    x: float
    y: float
    w: float
    h: float
    score: float = 1.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def box_iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
    iy = max(0.0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


class FaceDetector(Protocol):
    def detect(self, frame_rgb: np.ndarray) -> list[Box]: ...


class MediaPipeDetector:
    """`mediapipe` Python paketi orqali. Paket yo'q bo'lsa ImportError (ixtiyoriy backend)."""

    def __init__(self, min_confidence: float = 0.5, full_range: bool = True) -> None:
        import mediapipe as mp

        self._fd = mp.solutions.face_detection.FaceDetection(
            model_selection=1 if full_range else 0, min_detection_confidence=min_confidence
        )

    def detect(self, frame_rgb: np.ndarray) -> list[Box]:
        res = self._fd.process(frame_rgb)
        out: list[Box] = []
        for d in res.detections or []:
            bb = d.location_data.relative_bounding_box
            out.append(Box(bb.xmin, bb.ymin, bb.width, bb.height, float(d.score[0])))
        return out


# --- BlazeFace ONNX (R0-VIS-1) -----------------------------------------------------------------

# MediaPipe SsdAnchorsCalculator sozlamalari (fixed_anchor_size, aspect_ratio 1.0).
# short-range 128: [8,16,16,16] -> 16*16*2 + 8*8*6 = 896; back 256: [16,32,32,32] -> 896;
# full-range 192: [4], interpolated_scale yo'q -> 48*48*1 = 2304.
_BLAZE_CONFIGS: list[tuple[tuple[int, ...], bool]] = [
    ((8, 16, 16, 16), True),
    ((16, 32, 32, 32), True),
    ((4,), False),
]


def generate_anchors(input_size: int, strides: tuple[int, ...], interpolated: bool = True) -> np.ndarray:
    """SSD uslubidagi anchorlar [N, 2] (cx, cy) - normallashgan; o'lcham 1x1 (fixed_anchor_size)."""
    per_layer = 2 if interpolated else 1
    out: list[tuple[float, float]] = []
    i = 0
    while i < len(strides):
        j = i
        n = 0
        while j < len(strides) and strides[j] == strides[i]:
            n += per_layer
            j += 1
        fm = int(np.ceil(input_size / strides[i]))
        for y in range(fm):
            for x in range(fm):
                out.extend([((x + 0.5) / fm, (y + 0.5) / fm)] * n)
        i = j
    return np.asarray(out, dtype=np.float32)


def anchors_for(input_size: int, n_anchors: int) -> np.ndarray:
    for strides, interp in _BLAZE_CONFIGS:
        a = generate_anchors(input_size, strides, interp)
        if len(a) == n_anchors:
            return a
    raise ValueError(f"BlazeFace anchor sozlamasi topilmadi: kirish {input_size}, {n_anchors} anchor")


def decode_boxes(raw: np.ndarray, anchors: np.ndarray, input_size: int) -> np.ndarray:
    """raw [N, >=4] (dx, dy, w, h piksellarda) -> [N, 4] (xmin, ymin, xmax, ymax) normallashgan."""
    cx = raw[:, 0] / input_size + anchors[:, 0]
    cy = raw[:, 1] / input_size + anchors[:, 1]
    w = raw[:, 2] / input_size
    h = raw[:, 3] / input_size
    return np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)


def _iou_xyxy(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ix = np.clip(np.minimum(a[2], b[:, 2]) - np.maximum(a[0], b[:, 0]), 0, None)
    iy = np.clip(np.minimum(a[3], b[:, 3]) - np.maximum(a[1], b[:, 1]), 0, None)
    inter = ix * iy
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    union = area_a + area_b - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-12), 0.0)


def weighted_nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.3) -> list[tuple[np.ndarray, float]]:
    """MediaPipe "WEIGHTED" NMS: ustma-ust guruh ball bilan o'rtachalanadi, ball - eng yuqorisi."""
    order = np.argsort(-scores)
    boxes, scores = boxes[order], scores[order]
    remaining = np.ones(len(scores), dtype=bool)
    out: list[tuple[np.ndarray, float]] = []
    for i in range(len(scores)):
        if not remaining[i]:
            continue
        ious = _iou_xyxy(boxes[i], boxes)
        group = remaining & (ious > iou_threshold)
        group[i] = True
        w = scores[group][:, None]
        out.append(((boxes[group] * w).sum(axis=0) / w.sum(), float(scores[i])))
        remaining &= ~group
    return out


def _letterbox(frame: np.ndarray, size: int) -> tuple[np.ndarray, float, float, float, float]:
    """Nisbatni saqlab size x size ga (eng yaqin qo'shni), qora chiziqlar bilan.

    Qaytaradi: rasm, (pad_x, pad_y, scale_x, scale_y) - normallashgan kirishdan kadrga o'tish uchun.
    """
    h, w = frame.shape[:2]
    s = size / max(h, w)
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    ys = np.minimum((np.arange(nh) / s).astype(np.int64), h - 1)
    xs = np.minimum((np.arange(nw) / s).astype(np.int64), w - 1)
    small = frame[ys][:, xs]
    canvas = np.zeros((size, size, frame.shape[2]), dtype=frame.dtype)
    ox, oy = (size - nw) // 2, (size - nh) // 2
    canvas[oy : oy + nh, ox : ox + nw] = small
    return canvas, ox / size, oy / size, nw / size, nh / size


class OnnxBlazeFaceDetector:
    """BlazeFace (short/full-range) ONNX, onnxruntime orqali. Kirish o'lchami va chiqish
    tensorlari sessiyadan o'qiladi."""

    def __init__(self, model_path=None, session=None, min_score: float = 0.5,  # noqa: ANN001
                 iou_threshold: float = 0.3) -> None:
        if session is None:
            if model_path is None:
                raise ValueError("model_path yoki session kerak")
            import onnxruntime as ort

            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.session = session
        inp = session.get_inputs()[0]
        self.input_name = inp.name
        shape = list(inp.shape)
        self.nchw = len(shape) == 4 and shape[1] == 3
        dims = [d for d in shape[1:] if isinstance(d, int) and d > 3]
        if not dims:
            raise ValueError(f"BlazeFace kirish shakli noma'lum: {shape}")
        self.input_size = int(dims[0])
        self.min_score = min_score
        self.iou_threshold = iou_threshold
        self._anchors: np.ndarray | None = None

    def _split_outputs(self, outputs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        regs, cls = [], []
        for o in outputs:
            a = np.asarray(o, dtype=np.float32)
            a = a.reshape(-1, a.shape[-1]) if a.ndim >= 2 else a.reshape(-1, 1)
            (cls if a.shape[-1] == 1 else regs).append(a)
        if not regs or not cls:
            raise ValueError("BlazeFace chiqishlari (regressors/classificators) topilmadi")
        # Bo'lingan chiqishlar (masalan 512 + 384) - anchor tartibida: kattasi oldin.
        regs.sort(key=len, reverse=True)
        cls.sort(key=len, reverse=True)
        return np.concatenate(regs), np.concatenate(cls)[:, 0]

    def detect_raw(self, raw: np.ndarray, logits: np.ndarray) -> list[tuple[np.ndarray, float]]:
        """Dekodlash + sigmoid + NMS; natija kirish rasmi koordinatalarida (0..1)."""
        if self._anchors is None or len(self._anchors) != len(raw):
            self._anchors = anchors_for(self.input_size, len(raw))
        scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -100, 100)))
        keep = scores >= self.min_score
        if not keep.any():
            return []
        boxes = decode_boxes(raw[keep], self._anchors[keep], self.input_size)
        return weighted_nms(boxes, scores[keep], self.iou_threshold)

    def detect(self, frame_rgb: np.ndarray) -> list[Box]:
        img, ox, oy, sx, sy = _letterbox(frame_rgb[..., :3], self.input_size)
        x = img.astype(np.float32) / 127.5 - 1.0
        x = x.transpose(2, 0, 1)[None] if self.nchw else x[None]
        raw, logits = self._split_outputs(self.session.run(None, {self.input_name: x}))
        out: list[Box] = []
        for b, sc in self.detect_raw(raw, logits):
            x0 = float(np.clip((b[0] - ox) / sx, 0, 1))
            y0 = float(np.clip((b[1] - oy) / sy, 0, 1))
            x1 = float(np.clip((b[2] - ox) / sx, 0, 1))
            y1 = float(np.clip((b[3] - oy) / sy, 0, 1))
            if x1 > x0 and y1 > y0:
                out.append(Box(x0, y0, x1 - x0, y1 - y0, sc))
        return out


class _Kalman1D2:
    """Holat [cx, cy, vx, vy], o'lchov [cx, cy]."""

    def __init__(self, cx: float, cy: float, q: float = 1e-3, r: float = 4e-4) -> None:
        self.x = np.array([cx, cy, 0.0, 0.0])
        self.P = np.eye(4) * 0.01
        self.Q = np.eye(4) * q
        self.R = np.eye(2) * r
        self.H = np.array([[1.0, 0, 0, 0], [0, 1.0, 0, 0]])

    def predict(self, dt: float) -> np.ndarray:
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q
        return self.x[:2]

    def update(self, cx: float, cy: float) -> None:
        z = np.array([cx, cy])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P


@dataclass
class Track:
    id: int
    box: Box
    kf: _Kalman1D2
    hits: int = 1
    misses: int = 0
    history: list[tuple[int, Box]] = field(default_factory=list)


class FaceTracker:
    def __init__(self, iou_threshold: float = 0.2, max_misses: int = 10) -> None:
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self.tracks: list[Track] = []
        self._next_id = 0
        self._last_t: int | None = None

    def update(self, t_ms: int, boxes: list[Box]) -> list[Track]:
        dt = 0.0 if self._last_t is None else (t_ms - self._last_t) / 1000
        self._last_t = t_ms
        for tr in self.tracks:
            tr.kf.predict(dt)
        unmatched = list(range(len(boxes)))
        pairs = sorted(
            ((box_iou(tr.box, boxes[j]), ti, j) for ti, tr in enumerate(self.tracks) for j in unmatched),
            reverse=True,
        )
        used_t: set[int] = set()
        used_b: set[int] = set()
        for score, ti, j in pairs:
            if score < self.iou_threshold or ti in used_t or j in used_b:
                continue
            tr = self.tracks[ti]
            b = boxes[j]
            tr.kf.update(b.cx, b.cy)
            tr.box, tr.hits, tr.misses = b, tr.hits + 1, 0
            tr.history.append((t_ms, b))
            used_t.add(ti)
            used_b.add(j)
        for ti, tr in enumerate(self.tracks):
            if ti not in used_t:
                tr.misses += 1
        for j, b in enumerate(boxes):
            if j not in used_b:
                tr = Track(self._next_id, b, _Kalman1D2(b.cx, b.cy), history=[(t_ms, b)])
                self._next_id += 1
                self.tracks.append(tr)
        self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]
        return [t for t in self.tracks if t.misses == 0]

    def smoothed_center(self, track_id: int) -> tuple[float, float] | None:
        for t in self.tracks:
            if t.id == track_id:
                return float(t.kf.x[0]), float(t.kf.x[1])
        return None
