"""Validate and apply a complete plan to an isolated draft, never persisted state."""
import hashlib
import json
import math
import re

from lahza_engine.config import Settings
from lahza_engine.editing_agent.model import EditPlan, PreviewOut
from lahza_engine.fx.registry import get_plugin, validate_params
from lahza_engine.montage.model import Format, FxRef, MontageTimeline, TextItem
from lahza_engine.render.profiles import evaluate_timeline, get_profile
from lahza_engine.subtitle.style import StyleTemplate


class StalePlan(ValueError):
    pass


def revision(timeline: MontageTimeline, selected_video_id: str | None) -> str:
    data = {"timeline": timeline.to_json(), "selected_video_id": selected_video_id}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_timeline(tl: MontageTimeline, selection: str | None, settings: Settings | None = None) -> list[str]:
    # Revalidation also checks models constructed or modified outside Pydantic.
    MontageTimeline.model_validate(tl.to_json())
    StyleTemplate.model_validate(tl.captions.style.model_dump())
    if selection is not None and selection not in {v.id for v in tl.video}:
        raise ValueError("Selected video does not exist")
    fmt = tl.format
    if (fmt.w <= 0 or fmt.h <= 0 or not math.isfinite(fmt.fps) or fmt.fps <= 0
            or fmt.audio_hz <= 0):
        raise ValueError("Invalid output format")
    duration = tl.duration_ms

    def bounds(start, end, limit):
        if not 0 <= start < end <= limit:
            raise ValueError(f"Time range {start}..{end} is outside 0..{limit}")

    def fx(ref, limit, kind=None):
        manifest = get_plugin(ref.plugin)
        if kind and manifest.kind != kind:
            raise ValueError(f"{ref.plugin}: expected {kind} plugin")
        params = validate_params(manifest, ref.params, strict=True)
        for p in manifest.params:
            if p.type == "int" and p.id in ref.params and type(ref.params[p.id]) is not int:
                raise ValueError("FX integer parameters must be strict integers")
        end = ref.at_ms + (ref.dur_ms if ref.dur_ms is not None else
                           params["dur_ms"] if manifest.backend == "speed" else limit - ref.at_ms)
        bounds(ref.at_ms, end, limit)

    for i, clip in enumerate(tl.video):
        bounds(clip.src_in_ms, clip.src_out_ms, tl.media[clip.media].duration_ms)
        if clip.transition_in:
            tr = clip.transition_in
            manifest = get_plugin(tr.plugin)
            if manifest.kind != "transition":
                raise ValueError("Expected transition plugin")
            validate_params(manifest, tr.params, strict=True)
            if not 0 < tr.dur_ms <= min(clip.out_duration_ms, tl.video[i - 1].out_duration_ms):
                raise ValueError("Transition exceeds adjacent clips")
        for ref in clip.fx:
            fx(ref, clip.out_duration_ms)
    for item in [*tl.text, *tl.stickers, *tl.captions.words]:
        # Legacy overlays/ASR may extend past a later trim; preserve renderer semantics.
        bounds(item.start_ms, item.end_ms, max(duration, item.end_ms))
    for item in tl.text:
        if item.font_size is not None and not 24 <= item.font_size <= 200:
            raise ValueError("Text font size outside 24..200")
    for music in tl.music:
        end = music.end_ms if music.end_ms is not None else duration
        bounds(music.start_ms, end, duration)
        if not 0 <= music.src_in_ms < tl.media[music.media].duration_ms:
            raise ValueError("Music source time outside media")
        if music.fade_in_ms < 0 or music.fade_out_ms < 0:
            raise ValueError("Negative music fade")
    if tl.color:
        fx(tl.color, duration, "color")
    evaluation = evaluate_timeline(tl, settings or Settings())
    if evaluation.errors:
        raise ValueError("; ".join(evaluation.errors))
    return evaluation.warnings


def preview(timeline: MontageTimeline, plan: EditPlan, selected_video_id: str | None,
            settings: Settings | None = None) -> PreviewOut:
    # Also reject ambiguous plans constructed in-process without Pydantic validation.
    plan = EditPlan.model_validate(plan.model_dump(by_alias=True))
    if plan.base_revision != revision(timeline, selected_video_id):
        raise StalePlan("Timeline or selection changed; generate a new plan")
    if plan.unresolved:
        raise ValueError("Unresolved plan: " + "; ".join(plan.unresolved))
    draft = timeline.model_copy(deep=True)
    validate_timeline(draft, selected_video_id, settings)
    changes = []
    for command in plan.commands:
        args = command.args
        if command.tool == "set_format":
            profile = get_profile(args.profile)
            draft.target_platform = args.profile
            # Export presets change video geometry/rate, preserving the user's audio rate.
            recommended = profile.recommended_format.model_dump(exclude={"audio_hz"})
            draft.format = Format.model_validate({**draft.format.model_dump(), **recommended})
            changes.append(f"Set export profile to {args.profile}")
        elif command.tool == "set_captions":
            draft.captions.enabled = args.enabled
            if args.font_size is not None:
                draft.captions.style.font_size = args.font_size
            description = f"Captions {'enabled' if args.enabled else 'disabled'}"
            if args.font_size is not None:
                description += f"; font size {args.font_size}"
            changes.append(description)
        elif command.tool == "add_caption":
            if not 0 <= args.start_ms < args.end_ms <= draft.duration_ms:
                raise ValueError("New caption must fit within the output timeline")
            if not args.text.strip() or re.search(r"[{}\\]", args.text):
                raise ValueError("Caption must contain plain text")
            ids = {t.id for t in draft.text}
            number = 1
            while f"agent-caption-{number}" in ids:
                number += 1
            draft.text.append(TextItem(id=f"agent-caption-{number}", text=args.text,
                                       start_ms=args.start_ms, end_ms=args.end_ms,
                                       position="lower", kind="lower_third"))
            changes.append(f"Add caption: {args.text}")
        elif command.tool == "set_color":
            draft.color = FxRef(plugin=f"uz.lahza.color.{args.preset}", source="qolda")
            changes.append(f"Set color to {args.preset}")
        elif command.tool == "freeze_clip":
            clip = next((v for v in draft.video if v.id == args.clip_id), None)
            if clip is None:
                raise ValueError(f"Unknown clip: {args.clip_id}")
            end = args.at_ms + args.duration_ms
            if end > clip.out_duration_ms:
                raise ValueError("Freeze exceeds clip output duration")
            for ref in clip.fx:
                if ref.plugin == "uz.lahza.speed.freeze":
                    params = validate_params(get_plugin(ref.plugin), ref.params, strict=True)
                    existing_end = ref.at_ms + (ref.dur_ms if ref.dur_ms is not None else params["dur_ms"])
                    if args.at_ms < existing_end and ref.at_ms < end:
                        raise ValueError("Freeze overlaps an existing freeze")
            clip.user_edited = True
            clip.fx.append(FxRef(plugin="uz.lahza.speed.freeze", at_ms=args.at_ms,
                                 dur_ms=args.duration_ms, params={"dur_ms": args.duration_ms},
                                 source="qolda"))
            changes.append(f"Freeze {args.clip_id} at {args.at_ms}ms for {args.duration_ms}ms")
    warnings = validate_timeline(draft, selected_video_id, settings)
    return PreviewOut(timeline=draft, changes=changes, warnings=warnings)
