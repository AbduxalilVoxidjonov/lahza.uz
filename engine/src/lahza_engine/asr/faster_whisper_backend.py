"""faster-whisper (CTranslate2) backend - Windows + NVIDIA (CUDA) va CPU.

Apple Silicon uses CPU int8; CTranslate2 does not support the Apple GPU.
"""

from __future__ import annotations

from pathlib import Path
from unicodedata import category

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
            word_timestamps=True,
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
        out: list[Word] = []
        for seg in segments:
            for w in seg.words or []:
                text = normalize(w.word.strip())
                # Uzbek apostrophe U+02BB is Unicode Lm and isalnum(), but is not a word.
                if not any(category(c) in {"Lu", "Ll", "Lt", "Lo", "Nd", "Nl", "No"} for c in text):
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
