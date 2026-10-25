"""Transform a copy, validate it, then publish one atomic SQLite update."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException

from lahza_engine.fx.registry import get_plugin, validate_params
from lahza_engine.montage.model import FxRef, MontageTimeline, StickerItem, TextItem

from .model import Caption, Color, Freeze, Motion, Skill, Sticker, safe_asset
from .store import LOCK, SkillStore


def transform(tl: MontageTimeline, skill: Skill, assets: Path, retained: Path,
              title: str, video_id: str | None, start_ms: int) -> MontageTimeline:
    result = tl.model_copy(deep=True)
    if not result.video:
        raise ValueError("Target montage needs a video item")
    index = next((i for i, v in enumerate(result.video) if v.id == video_id), None) if video_id else 0
    if index is None:
        raise ValueError("Target video not found")
    video = result.video[index]
    if start_ms >= video.out_duration_ms:
        raise ValueError("start_ms must be inside the target video")
    absolute = result.item_starts()[index]
    for action in skill.actions:
        if isinstance(action, Color):
            plugin = "uz.lahza.color." + action.preset
            params = validate_params(get_plugin(plugin), {}, strict=True)
            result.color = FxRef(plugin=plugin, params=params, source="qolda")
            continue
        at = start_ms + action.at_ms
        duration = min(action.duration_ms, video.out_duration_ms - at)
        if duration <= 0:
            raise ValueError("An action starts outside the target video")
        uid = "skill-" + uuid.uuid4().hex
        if isinstance(action, Caption):
            text = action.text.replace("{title}", title)
            if not text.strip() or len(text) > 500:
                raise ValueError("Caption needs a nonempty title, up to 500 characters after substitution")
            result.text.append(TextItem(id=uid, start_ms=absolute + at, end_ms=absolute + at + duration,
                                        text=text, position=action.position, animation=action.animation))
        elif isinstance(action, (Freeze, Motion)):
            if isinstance(action, Freeze):
                if duration < 100:
                    raise ValueError("Freeze needs at least 100 ms remaining")
                plugin, params = "uz.lahza.speed.freeze", {"dur_ms": duration}
            else:
                plugin, params = "uz.lahza.motion." + action.preset, {}
            checked = validate_params(get_plugin(plugin), params, strict=True)
            video.fx.append(FxRef(plugin=plugin, at_ms=at, dur_ms=duration, params=checked, source="qolda"))
            video.user_edited = True
        elif isinstance(action, Sticker):
            from lahza_engine.stickers import inspect_sticker
            relative = safe_asset(action.asset)
            asset = assets / relative
            if asset.is_symlink() or not asset.resolve().is_relative_to(assets.resolve()):
                raise ValueError("Unsafe skill asset")
            inspect_sticker(str(asset))
            # Montage-owned copies survive uninstall/replacement. Never copy arbitrary paths.
            retained.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(asset.read_bytes()).hexdigest()
            dest = retained / (digest + asset.suffix)
            if dest.is_symlink():
                raise ValueError("Unsafe retained asset")
            if not dest.exists():
                temp = retained / ("." + uuid.uuid4().hex)
                try:
                    shutil.copyfile(asset, temp)
                    temp.replace(dest)
                finally:
                    temp.unlink(missing_ok=True)
            params = action.model_dump(exclude={"type", "asset", "at_ms", "duration_ms"})
            result.stickers.append(StickerItem(id=uid, path=str(dest), start_ms=absolute + at,
                                               end_ms=absolute + at + duration, **params))
    result.provenance.notes.append(f"Editing skill {skill.id}@{skill.version}")
    return MontageTimeline.model_validate(result.to_json())


def apply_saved(state, sid: str, montage_id: str, title: str = "", video_id: str | None = None,
                start_ms: int = 0, expected_timeline: str | None = None) -> dict:
    from lahza_engine.api.routes_montage import montage_dir
    # Match the existing State DB lock. Transaction includes read + validation + write.
    with LOCK, state.lib_lock, state.library:
        store = SkillStore(state.settings.data_dir)
        skill = store.load(sid)
        rows = state.lib("SELECT * FROM montages WHERE id = ?", (montage_id,))
        if not rows:
            raise HTTPException(404, "Montage not found")
        row = rows[0]
        if row["status"] != "ready" or not row["timeline_json"]:
            raise HTTPException(409, "Only saved ready montages support editing skills")
        if expected_timeline is not None and hashlib.sha256(row["timeline_json"].encode()).hexdigest() != expected_timeline:
            raise HTTPException(409, "Montage changed; refresh before applying")
        result = transform(MontageTimeline.model_validate_json(row["timeline_json"]), skill,
                           store.directory(sid), montage_dir(state, montage_id) / "skill-assets",
                           title, video_id, start_ms)
        state.library.execute(
            "UPDATE montages SET timeline_json = ?, duration_ms = ?, user_edited = 1,"
            " updated_at = datetime('now') WHERE id = ?",
            (result.model_dump_json(by_alias=True), result.duration_ms, montage_id))
    return {"ok": True, "timeline": result.to_json(), "user_edited": True}
