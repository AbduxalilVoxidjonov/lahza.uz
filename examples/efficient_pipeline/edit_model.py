"""Pure edits of lahza.timeline/1 dictionaries; no inference or engine dependency.

Span = half-open SOURCE milliseconds. Keep immutable original transcripts outside
the timeline; captions.words are disposable OUTPUT-time projections. Store the
previous dictionary for undo. Durations use MontageTimeline's round(ms / speed).
"""

from bisect import bisect_left
from copy import deepcopy
from math import isfinite

Span = tuple[int, int]


def ms(value: int) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("milliseconds must be nonnegative integers")
    return value


def merge_spans(spans: list[Span] | tuple[Span, ...]) -> list[Span]:
    merged: list[Span] = []
    for a, b in sorted(spans):
        if ms(a) >= ms(b):
            raise ValueError("expected nonempty half-open span")
        if merged and a <= merged[-1][1]:
            merged[-1] = merged[-1][0], max(b, merged[-1][1])
        else:
            merged.append((a, b))
    return merged


def keep_spans(bounds: Span, cuts: list[Span] | tuple[Span, ...]) -> list[Span]:
    """Export contract: sorted kept SOURCE spans; reject out-of-bounds cuts."""
    lo, hi = bounds
    merge_spans([bounds])
    kept = []
    for a, b in merge_spans(cuts):
        if a < bounds[0] or b > hi:
            raise ValueError("cut outside selected source bounds")
        if lo < a:
            kept.append((lo, a))
        lo = b
    return kept + ([(lo, hi)] if lo < hi else [])


def _finite(value):
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("nonfinite timeline value")
    if isinstance(value, dict):
        for item in value.values():
            _finite(item)
    if isinstance(value, list):
        for item in value:
            _finite(item)


def delete_source(timeline: dict, clip_id: str, cuts: list[Span] | tuple[Span, ...]) -> dict:
    """Split ONE occurrence, ripple OUTPUT overlays, return an independent snapshot.

    The first surviving fragment retains its ID; later IDs derive deterministically
    from the occurrence and source span. No transcript is edited. Crossing caption
    words are dropped, never shortened. Music is split with source offsets so it
    skips deleted output intervals rather than restarting. Sub-ms edits are refused.
    """
    _finite(timeline)
    if timeline.get("schema") != "lahza.timeline/1":
        raise ValueError("expected lahza.timeline/1")
    videos = timeline.get("video", [])
    ids = [v["id"] for v in videos]
    if not clip_id or len(set(ids)) != len(ids) or ids.count(clip_id) != 1:
        raise ValueError("one unique selected clip_id required")
    if any(v.get("transition_in") or v.get("fx") for v in videos):
        raise ValueError("transitions/FX need their own retiming adapter")
    pieces, new_video = [], []  # (old output start/end, new output start/end)
    old_t = new_t = 0
    used = set(ids)
    for video in videos:
        a, b = ms(video["src_in_ms"]), ms(video["src_out_ms"])
        speed = video.get("speed", 1.0)
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.25 <= speed <= 4:
            raise ValueError("speed must be finite and in [0.25, 4]")
        if a >= b or b > ms(timeline["media"][video["media"]]["duration_ms"]):
            raise ValueError("invalid video source bounds")
        duration = round((b - a) / speed)
        if duration < 1:
            raise ValueError("video duration rounds to zero output milliseconds")
        keeps = keep_spans((a, b), cuts) if video["id"] == clip_id else [(a, b)]
        if video["id"] == clip_id and any(
            round((lo - a) / speed) == round((hi - a) / speed) for lo, hi in merge_spans(cuts)
        ):
            raise ValueError("cut rounds to zero output milliseconds")
        for index, (lo, hi) in enumerate(keeps):
            start, end = old_t + round((lo - a) / speed), old_t + round((hi - a) / speed)
            length = round((hi - lo) / speed)
            if end <= start or length < 1:
                raise ValueError("edit cannot be represented at integer output milliseconds")
            item = deepcopy(video)
            if index:
                base = f"{clip_id}~{lo}-{hi}"
                name = base
                while name in used:
                    name += "~"
                item["id"] = name
                used.add(name)
            item.update(src_in_ms=lo, src_out_ms=hi)
            if video["id"] == clip_id and cuts:
                item["user_edited"] = True
            new_video.append(item)
            pieces.append((start, end, new_t, new_t + length))
            new_t += length
        old_t += duration
    if not new_video:
        raise ValueError("deleting the entire video track is unsupported")
    if not cuts:
        return deepcopy(timeline)

    ends, prefix = [p[1] for p in pieces], [0]
    for a, b, _, _ in pieces:
        prefix.append(prefix[-1] + b - a)

    def remap(t, coverage=False):
        index = bisect_left(ends, t)
        if index == len(pieces):
            return prefix[-1] if coverage else new_t
        a, b, c, d = pieces[index]
        offset = max(0, t - a)
        if coverage:
            return prefix[index] + offset
        return c + round(offset * (d - c) / (b - a))

    def bounds(item, music=False):
        a = ms(item["start_ms"])
        b = old_t if music and item.get("end_ms") is None else ms(item["end_ms"])
        if a >= b:
            raise ValueError("invalid output span")
        return a, b

    result = deepcopy(timeline)
    result["video"] = new_video
    for track in ("text", "stickers"):
        result[track] = []
        for item in timeline.get(track, []):
            a, b = bounds(item)
            if item.get("kind") == "card" and b > old_t:
                raise ValueError("card-extension semantics unsupported")
            c, d = remap(a), remap(b)
            if c < d:
                result[track].append({**deepcopy(item), "start_ms": c, "end_ms": d})
    captions = result.setdefault("captions", {})
    captions["words"] = []
    for word in timeline.get("captions", {}).get("words", []):
        a, b = bounds(word)
        coverage = remap(b, coverage=True) - remap(a, coverage=True)
        if coverage == b - a and remap(a) < remap(b):
            captions["words"].append({**deepcopy(word), "start_ms": remap(a), "end_ms": remap(b)})
    result["music"] = []
    for music in timeline.get("music", []):
        a, b = bounds(music, music=True)
        src = ms(music.get("src_in_ms", 0))
        media_duration = ms(timeline["media"][music["media"]]["duration_ms"])
        b = min(b, a + media_duration - src)
        if src >= media_duration:
            raise ValueError("music source offset outside media")
        runs = []
        for x, y, _, _ in pieces:
            lo, hi = max(a, x), min(b, y)
            if lo < hi:
                if runs and runs[-1][1] == lo:
                    runs[-1] = runs[-1][0], hi
                else:
                    runs.append((lo, hi))
        for lo, hi in runs:
            c, d = remap(lo), remap(hi)
            if c < d:
                result["music"].append(
                    {
                        **deepcopy(music),
                        "src_in_ms": src + lo - a,
                        "start_ms": c,
                        "end_ms": d,
                        "fade_in_ms": min(music.get("fade_in_ms", 500), d - c) if lo == a else 0,
                        "fade_out_ms": min(music.get("fade_out_ms", 1500), d - c) if hi == b else 0,
                    }
                )
    # duration_ms is derived in MontageTimeline, not part of its serialized schema.
    if "duration_ms" in result:
        result["duration_ms"] = new_t
    return result
