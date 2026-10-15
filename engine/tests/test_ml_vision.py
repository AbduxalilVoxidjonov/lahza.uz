import numpy as np
import pytest

from lahza_engine.reframe.faces import (
    Box,
    OnnxBlazeFaceDetector,
    anchors_for,
    decode_boxes,
    generate_anchors,
    weighted_nms,
)
from lahza_engine.reframe.speaker_map import AsdSample, active_index, largest_face_index


def test_anchor_counts() -> None:
    assert len(generate_anchors(128, (8, 16, 16, 16))) == 896
    assert len(generate_anchors(192, (4,), interpolated=False)) == 2304
    a = anchors_for(128, 896)
    assert a[0].tolist() == pytest.approx([0.5 / 16, 0.5 / 16])
    assert a[1].tolist() == a[0].tolist()  # har katakda 2 ta (stride 8)
    assert a[512].tolist() == pytest.approx([0.5 / 8, 0.5 / 8])  # stride 16 qatlami boshlanishi
    assert np.all(a[512:518] == a[512])  # 6 ta anchor
    with pytest.raises(ValueError):
        anchors_for(128, 1000)


def test_decode_and_weighted_nms() -> None:
    anchors = np.array([[0.5, 0.5], [0.5, 0.5], [0.1, 0.1]], dtype=np.float32)
    raw = np.zeros((3, 16), dtype=np.float32)
    raw[0, :4] = [0, 0, 64, 64]  # markaz 0.5, o'lcham 0.5
    raw[1, :4] = [6.4, 0, 64, 64]  # biroz o'ngga
    raw[2, :4] = [0, 0, 12.8, 12.8]
    boxes = decode_boxes(raw, anchors, 128)
    assert boxes[0].tolist() == pytest.approx([0.25, 0.25, 0.75, 0.75])
    res = weighted_nms(boxes, np.array([0.9, 0.6, 0.8]), 0.3)
    assert len(res) == 2
    merged, score = res[0]
    assert score == pytest.approx(0.9)
    assert merged[0] == pytest.approx(0.25 + 0.05 * 0.6 / 1.5)  # ball bo'yicha o'rtacha


class _Inp:
    def __init__(self, shape):
        self.name = "input"
        self.shape = shape


class FakeBlazeSession:
    """Bitta yuz: 896 anchordan bittasida yuqori logit. Chiqishlar bo'lingan (512 + 384)."""

    def __init__(self, nchw: bool = False) -> None:
        self.shape = [1, 3, 128, 128] if nchw else [1, 128, 128, 3]
        self.seen = None

    def get_inputs(self):
        return [_Inp(self.shape)]

    def run(self, _outs, feeds):
        self.seen = feeds["input"]
        anchors = anchors_for(128, 896)
        idx = 512 + 6 * (4 * 8 + 4)  # stride 16 katagi (4, 4): markaz (0.5625, 0.5625)
        reg = np.zeros((1, 896, 16), dtype=np.float32)
        cls = np.full((1, 896, 1), -10.0, dtype=np.float32)
        reg[0, idx, :4] = [0, 0, 32, 32]
        cls[0, idx, 0] = 5.0
        assert anchors[idx].tolist() == pytest.approx([0.5625, 0.5625])
        return [reg[:, :512], cls[:, :512], reg[:, 512:], cls[:, 512:]]


@pytest.mark.parametrize("nchw", [False, True])
def test_onnx_blazeface_detect_letterbox(nchw: bool) -> None:
    sess = FakeBlazeSession(nchw)
    det = OnnxBlazeFaceDetector(session=sess)
    assert det.input_size == 128 and det.nchw is nchw
    frame = np.full((100, 200, 3), 255, dtype=np.uint8)  # keng kadr -> tepada/pastda chiziq
    boxes = det.detect(frame)
    assert sess.seen.shape == ((1, 3, 128, 128) if nchw else (1, 128, 128, 3))
    assert sess.seen.min() == pytest.approx(-1.0) and sess.seen.max() == pytest.approx(1.0)
    assert len(boxes) == 1
    b = boxes[0]
    # kirishda x: 0.5625±0.125; y: letterbox (pad 0.25, balandlik 0.5) -> (0.5625-0.25)/0.5
    assert b.cx == pytest.approx(0.5625, abs=1e-3)
    assert b.cy == pytest.approx(0.625, abs=1e-3)
    assert b.w == pytest.approx(0.25, abs=1e-3) and b.h == pytest.approx(0.5, abs=1e-3)
    assert b.score == pytest.approx(1 / (1 + np.exp(-5.0)), abs=1e-4)


def test_largest_face_fallback_without_asd() -> None:
    boxes = [Box(0, 0, 0.1, 0.1), Box(0.5, 0.5, 0.3, 0.3), Box(0.2, 0.2, 0.2, 0.2)]
    assert largest_face_index([]) is None
    assert largest_face_index(boxes) == 1
    assert active_index(boxes) == 1
    sample = AsdSample(0, "S1", {7: 0.9, 8: 0.1})
    assert active_index(boxes, track_ids=[8, 9, 7], sample=sample, speaker_to_track={"S1": 7}) == 2
