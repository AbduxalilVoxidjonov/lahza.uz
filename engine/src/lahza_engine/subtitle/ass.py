"""ASS (Advanced SubStation Alpha) generatori - preview ham, render ham shu fayldan (ADR-0007).

Karaoke: har bir so'z faol bo'lgan oraliq uchun alohida Dialogue qatori yoziladi; faol so'z
highlight rangida (va "pop" rejimida biroz kattalashgan). Bu \\k "sweep"dan aniqroq va
so'z vaqtlari bilan bir xil ishlaydi.
"""

from __future__ import annotations

from lahza_engine.config import SubtitleSafeZone
from lahza_engine.subtitle.layout import CaptionChunk, chunk_words, max_chars_per_line
from lahza_engine.subtitle.style import StyleTemplate, ass_color
from lahza_engine.text.orthography import fold_for_match
from lahza_engine.text.translit import display_text
from lahza_engine.timeline import Timeline
from lahza_engine.types import Word


def ass_time(ms: int) -> str:
    ms = max(0, ms)
    cs = round(ms / 10)
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _alignment_and_margin(style: StyleTemplate, zone: SubtitleSafeZone, height: int) -> tuple[int, int]:
    if style.position == "lower":
        return 2, int(height * zone.bottom_pct)  # pastdan 35% band - interfeys
    if style.position == "upper":
        return 8, int(height * zone.top_pct)
    return 5, 0


