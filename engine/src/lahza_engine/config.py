"""Sozlamalar.

Qiymatlar ikki turda:
* TZ'dan olingan talablar (masalan, xavfsiz zona foizlari, 1080x1920) - manba ko'rsatilgan.
* Boshlang'ich muhandislik qiymatlari - "R0" deb belgilangan; ular R0 benchmarkida
  (docs/02-yol-xaritasi.md) o'lchanib, yangilanadi. Ularni fakt sifatida talqin qilmang.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field


def default_data_dir() -> Path:
    """Foydalanuvchi ma'lumotlari papkasi (modellar, kutubxona, loglar)."""
    env = os.environ.get("LAHZA_DATA_DIR")
    if env:
        return Path(env)
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Lahza Studio"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        return Path(base) / "Lahza Studio"
    return home / ".local" / "share" / "lahza-studio"


class HighlightConfig(BaseModel):
    min_clip_ms: int = 30_000  # TZ 7-bo'lim: standart 30-60 s
    max_clip_ms: int = 60_000
    hard_min_ms: int = 15_000  # TZ: 15-180 s oralig'ida sozlanadi
    hard_max_ms: int = 180_000
    clip_count: int = 10
    pre_roll_ms: int = 150  # TZ: 100-200 ms "nafas"
    post_roll_ms: int = 300  # TZ: gap oxiri + 300 ms
    min_pause_before_start_ms: int = 150  # TZ: oldidagi pauza >= 150 ms
    # R0: LLM oynasi uzunligi va ustma-ustligi R0'da tanlanadi.
    llm_window_ms: int = 8 * 60_000
    llm_window_overlap_ms: int = 60_000
    # R0: yakuniy ball vaznlari foydalanuvchi qarorlaridan o'rganiladi.
    weight_llm: float = 0.7
    weight_signals: float = 0.3
    nms_iou: float = 0.3


class SubtitleSafeZone(BaseModel):
    """Conservative Lahza safe guides based on ads guidance, not universal organic rules."""

    top_pct: float = 0.14
    bottom_pct: float = 0.35
    side_pct: float = 0.06


class RenderConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    video_bitrate_kbps: int = 12_000  # TZ: 8-15 Mbps oralig'ida sozlanadi
    audio_bitrate_kbps: int = 192
    audio_rate: int = 48_000
    fade_ms: int = 150  # TZ: 100-200 ms
    # TZ 19-bo'lim: standart LUFS maqsadi ANIQLANSIN. None bo'lsa loudnorm qo'llanmaydi.
    loudnorm_target_lufs: float | None = None


class ReframeConfig(BaseModel):
    analysis_fps: float = 5.0  # TZ 4-bo'lim: 5 fps (sozlanadi)
    # R0: quyidagilar Reframe-Eval to'plamida tanlanadi.
    dead_zone: float = 0.06
    max_speed_per_s: float = 0.35
    one_euro_min_cutoff: float = 0.3
    one_euro_beta: float = 0.05
    cut_threshold: float = 0.25
    min_layout_hold_ms: int = 2_000
    face_top_third: bool = True


class Settings(BaseModel):
    data_dir: Path = Field(default_factory=default_data_dir)
    highlight: HighlightConfig = Field(default_factory=HighlightConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    reframe: ReframeConfig = Field(default_factory=ReframeConfig)
    safe_zone: SubtitleSafeZone = Field(default_factory=SubtitleSafeZone)
    allow_network: bool = False  # NFR-01: faqat model yuklash/yangilash uchun yoqiladi
    # V1-3 (TZ 19, ADR-0016): oflayn litsenziya kaliti. Tijorat qarori qabul qilinmaguncha O'CHIQ -
    # o'chiq bo'lsa hech narsa tekshirilmaydi/bloklanmaydi. Sinash uchun: LAHZA_LICENSING=1.
    licensing_enabled: bool = Field(default_factory=lambda: os.environ.get("LAHZA_LICENSING") == "1")

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "Models"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "Library"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "Logs"
