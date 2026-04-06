from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sound_intents.resolver import (
    list_intent_ids,
    load_registry,
    normalize_phrase,
    resolve_in_registry,
)


def test_normalize_phrase() -> None:
    assert normalize_phrase("  E   Piano  ") == "e piano"


def test_resolve_e_piano_aliases_minimal_registry() -> None:
    reg = {
        "intents": {
            "electric_piano": {
                "aliases": ["e piano", "rhodes"],
                "patch_file": "presets/x.json",
                "syx_overlay": "patch_only",
            }
        }
    }
    assert resolve_in_registry("E Piano", reg)[0] == "electric_piano"
    assert resolve_in_registry("electric piano", reg)[0] == "electric_piano"
    assert resolve_in_registry("electric_piano", reg)[0] == "electric_piano"
    assert resolve_in_registry("Rhodes", reg)[0] == "electric_piano"


def test_resolve_unknown() -> None:
    reg = {"intents": {"electric_piano": {"aliases": ["x"], "patch_file": "a.json"}}}
    try:
        resolve_in_registry("lead synth", reg)
    except ValueError as e:
        assert "Unknown sound intent" in str(e)
        assert "electric_piano" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_list_intent_ids() -> None:
    reg = {"intents": {"b": {}, "a": {}}}
    assert list_intent_ids(reg) == ["a", "b"]


def test_load_real_registry() -> None:
    path = ROOT / "sound_intents" / "registry.json"
    if not path.is_file():
        return
    reg = load_registry(path)
    iid, meta = resolve_in_registry("tines", reg)
    assert iid == "electric_piano"
    assert meta.get("syx_overlay") == "patch_only"
    assert "patch_file" in meta


def _run() -> None:
    test_normalize_phrase()
    test_resolve_e_piano_aliases_minimal_registry()
    test_resolve_unknown()
    test_list_intent_ids()
    test_load_real_registry()
    print("test_sound_intents: ok")


if __name__ == "__main__":
    _run()