def header(style: StyleTemplate, zone: SubtitleSafeZone, width: int, height: int) -> str:
    align, margin_v = _alignment_and_margin(style, zone, height)
    margin_lr = int(width * zone.side_pct)
    border_style = 3 if style.box else 1
    back = ass_color(style.box_color, 1 - style.box_opacity) if style.box else ass_color("#000000", 1.0)
    bold = -1 if style.bold else 0
    return "\n".join(
        [
            "[Script Info]",
            "; Lahza Studio tomonidan yaratilgan",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{style.font_family},{style.font_size},{ass_color(style.primary_color)},{ass_color(style.highlight_color)},{ass_color(style.outline_color)},{back},{bold},0,0,0,100,100,0,0,"
            f"{border_style},{style.outline_width},{style.shadow},{align},{margin_lr},{margin_lr},{margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


_EDGE_PUNCT = ".,!?…:;—-\"'«»“”„()[]ʻʼ‘’`"
POP_MS = 150
"""Pop animatsiyasi davomiyligi: so'z boshida pop_scale% dan 100% gacha (\\t)."""


def _fold_token(text: str) -> str:
    return fold_for_match(text).strip(_EDGE_PUNCT + " ")


def _fold_set(items: list[str]) -> frozenset[str]:
    return frozenset(f for f in (_fold_token(x) for x in items) if f)


def clean_words(words: list[Word], style: StyleTemplate) -> list[Word]:
    """To'ldiruvchi so'zlarni subtitrdan olib tashlaydi (video kesilmaydi)."""
    if not style.remove_fillers:
        return list(words)
    fillers = _fold_set(style.filler_words)
    return [w for w in words if _fold_token(w.text) not in fillers]


def mask_word(text: str) -> str:
    """Birinchi harfdan keyingi harflar '*': "ahmoq," -> "a****,"."""
    i, j = 0, len(text)
    while i < j and not text[i].isalnum():
        i += 1
    while j > i and not text[j - 1].isalnum():
        j -= 1
    core = text[i:j]
    if len(core) <= 1:
        return text
    return text[:i] + core[0] + "*" * (len(core) - 1) + text[j:]


class _Lexicon:
    def __init__(self, style: StyleTemplate) -> None:
        self.keywords = _fold_set(style.keywords)
        self.profanity = _fold_set(style.profanity_words) if style.mask_profanity else frozenset()

    def is_keyword(self, w: Word) -> bool:
        return bool(self.keywords) and _fold_token(w.text) in self.keywords

    def plain(self, w: Word, style: StyleTemplate) -> str:
        """Imlo rejimi/yozuv + so'kinish maskasi (registr va ASS ekranlashsiz)."""
        t = display_text(w.text, style.orthography, style.script)
        if self.profanity and _fold_token(w.text) in self.profanity:
            t = mask_word(t)
        return t


def _word_text(w: Word, style: StyleTemplate, lex: _Lexicon) -> str:
    t = lex.plain(w, style)
    return escape(t.upper() if style.uppercase else t)


def _render_chunk(chunk: CaptionChunk, active: Word | None, style: StyleTemplate,
                  lex: _Lexicon) -> str:
    hl = ass_color(style.highlight_color)
    prim = ass_color(style.primary_color)
    base_bold = 1 if style.bold else 0
    lines_out = []
    for line in chunk.lines:
        parts = []
        for w in line:
            txt = _word_text(w, style, lex)
            on: list[str] = []
            off: list[str] = []
            is_active = active is not None and w is active and style.animation != "none"
            keyword = lex.is_keyword(w)
            if is_active or keyword:
                on.append(f"\\c{hl}")
                off.append(f"\\c{prim}")
            if keyword:
                on.append("\\b1")
                off.append(f"\\b{base_bold}")
            if is_active and style.animation == "pop" and style.pop_scale > 100:
                p = style.pop_scale
                on.append(f"\\fscx{p}\\fscy{p}\\t(0,{POP_MS},\\fscx100\\fscy100)")
                off.append("\\fscx100\\fscy100")
            if on:
                parts.append("{" + "".join(on) + "}" + txt + "{" + "".join(off) + "}")
            else:
                parts.append(txt)
        lines_out.append(" ".join(parts))
    return "\\N".join(lines_out)


def map_words(words: list[Word], timeline: Timeline, offset_ms: int = 0) -> list[Word]:
    """Manba vaqtidagi so'zlar -> chiqish vaqti (o'chirilgan joydagilari tashlanadi).

    Hook prefiksi (PRO-3) bo'lsa, uning so'zlari chiqish boshida ikkinchi marta ham chiqadi.
    """
    mapped: list[Word] = []
    for w in words if timeline.prefix_ms else ():
        a, b = timeline.prefix_to_out(w.start_ms), timeline.prefix_to_out(w.end_ms)
        if a is not None and b is not None and b > a:
            mapped.append(w.model_copy(update={"start_ms": a - offset_ms, "end_ms": b - offset_ms}))
    for w in words:
        a, b = timeline.to_out(w.start_ms), timeline.to_out(w.end_ms)
        if a is None or b is None or b <= a:
            continue  # o'chirilgan joydagi so'z
        mapped.append(w.model_copy(update={"start_ms": a - offset_ms, "end_ms": b - offset_ms}))
    return mapped


def build_ass(
    words: list[Word],
    timeline: Timeline,
    style: StyleTemplate,
    zone: SubtitleSafeZone | None = None,
    width: int = 1080,
    height: int = 1920,
    offset_ms: int = 0,
) -> str:
    """Klipdagi so'zlardan (manba vaqtida) chiqish vaqtidagi ASS hujjati.

    offset_ms: chiqish vaqtidan ayiriladi (bitta kadrli preview uchun; tugagan qatorlar tashlanadi).
    """
    zone = zone or SubtitleSafeZone()
    lex = _Lexicon(style)
    mapped = map_words(clean_words(words, style), timeline)

    usable = width - 2 * int(width * zone.side_pct)
    chunks = chunk_words(
        mapped,
        max_words=style.max_words,
        max_lines=style.max_lines,
        max_chars=max_chars_per_line(style.font_size, usable),
    )
    events: list[str] = []

    def emit(start: int, end: int, text: str) -> None:
        start, end = start - offset_ms, end - offset_ms
        if end > 0 and end > start:
            events.append(_dialogue(start, end, text))

    for ci, chunk in enumerate(chunks):
        chunk_end = chunk.end_ms
        if ci + 1 < len(chunks):
            # Qisqa pauzalarda subtitr miltillamasin: keyingi bo'lakkacha ushlab turish (<= 400 ms).
            chunk_end = min(chunks[ci + 1].start_ms, chunk.end_ms + 400)
        if style.animation == "none":
            emit(chunk.start_ms, chunk_end, _render_chunk(chunk, None, style, lex))
            continue
        for wi, w in enumerate(chunk.words):
            start = w.start_ms if wi > 0 else chunk.start_ms
            end = chunk.words[wi + 1].start_ms if wi + 1 < len(chunk.words) else chunk_end
            emit(start, end, _render_chunk(chunk, w, style, lex))
    return header(style, zone, width, height) + "\n" + "\n".join(events) + "\n"


def _dialogue(start: int, end: int, text: str) -> str:
    return f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}"


def _cues(words: list[Word], timeline: Timeline, max_words: int,
          style: StyleTemplate | None) -> list[tuple[int, int, str]]:
    if style is not None:
        words = clean_words(words, style)
        lex = _Lexicon(style)
    chunks = chunk_words(map_words(words, timeline), max_words=max_words, max_lines=2, max_chars=42)
    out = []
    for c in chunks:
        if style is None:
            text = "\n".join(" ".join(w.text for w in line) for line in c.lines)
        else:
            text = "\n".join(" ".join(lex.plain(w, style) for w in line) for line in c.lines)
        out.append((c.start_ms, c.end_ms, text))
    return out


def _clock(ms: int, sep: str) -> str:
    h, rem = divmod(max(0, ms), 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, x = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{x:03d}"


def build_srt(words: list[Word], timeline: Timeline, max_words: int = 7,
              style: StyleTemplate | None = None) -> str:
    """Instagram/boshqa platformalar uchun oddiy SRT (TZ 9-bo'lim).

    style berilsa: imlo rejimi, to'ldiruvchi so'zlar va so'kinish maskasi qo'llanadi.
    """
    out = []
    for i, (a, b, text) in enumerate(_cues(words, timeline, max_words, style), 1):
        out.append(f"{i}\n{_clock(a, ',')} --> {_clock(b, ',')}\n{text}\n")
    return "\n".join(out)


def build_vtt(words: list[Word], timeline: Timeline, max_words: int = 7,
              style: StyleTemplate | None = None) -> str:
    """WebVTT (TZ 9-bo'lim: "SRT va VTT")."""
    out = ["WEBVTT", ""]
    for a, b, text in _cues(words, timeline, max_words, style):
        # VTT'da "-->" va bo'sh qator cue'ni buzadi.
        safe = text.replace("-->", "→")
        out.append(f"{_clock(a, '.')} --> {_clock(b, '.')}\n{safe}\n")
    return "\n".join(out)


# --- Montaj matn qatlami (TextItem: sarlavha, hook, CTA, lower-third, karta) -----------------

TEXT_KIND_STYLE: dict[str, tuple[str, float, bool]] = {
    # kind -> (ASS uslub nomi, shrift o'lchami ko'paytmasi (subtitr o'lchamiga nisbatan), quti)
    "card": ("Card", 1.35, False),
    "title": ("Title", 1.15, False),
    "hook": ("Hook", 1.2, True),
    "cta": ("Cta", 1.05, True),
    "lower_third": ("Lower", 0.75, True),
}
SLIDE_PX = 80
ANIM_MS = 250


def _text_style_line(name: str, style: StyleTemplate, size: int, box: bool, align: int,
                     margin_lr: int, margin_v: int) -> str:
    bold = -1 if style.bold else 0
    if box:
        back = ass_color(style.box_color, 1 - max(style.box_opacity, 0.6))
        border_style, outline = 3, max(8.0, style.outline_width)
        outline_col = back
    else:
        back = ass_color("#000000", 1.0)
        border_style, outline = 1, style.outline_width
        outline_col = ass_color(style.outline_color)
    return (f"Style: {name},{style.font_family},{size},{ass_color(style.primary_color)},"
            f"{ass_color(style.highlight_color)},{outline_col},{back},{bold},0,0,0,100,100,0,0,"
            f"{border_style},{outline},{style.shadow},{align},{margin_lr},{margin_lr},{margin_v},1")


def _text_anchor(position: str, kind: str, zone: SubtitleSafeZone, width: int,
                 height: int) -> tuple[int, int, int]:
    """(ASS alignment, x, y) - matn qatlami joyi (Instagram interfeysi zonasidan tashqarida)."""
    side = int(width * zone.side_pct)
    if kind == "lower_third":
        return 1, side, int(height * (1 - zone.bottom_pct)) - 20
    if position == "upper":
        return 8, width // 2, int(height * zone.top_pct) + 20
    if position == "lower":
        return 2, width // 2, int(height * (1 - zone.bottom_pct)) - 20
    return 5, width // 2, height // 2


def text_item_events(items: list, style: StyleTemplate, zone: SubtitleSafeZone | None = None,
                     width: int = 1080, height: int = 1920, offset_ms: int = 0
                     ) -> tuple[list[str], list[str]]:
    """Montaj TextItem'lari -> (qo'shimcha Style qatorlari, Dialogue qatorlari).

    `items` - `montage.model.TextItem` ro'yxati (vaqtlari chiqish vaqtida). Animatsiya:
    fade -> \\fad, pop -> \\fscx/\\t, slide_up -> \\move. Karta foni rendererda chiziladi.
    """
    zone = zone or SubtitleSafeZone()
    side = int(width * zone.side_pct)
    styles: dict[str, str] = {}
    events: list[str] = []
    for it in items:
        name, mult, box = TEXT_KIND_STYLE.get(it.kind, TEXT_KIND_STYLE["title"])
        size = it.font_size or max(24, round(style.font_size * mult))
        sname = f"{name}{size}"
        align, x, y = _text_anchor(it.position, it.kind, zone, width, height)
        if sname not in styles:
            styles[sname] = _text_style_line(sname, style, size, box, align, side, 0)
        tags = [f"\\an{align}"]
        if it.animation == "slide_up":
            tags.append(f"\\move({x},{y + SLIDE_PX},{x},{y},0,{ANIM_MS})\\fad({ANIM_MS},0)")
        else:
            tags.append(f"\\pos({x},{y})")
        if it.animation == "fade":
            tags.append(f"\\fad({ANIM_MS},{ANIM_MS})")
        elif it.animation == "pop":
            tags.append(f"\\fscx120\\fscy120\\t(0,{POP_MS},\\fscx100\\fscy100)")
        lines = [escape(display_text(x_, style.orthography, style.script))
                 for x_ in str(it.text).splitlines()]
        text = "\\N".join(x_ for x_ in lines if x_.strip()) or " "
        if style.uppercase and it.kind in ("hook", "cta"):
            text = text.upper()
        start, end = it.start_ms - offset_ms, it.end_ms - offset_ms
        if end > 0 and end > start:
            events.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},{sname},,0,0,0,,"
                          "{" + "".join(tags) + "}" + text)
    return list(styles.values()), events


def build_montage_ass(
    text_items: list,
    words: list[Word],
    style: StyleTemplate,
    zone: SubtitleSafeZone | None = None,
    width: int = 1080,
    height: int = 1920,
    offset_ms: int = 0,
) -> str:
    """Montaj uchun yagona ASS: subtitr so'zlari (chiqish vaqtida) + TextItem qatlamlari."""
    end = max([1, *(w.end_ms for w in words), *(t.end_ms for t in text_items)]) + 1000
    doc = build_ass(words, Timeline(0, end), style, zone, width, height, offset_ms=offset_ms)
    extra_styles, events = text_item_events(text_items, style, zone, width, height, offset_ms)
    if extra_styles:
        doc = doc.replace("\n\n[Events]", "\n" + "\n".join(extra_styles) + "\n\n[Events]", 1)
    if events:
        doc = doc.rstrip("\n") + "\n" + "\n".join(events) + "\n"
    return doc
