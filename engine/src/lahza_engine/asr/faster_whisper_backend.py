"""faster-whisper (CTranslate2) backend - Windows + NVIDIA (CUDA) va CPU.

CTranslate2 Apple Silicon GPU'ni qo'llamaydi, shuning uchun macOS'da whisper.cpp ishlatiladi.
"""

from __future__ import annotations

from pathlib import Path

from lahza_engine.asr.base import AsrOptions, hotword_prompt
from lahza_engine.text.orthography import normalize
from lahza_engine.types import Word


class FasterWhisperBackend:
    def __init__(self, model_dir: Path, model_id: str, device: str = "auto") -> None:
        from faster_whisper import WhisperModel

        compute = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(str(model_dir), device=device, compute_type=compute)
        self.model_id = model_id

    def transcribe_chunk(self, wav: Path, offset_ms: int, opts: AsrOptions) -> list[Word]:
        prompt = hotword_prompt(opts.hotwords)
        kwargs = dict(
            language=opts.language,
            word_timestamps=True,
            condition_on_previous_text=False,
            vad_filter=False,  # VAD oldinroq bajarilgan
        )
        try:
            segments, _ = self.model.transcribe(str(wav), hotwords=prompt, **kwargs)
        except TypeError:
            # faster-whisper < 1.0: `hotwords` yo'q - lug'at initial_prompt orqali uzatiladi.
            segments, _ = self.model.transcribe(str(wav), initial_prompt=prompt, **kwargs)
        out: list[Word] = []
        for seg in segments:
            for w in seg.words or []:
                text = w.word.strip()
                if not text:
                    continue
                out.append(
                    Word(
                        text=normalize(text),
                        start_ms=offset_ms + int(w.start * 1000),
                        end_ms=offset_ms + int(w.end * 1000),
                        conf=float(w.probability),
                    )
                )
        return out
