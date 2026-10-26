"""whisper.cpp (`whisper-cli`) backend - macOS (Metal/Core ML) va Windows AMD/Intel (Vulkan).

"whisper" rejimi: so'z darajasi uchun `-ml 1 -sow` (har segment = bitta so'z) va `-oj` (JSON);
JSON'dagi `transcription[].offsets.{from,to}` - ms. "ctc" rejimi (standart): `-nt` - timestamp
tokenlarisiz dekodlash, faqat matn olinadi; so'z vaqtlari bo'lak ichida taxminiy, aniqini CTC aligner
beradi (asr/base.py AsrOptions.timestamps). Bayroqlar mahkamlangan whisper.cpp versiyasi
bilan R0'da tekshiriladi (third_party/runtimes.toml).
"""

from __future__ import annotations

import json
import tempfile
import wave
from pathlib import Path

from lahza_engine.align.realign import distribute
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


def parse_whisper_text(data: dict, offset_ms: int, duration_ms: int) -> list[Word]:
    """`-nt` JSON: segment matnlari so'zlarga bo'linadi, vaqt [offset, offset+davomiylik] ichida
    harf soniga proporsional (offsets ishlatilmaydi - timestamp'siz rejimda ishonchsiz)."""
    words: list[Word] = []
    for seg in data.get("transcription", []):
        text = (seg.get("text") or "").strip()
        if not text or (text.startswith("[") and text.endswith("]")):
            continue
        words.extend(Word(text=t, start_ms=0, end_ms=0) for t in (normalize(x) for x in text.split())
                     if any(c.isalnum() and c not in "ʻʼ" for c in t))
    return distribute(words, offset_ms, offset_ms + max(duration_ms, len(words)))


def _wav_ms(path: Path) -> int:
    """Bo'lak davomiyligi (ms); o'qib bo'lmasa 0 (so'zlar offset atrofida minimal oraliq oladi)."""
    try:
        with wave.open(str(path), "rb") as w:
            return int(w.getnframes() * 1000 / max(1, w.getframerate()))
    except (OSError, EOFError, wave.Error):
        return 0


def output_args(opts: AsrOptions) -> list[str]:
    """Rejimga qarab chiqish bayroqlari: "ctc" - `-nt` (timestamp'siz), "whisper" - so'z segmentlari."""
    if opts.timestamps == "ctc":
        return ["-nt"]
    return ["-ml", "1", "-sow"]


def decoder_args(opts: AsrOptions) -> list[str]:
    """faster-whisper backend'i bilan bir xil dekoder sozlamalari (whisper-cli bayroqlari).

    `-tp` harorat, `-nf` - harorat fallback'i o'chiq (faqat temperature == 0 da), `-bs` beam,
    `-et`/`-lpt` - compression_ratio/log_prob chegaralarining whisper.cpp ekvivalenti. `-nth`
    (no_speech) faqat yangi whisper.cpp'da bor - versiya mahkamlanmaguncha qo'yilmaydi.
    """
    args = ["-bs", str(opts.beam_size), "-tp", f"{opts.temperature:g}", "-et", "2.4", "-lpt", "-1.0"]
    if opts.temperature <= 0:
        args.append("-nf")
    return args


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
                *output_args(opts), "-oj", "-of", out_base, "-np",
                *decoder_args(opts),
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
        if opts.timestamps == "ctc":
            return parse_whisper_text(data, offset_ms, _wav_ms(Path(wav)))
        return parse_whisper_json(data, offset_ms)
