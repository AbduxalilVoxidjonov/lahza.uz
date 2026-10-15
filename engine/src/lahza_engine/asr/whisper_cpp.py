"""whisper.cpp (`whisper-cli`) backend - macOS (Metal/Core ML) va Windows AMD/Intel (Vulkan).

So'z darajasi uchun `-ml 1 -sow` (har segment = bitta so'z) va `-oj` (JSON) ishlatiladi.
JSON'dagi `transcription[].offsets.{from,to}` - ms. Bayroqlar mahkamlangan whisper.cpp versiyasi
bilan R0'da tekshiriladi (third_party/runtimes.toml).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lahza_engine.asr.base import AsrOptions, hotword_prompt
from lahza_engine.media.tools import find_tool, run
from lahza_engine.text.orthography import normalize
from lahza_engine.types import Word


def parse_whisper_json(data: dict, offset_ms: int) -> list[Word]:
    words: list[Word] = []
    for seg in data.get("transcription", []):
        text = (seg.get("text") or "").strip()
        if not text or (text.startswith("[") and text.endswith("]")):
            continue  # [_BEG_], [MUSIQA] kabi maxsus tokenlar
        off = seg.get("offsets") or {}
        a, b = int(off.get("from", 0)), int(off.get("to", 0))
        if b <= a:
            continue
        words.append(Word(text=normalize(text), start_ms=a + offset_ms, end_ms=b + offset_ms))
    return words


class WhisperCppBackend:
    def __init__(self, model_path: Path, model_id: str) -> None:
        self.model_path = model_path
        self.model_id = model_id
        self.exe = find_tool("whisper-cli")

    def transcribe_chunk(self, wav: Path, offset_ms: int, opts: AsrOptions) -> list[Word]:
        with tempfile.TemporaryDirectory() as td:
            out_base = Path(td) / "out"
            args = [
                self.exe, "-m", self.model_path, "-f", wav, "-l", opts.language,
                "-ml", "1", "-sow", "-oj", "-of", out_base, "-np",
            ]
            if opts.threads:
                args += ["-t", str(opts.threads)]
            prompt = hotword_prompt(opts.hotwords)
            if prompt:
                # Eslatma: `-mc 0` qo'yilmaydi - u boshlang'ich promptni ham o'chiradi.
                args += ["--prompt", prompt]
            r = run(args, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"whisper-cli xatosi: {r.stderr.strip()[-500:]}")
            data = json.loads(out_base.with_suffix(".json").read_text(encoding="utf-8"))
        return parse_whisper_json(data, offset_ms)
