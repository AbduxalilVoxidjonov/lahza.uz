"""Video shablonlarni yuklash, tekshirish, import/eksport (`lahza.template/1`, docs/11 5.6).

* O'rnatilgan shablonlar - `templates/builtin/*.json` (paket ichida, faqat o'qiladi).
* Foydalanuvchi shablon fayli - xuddi shu sxemadagi bitta JSON obyekt: `{"schema": "lahza.template/1", ...}`.

Shablon - faqat ma'lumot (ADR-0011): unda yo'l, buyruq yoki FFmpeg ifodasi bo'lmaydi; plagin id'lari
fx reestri (`lahza_engine.fx.registry`) bo'yicha tekshiriladi.
"""

from __future__ import annotations

import functools
import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lahza_engine.templates.model import TEMPLATE_SCHEMA, Template

BUILTIN_DIR = Path(__file__).parent / "builtin"
MAX_FILE_BYTES = 256 * 1024
"""Shablon fayli kichik JSON; bundan kattasi - noto'g'ri fayl."""

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
PLACEHOLDERS = ("sarlavha", "shou", "cta")
MAX_TEXT_LEN = 300


class TemplateError(ValueError):
    """Shablonni o'qib/tekshirib bo'lmadi (foydalanuvchiga ko'rsatiladigan o'zbekcha xabar)."""


# --- fx reestri (RENDER agenti) --------------------------------------------------------------


def _registry() -> Any | None:
    """`lahza_engine.fx.registry` moduli yoki None (reestr hali yo'q bo'lsa - tekshiruv o'tkaziladi)."""
    try:
        from lahza_engine.fx import registry
    except ImportError:
        return None
    return registry


def fx_registry_available() -> bool:
    return _registry() is not None


def _check_plugin(reg: Any, plugin_id: str, kinds: tuple[str, ...], where: str,
                  params: dict[str, Any] | None = None) -> None:
    try:
        m = reg.get_plugin(plugin_id)
    except KeyError:
        raise TemplateError(f"{where}: '{plugin_id}' plagini o'rnatilmagan") from None
    kind = getattr(m, "kind", None)
    if kind is not None and kind not in kinds:
        raise TemplateError(f"{where}: '{plugin_id}' plagini turi '{kind}', kutilgan: {', '.join(kinds)}")
    validate = getattr(reg, "validate_params", None)
    if params and validate is not None:
        try:
            validate(m, dict(params))
        except (ValueError, TypeError, KeyError) as e:
            raise TemplateError(f"{where}: '{plugin_id}' parametrlari noto'g'ri: {e}") from None


# --- tekshirish ------------------------------------------------------------------------------


def _check_text(text: str, where: str) -> None:
    if not text.strip():
        raise TemplateError(f"{where}: matn bo'sh")
    if len(text) > MAX_TEXT_LEN:
        raise TemplateError(f"{where}: matn juda uzun ({len(text)} > {MAX_TEXT_LEN} belgi)")
    for m in _PLACEHOLDER_RE.finditer(text):
        name = m.group(1).split(":", 1)[0].strip()
        if name not in PLACEHOLDERS:
            raise TemplateError(
                f"{where}: noma'lum o'rinbosar '{{{name}}}' (ruxsat: {', '.join('{' + p + '}' for p in PLACEHOLDERS)})"
            )


