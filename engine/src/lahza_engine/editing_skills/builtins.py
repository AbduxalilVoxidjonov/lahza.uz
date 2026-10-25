"""Original bundled, inspectable data-only examples."""
from pathlib import Path

from .model import Skill

BUILTIN_DIR = Path(__file__).parent / "builtin"


def builtins() -> list[Skill]:
    return [Skill.model_validate_json(p.read_bytes()) for p in sorted(BUILTIN_DIR.glob("*.json"))]
