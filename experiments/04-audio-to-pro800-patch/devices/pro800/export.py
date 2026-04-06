from __future__ import annotations

import json
from pathlib import Path

from devices.pro800.schema import Pro800Patch
from devices.pro800.sysex_encode import build_single_preset_syx
from devices.pro800.sysex_tools import parse_pro800_dump


CC_MAP = {
    "osc1_level": 20,
    "osc2_level": 21,
    "noise_level": 22,
    "osc_detune": 23,
    "osc_mix_bias": 24,
    "filter_cutoff": 74,
    "filter_resonance": 71,
    "filter_env_amount": 25,
    "amp_attack": 73,
    "amp_decay": 75,
    "amp_sustain": 70,
    "amp_release": 72,
    "filter_attack": 26,
    "filter_decay": 27,
    "filter_sustain": 28,
    "filter_release": 29,
    "lfo_rate": 76,
    "lfo_depth": 77,
    "poly_mod_amount": 30,
}


def export_patch_json(patch: Pro800Patch, path: Path) -> Path:
    path.write_text(json.dumps(patch.to_dict(), indent=2), encoding="utf-8")
    return path


def export_patch_cc_stream(patch: Pro800Patch, path: Path, midi_channel: int = 0) -> Path:
    payload = []
    for key, value in patch.params_0_127.items():
        if key not in CC_MAP:
            continue
        payload.append({"channel": midi_channel, "cc": CC_MAP[key], "value": int(value)})
    path.write_text(json.dumps({"name": patch.name, "cc_stream": payload}, indent=2), encoding="utf-8")
    return path


def export_patch_syx_placeholder(patch: Pro800Patch, path: Path) -> Path:
    # Placeholder blob format for Phase 1 workflow validation.
    marker = [0xF0, 0x00, 0x20, 0x32, 0x7F, 0x01]
    body = [patch.params_0_127[k] & 0x7F for k in sorted(patch.params_0_127.keys())]
    syx = bytes(marker + body + [0xF7])
    path.write_bytes(syx)
    return path


def read_template_preset_index(template_path: Path) -> int:
    packets = parse_pro800_dump(template_path)
    if not packets:
        raise ValueError(f"No PRO-800 packet in template: {template_path}")
    return int(packets[0].index)


def export_patch_syx(
    patch: Pro800Patch,
    path: Path,
    *,
    template_path: Path | None = None,
    preset_index: int | None = None,
) -> Path:
    """Write `.syx`: real single-preset packet if *template_path* exists, else placeholder."""
    if template_path is not None and template_path.is_file():
        idx = (
            int(preset_index)
            if preset_index is not None
            else read_template_preset_index(template_path)
        )
        path.write_bytes(build_single_preset_syx(patch, template_path, idx))
        return path
    return export_patch_syx_placeholder(patch, path)

