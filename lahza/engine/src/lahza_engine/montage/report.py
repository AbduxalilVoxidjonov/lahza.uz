"""Montaj hisoboti `<nom>_edl.json` (ADR-0013, docs/11 10.2).

Har chiqish kadrini manbasigacha kuzatish mumkin: qaysi fayl (yo'l, xesh), manbaning qaysi oralig'i,
montajning qaysi oralig'iga tushgani, qanday o'tish/effekt/rang qo'llangani va nega tanlangani.
Lahza yangi kadr generatsiya qilmaydi - hisobotda `"haqiqiy_kadr": true`.

Video trek timeline boshidan (0) boshlanadi (`MontageTimeline.item_starts()`); matn kartalari
(shu jumladan intro/outro `card`) video USTIDA chiziladi, videodan keyingi oraliq kartaning rangli
foni bilan to'ldiriladi. Davomiylik - `tl.duration_ms`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lahza_engine.montage.model import MontageTimeline

EDL_SCHEMA = "lahza.edl/1"

def _fx_entry(ref: Any) -> dict[str, Any]:
    from lahza_engine.fx.registry import FxError, get_plugin, validate_params

    entry: dict[str, Any] = {"plugin": ref.plugin, "at_ms": ref.at_ms, "dur_ms": ref.dur_ms,
                             "source": ref.source}
    try:
        m = get_plugin(ref.plugin)
        entry["name"] = m.name.get("uz")
        entry["kind"] = m.kind
        entry["params"] = validate_params(m, ref.params)
    except (KeyError, FxError) as e:
        entry["params"] = dict(ref.params)
        entry["error"] = str(e)
    return entry


def edl_report(tl: MontageTimeline) -> dict[str, Any]:
    """Montaj hisoboti (JSON'ga tayyor dict)."""
    starts = tl.item_starts()
    items = []
    used: dict[str, int] = {}
    for it, st in zip(tl.video, starts, strict=True):
        m = tl.media[it.media]
        used[m.id] = used.get(m.id, 0) + (it.src_out_ms - it.src_in_ms)
        items.append({
            "id": it.id,
            "role": it.role,
            "reason": it.reason,
            "user_edited": it.user_edited,
            "media": {"id": m.id, "path": m.path, "hash": m.hash, "origin": m.origin},
            "src_in_ms": it.src_in_ms,
            "src_out_ms": it.src_out_ms,
            "speed": it.speed,
            "out_start_ms": st,
            "out_end_ms": st + it.out_duration_ms,
            "reframe": it.reframe,
            "crop": it.crop.model_dump() if it.crop else None,
            "mute": it.mute,
            "volume_db": it.volume_db,
            "transition_in": (
                {"plugin": it.transition_in.plugin, "dur_ms": it.transition_in.dur_ms}
                if it.transition_in else None),
            "fx": [_fx_entry(f) for f in it.fx],
        })
    music = []
    for mu in tl.music:
        m = tl.media[mu.media]
        music.append({"media": {"id": m.id, "path": m.path, "hash": m.hash},
                      "src_in_ms": mu.src_in_ms, "start_ms": mu.start_ms, "end_ms": mu.end_ms,
                      "gain_db": mu.gain_db, "duck": mu.duck})
    return {
        "schema": EDL_SCHEMA,
        "timeline_schema": tl.schema_,
        "haqiqiy_kadr": True,
        "generativ": False,
        "format": tl.format.model_dump(),
        "duration_ms": tl.duration_ms,
        "sources": [
            {"id": m.id, "path": m.path, "hash": m.hash, "origin": m.origin,
             "used_ms": used.get(m.id, 0)}
            for m in tl.media.values() if m.id in used
        ],
        "items": items,
        "color": _fx_entry(tl.color) if tl.color else None,
        "text": [{"id": x.id, "kind": x.kind, "start_ms": x.start_ms, "end_ms": x.end_ms,
                  "text": x.text, "background": x.background} for x in tl.text],
        "music": music,
        "captions": {"enabled": tl.captions.enabled, "words": len(tl.captions.words),
                     "style": tl.captions.style.name},
        "brand": {"logo": Path(tl.brand.logo_path).name if tl.brand.logo_path else None,
                  "position": tl.brand.logo_position},
        "audio": tl.audio.model_dump(),
        "provenance": tl.provenance.model_dump(),
    }


def edl_path_for(video: Path) -> Path:
    return video.with_name(f"{video.stem}_edl.json")


def write_edl(tl: MontageTimeline, path: Path, extra: dict[str, Any] | None = None) -> Path:
    data = edl_report(tl)
    if extra:
        data["render"] = extra
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
