from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prompts"


class PromptTemplate(BaseModel):
    version: str
    system: str


def load_prompt(name: str, version: str = "v1") -> PromptTemplate:
    """Load a versioned system prompt from config/prompts/<version>/<name>.yaml.

    Prompts are data, not string literals in Python, so a prompt change
    is a diff to a YAML file (and trivially A/B-able by version) rather
    than a code change.
    """
    path = PROMPTS_DIR / version / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no prompt named {name!r} at version {version!r} ({path})")
    raw = yaml.safe_load(path.read_text())
    return PromptTemplate(**raw)
