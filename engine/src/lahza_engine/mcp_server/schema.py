"""Tool `inputSchema` lari uchun minimal JSON Schema tekshiruvchi (bog'liqliksiz).

Faqat biz ishlatadigan qism: type, properties, required, additionalProperties, enum, minimum,
maximum, minLength, maxLength, pattern. Xato - aniq yo'l bilan matn.
"""

from __future__ import annotations

import re
from typing import Any

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
}


def _type_ok(value: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "null":
        return value is None
    return isinstance(value, _TYPES[t])


def validate(value: Any, schema: dict[str, Any], path: str = "arguments") -> list[str]:
    errors: list[str] = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            return [f"{path}: '{'/'.join(types)}' turi kutilgan"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {schema['enum']} dan biri bo'lishi kerak")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: >= {schema['minimum']} bo'lishi kerak")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: <= {schema['maximum']} bo'lishi kerak")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: kamida {schema['minLength']} belgi")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: ko'pi bilan {schema['maxLength']} belgi")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: format noto'g'ri")
    if isinstance(value, dict) and (t == "object" or "properties" in schema):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: majburiy maydon")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}.{key}: noma'lum maydon")
        for key, sub in props.items():
            if key in value:
                errors.extend(validate(value[key], sub, f"{path}.{key}"))
    return errors
