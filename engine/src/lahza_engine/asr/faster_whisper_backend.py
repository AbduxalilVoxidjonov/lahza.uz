"""faster-whisper (CTranslate2) backend - Windows + NVIDIA (CUDA) va CPU.

Apple Silicon uses CPU int8; CTranslate2 does not support the Apple GPU.
"""

from __future__ import annotations

import math
from pathlib import Path
from unicodedata import category

from lahza_engine.align.realign import distribute
from lahza_engine.asr.base import AsrOptions, hotword_prompt
from lahza_engine.text.orthography import normalize
from lahza_engine.types import Word


class FasterWhisperBackend:
    def __init__(self, model_dir: Path, model_id: str, device: str = "auto") -> None:
        from faster_whisper import WhisperModel

        compute = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(str(model_dir), device=device, compute_type=compute, local_files_only=True)
        self.model_id = model_id

    def transcribe_chunk(self, wav: Path, offset_ms: int, opts: AsrOptions) -> list[Word]:
        prompt = hotword_prompt(opts.hotwords)
        kwargs = dict(
            language=opts.language,
            # "ctc": timestamp tokenlarisiz (aniqroq matn), vaqtlarni CTC aligner beradi.
            word_timestamps=opts.timestamps != "ctc",
            without_timestamps=opts.timestamps == "ctc",
            beam_size=opts.beam_size,
            temperature=opts.temperature,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            vad_filter=False,  # VAD oldinroq bajarilgan
        )
        try:
            segments, _ = self.model.transcribe(str(wav), hotwords=prompt, **kwargs)
        except TypeError as exc:
            # The callable's name may itself contain 'hotwords'; only a rejected
            # keyword is evidence for the compatibility fallback.
            if not any(s in str(exc) for s in (
                "unexpected keyword argument 'hotwords'", 'unexpected keyword argument "hotwords"',
            )):
                raise
            # faster-whisper < 1.0: `hotwords` yo'q - lug'at initial_prompt orqali uzatiladi.
            segments, _ = self.model.transcribe(str(wav), initial_prompt=prompt, **kwargs)
        if opts.timestamps == "ctc":
            return _text_words(segments, offset_ms)
        out: list[Word] = []
        for seg in segments:
            for w in seg.words or []:
                text = normalize(w.word.strip())
                if not _is_word(text):
                    continue
                out.append(
                    Word(
                        text=text,
                        start_ms=offset_ms + int(w.start * 1000),
                        end_ms=offset_ms + int(w.end * 1000),
                        conf=float(w.probability),
                    )
                )
        return out


def _is_word(text: str) -> bool:
    # Uzbek apostrophe U+02BB is Unicode Lm and isalnum(), but is not a word.
    return any(category(c) in {"Lu", "Ll", "Lt", "Lo", "Nd", "Nl", "No"} for c in text)


def segment_conf(avg_logprob: float | None) -> float | None:
    """Segment ishonchi: exp(o'rtacha token log-ehtimoli) - tokenlar ehtimolining geometrik o'rtachasi.

    `without_timestamps` da so'z ehtimoli (word.probability) yo'q; bu - bir xil shkaladagi
    (0..1, UI'da < 0.6 "past ishonch") eng yaqin o'lchov.
    """
    if avg_logprob is None or not math.isfinite(avg_logprob):
        return None
    return max(0.0, min(1.0, math.exp(avg_logprob)))


def _text_words(segments: object, offset_ms: int) -> list[Word]:
    """Timestamp'siz segmentlar -> so'zlar; vaqt segment ichida harf soniga proporsional (taxminiy)."""
    out: list[Word] = []
    for seg in segments:  # type: ignore[attr-defined]
        words = [Word(text=t, start_ms=0, end_ms=0, conf=segment_conf(getattr(seg, "avg_logprob", None)))
                 for t in (normalize(x) for x in (seg.text or "").split()) if _is_word(t)]
        a = offset_ms + int(round(float(seg.start) * 1000))
        b = offset_ms + int(round(float(seg.end) * 1000))
        out.extend(distribute(words, a, max(b, a + len(words))))
    return out
