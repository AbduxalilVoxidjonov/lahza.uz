"""Strict public editing contract; times are integer output milliseconds."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lahza_engine.montage.model import MontageTimeline


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class FormatArgs(Strict):
    profile: Literal["instagram_reels", "youtube_shorts", "youtube_video"] = Field(
        description="Export video preset: instagram_reels/ youtube_shorts = vertical 9:16; youtube_video = wide 16:9. Preserve audio rate.")


class CaptionsArgs(Strict):
    enabled: bool = Field(description="Final caption visibility. Uzbek yoq/yoqib = true; o'chir/o‘chir = false. Preserve current visibility if only size is requested.")
    font_size: int | None = Field(None, ge=24, le=200,
        description="Final absolute font size in pixels (24..200), never a delta. Null preserves size. Resolve kattaroq/kichikroq using current captions.font_size.")


class CaptionArgs(Strict):
    text: str = Field(min_length=1, max_length=500, pattern=r"^[^{}\\\x00-\x08\x0b-\x1f]+$")
    start_ms: int = Field(ge=0, description="Caption start in absolute timeline output milliseconds.")
    end_ms: int = Field(gt=0, description="Caption end, greater than start and no later than timeline duration.")


class ColorArgs(Strict):
    preset: Literal["warm", "cool", "bw", "vivid", "film"] = Field(
        description="warm = iliq/iliqroq (warmer); cool = sovuq/sovuqroq; vivid = yorqin (more saturated); film = kino; bw = oq-qora (black and white).")


class FreezeArgs(Strict):
    clip_id: str = Field(min_length=1, max_length=128, description="Exact existing clip ID; tanlangan klip means context.selected_video_id.")
    at_ms: int = Field(ge=0, description="Freeze start in clip LOCAL OUTPUT milliseconds; 7-soniyasidan = 7000, independent of source offsets and timeline clip start.")
    duration_ms: int = Field(ge=100, le=5000, description="Freeze length in milliseconds, 100..5000; 1 soniya = 1000. Start + length must fit clip output and avoid existing freezes.")


class SetFormat(Strict):
    tool: Literal["set_format"]
    args: FormatArgs


class SetCaptions(Strict):
    tool: Literal["set_captions"]
    args: CaptionsArgs


class AddCaption(Strict):
    tool: Literal["add_caption"]
    args: CaptionArgs


class SetColor(Strict):
    tool: Literal["set_color"]
    args: ColorArgs


class FreezeClip(Strict):
    tool: Literal["freeze_clip"]
    args: FreezeArgs


Command = Annotated[SetFormat | SetCaptions | AddCaption | SetColor | FreezeClip,
                    Field(discriminator="tool")]
OPERATIONS = ["set_format", "set_captions", "add_caption", "set_color", "freeze_clip"]


class Proposal(Strict):
    commands: list[Command] = Field(max_length=12, description="Only requested edits; at most one each of set_format, set_captions, set_color. Combine visibility and size in one set_captions.")
    unresolved: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=12)


    @model_validator(mode="after")
    def _singleton_commands(self):
        seen = set()
        for command in self.commands:
            if command.tool in {"set_format", "set_captions", "set_color"}:
                if command.tool in seen:
                    raise ValueError(f"Ambiguous editing output: duplicate/conflicting {command.tool}; return one final command per setting")
                seen.add(command.tool)
        return self


class EditPlan(Proposal):
    schema_: Literal["lahza.edit-plan/1"] = Field(alias="schema")
    base_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class PlanIn(Strict):
    prompt: str = Field(min_length=1, max_length=2000)
    timeline: MontageTimeline
    selected_video_id: str | None = None
    planner: Literal["local", "claude"] = "local"


class PreviewIn(Strict):
    timeline: MontageTimeline
    plan: EditPlan
    selected_video_id: str | None = None


class PreviewOut(Strict):
    timeline: MontageTimeline
    changes: list[str]
    warnings: list[str]


class PlanOut(Strict):
    plan: EditPlan
    changes: list[str]
    warnings: list[str]
    model_id: str
    planner: Literal["local", "claude"] = "local"


class Status(Strict):
    available: bool
    reason: str | None
    model_id: str | None
    supported_operations: list[str]