def validate_template(t: Template, *, check_fx: bool = True) -> Template:
    """Pydantic tekshiruvidan tashqari qoidalar. Xato bo'lsa `TemplateError`.

    `check_fx` - plagin id'larini fx reestri bo'yicha tekshirish (reestr o'rnatilmagan bo'lsa o'tkaziladi).
    """
    if not _ID_RE.match(t.id):
        raise TemplateError(
            f"shablon id '{t.id}' noto'g'ri: faqat kichik lotin harflari, raqam, '.', '-', '_' (3-128 belgi)"
        )
    if not t.name.uz.strip():
        raise TemplateError("shablon nomi (uz) bo'sh")
    if t.target_duration_ms < t.min_shot_ms:
        raise TemplateError("maqsad davomiylik minimal kadr uzunligidan qisqa")
    for label, card in (("intro", t.intro), ("hook_text", t.hook_text), ("outro", t.outro)):
        if card is None:
            continue
        _check_text(card.text, label)
        if card.background is not None and not _HEX_RE.match(card.background):
            raise TemplateError(f"{label}: fon rangi #RRGGBB ko'rinishida bo'lishi kerak")
    intro_ms = t.intro.dur_ms if t.intro and t.intro.kind == "card" else 0
    outro_ms = t.outro.dur_ms if t.outro and t.outro.kind == "card" else 0
    if intro_ms + outro_ms >= t.target_duration_ms:
        raise TemplateError("intro va outro kartalari maqsad davomiylikdan uzun")
    for i, r in enumerate(t.fx):
        if r.trigger == "every_n" and not r.every_n:
            raise TemplateError(f"fx[{i}]: every_n trigger uchun every_n majburiy")
    if t.transition is not None and t.transition.dur_ms * 2 > t.min_shot_ms and t.transition.plugin != "uz.lahza.tr.cut":
        raise TemplateError("o'tish davomiyligi minimal kadr uzunligining yarmidan oshmasligi kerak")
    if check_fx:
        reg = _registry()
        if reg is not None:
            if t.transition is not None:
                _check_plugin(reg, t.transition.plugin, ("transition",), "o'tish", t.transition.params)
            if t.color:
                _check_plugin(reg, t.color, ("color",), "rang")
            for i, r in enumerate(t.fx):
                _check_plugin(reg, r.plugin, ("motion", "color", "text", "overlay", "audio", "speed"),
                              f"fx[{i}]", r.params)
    return t


def parse_template(data: Any, *, check_fx: bool = True) -> Template:
    """JSON obyektdan shablon (o'zbekcha `TemplateError` bilan)."""
    if not isinstance(data, dict):
        raise TemplateError("shablon JSON obyekt bo'lishi kerak")
    schema = data.get("schema")
    if schema != TEMPLATE_SCHEMA:
        raise TemplateError(f"bu Lahza video shabloni emas (schema '{schema}', kutilgan '{TEMPLATE_SCHEMA}')")
    try:
        t = Template.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(x) for x in first.get("loc", ())) or "shablon"
        raise TemplateError(f"shablon noto'g'ri ({loc}): {first.get('msg', '')}") from None
    return validate_template(t, check_fx=check_fx)


# --- o'rnatilgan shablonlar ------------------------------------------------------------------


@functools.cache
def _builtin_cached() -> tuple[Template, ...]:
    out: list[Template] = []
    for p in sorted(BUILTIN_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        # Fx tekshiruvi testda (reestr bilan); bu yerda reestrga bog'liqlik qo'yilmaydi.
        t = parse_template(data, check_fx=False)
        out.append(t.model_copy(update={"builtin": True}))
    return tuple(out)


def builtin_templates() -> list[Template]:
    """O'rnatilgan shablonlar (keshlangan; har chaqiruvda mustaqil nusxa)."""
    return [t.model_copy(deep=True) for t in _builtin_cached()]


def get_builtin(template_id: str) -> Template:
    for t in _builtin_cached():
        if t.id == template_id:
            return t.model_copy(deep=True)
    raise KeyError(template_id)


def is_builtin_id(template_id: str) -> bool:
    return any(t.id == template_id for t in _builtin_cached())


# --- fayl import/eksport ---------------------------------------------------------------------


def load_template_file(path: str | os.PathLike[str]) -> Template:
    """Foydalanuvchi shablon faylini o'qish. Natija har doim `builtin=False`."""
    p = Path(path)
    if not p.is_file():
        raise TemplateError(f"shablon fayli topilmadi: {p.name}")
    if p.stat().st_size > MAX_FILE_BYTES:
        raise TemplateError("shablon fayli juda katta")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise TemplateError("shablon fayli UTF-8 matn emas") from None
    except json.JSONDecodeError as e:
        raise TemplateError(f"shablon fayli JSON emas ({e.lineno}-qator)") from None
    t = parse_template(data)
    return t.model_copy(update={"builtin": False})


def save_template_file(t: Template, path: str | os.PathLike[str]) -> Path:
    """Shablonni faylga yozish (atomar). Eksport qilingan fayl `builtin=false` bo'ladi."""
    p = Path(path)
    data = t.model_copy(update={"builtin": False}).to_json()
    tmp = p.with_name(p.name + ".tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        raise TemplateError(f"shablonni yozib bo'lmadi: {e.strerror or e}") from None
    return p
