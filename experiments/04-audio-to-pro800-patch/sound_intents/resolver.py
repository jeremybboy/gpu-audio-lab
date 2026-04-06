from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_phrase(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _intent_match_names(intent_id: str, meta: dict[str, Any]) -> list[str]:
    names = [intent_id, intent_id.replace("_", " ")]
    for a in meta.get("aliases", []):
        if isinstance(a, str):
            names.append(a)
    return names


def resolve_in_registry(describe: str, registry: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (intent_id, intent_meta) or raise ValueError."""
    q = normalize_phrase(describe)
    if not q:
        raise ValueError("describe must be non-empty")
    intents = registry.get("intents")
    if not isinstance(intents, dict):
        raise ValueError("registry missing valid 'intents' object")
    for intent_id, meta in intents.items():
        if not isinstance(meta, dict):
            continue
        for n in _intent_match_names(intent_id, meta):
            if normalize_phrase(n) == q:
                return str(intent_id), meta
    known = list_intent_ids(registry)
    raise ValueError(
        f"Unknown sound intent {describe!r}. Known intents: {', '.join(known)}"
    )


def list_intent_ids(registry: dict[str, Any]) -> list[str]:
    intents = registry.get("intents")
    if not isinstance(intents, dict):
        return []
    return sorted(intents.keys(), key=str.lower)


def load_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or Path(__file__).resolve().parent / "registry.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("registry must be a JSON object")
    if "intents" not in data:
        raise ValueError("registry.json must contain 'intents'")
    return data


def resolve_sound_intent(describe: str, *, registry_path: Path | None = None) -> tuple[str, dict[str, Any]]:
    reg = load_registry(registry_path)
    return resolve_in_registry(describe, reg)
