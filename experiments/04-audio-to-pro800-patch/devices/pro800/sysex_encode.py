from __future__ import annotations

"""Build SynthTribe-style single-preset PRO-800 SysEx from a template + Pro800Patch.

Decoded byte offsets follow the community table:
https://github.com/samstaton/pro800/blob/main/pro800syx.md

Continuous 0..127 parameters are stored as little-endian uint16. Firmware 0x6F often uses
the **full 0..65535** range in templates (e.g. osc levels 0xFFFF); mapping only to 0..16383
collapses those values and can silence the patch — see apply path below.
"""

from pathlib import Path

from devices.pro800.schema import Pro800Patch
from devices.pro800.sysex_tools import (
    pack_pro800_7bit_payload,
    parse_pro800_dump,
    unpack_pro800_7bit_payload,
)

# Bytes 1..8 after F0 in single-preset exports we have seen.
_SYX_PREFIX = bytes([0x00, 0x20, 0x32, 0x00, 0x01, 0x24, 0x00, 0x78])


def _u16_le_from_midi127(buf: bytearray, offset: int, value: int) -> None:
    if offset + 1 >= len(buf):
        return
    v = max(0, min(127, int(value)))
    x = int(round(v / 127.0 * 16383)) & 0xFFFF
    buf[offset] = x & 0xFF
    buf[offset + 1] = (x >> 8) & 0xFF


def _u16_le_read(buf: bytes, offset: int) -> int:
    if offset + 1 >= len(buf):
        return 0
    return int(buf[offset]) | (int(buf[offset + 1]) << 8)


def _u16_le_write(buf: bytearray, offset: int, value: int) -> None:
    if offset + 1 >= len(buf):
        return
    x = max(0, min(0xFFFF, int(value)))
    buf[offset] = x & 0xFF
    buf[offset + 1] = (x >> 8) & 0xFF


def _midi127_from_u16_le(buf: bytes, offset: int) -> int:
    """Inverse of _u16_le_from_midi127 (0..16383 wire range — legacy / tweak-syx)."""
    if offset + 1 >= len(buf):
        return 64
    x = _u16_le_read(buf, offset)
    x = min(16383, x)
    return min(127, max(0, int(round(x / 16383.0 * 127.0))))


def _u16_le_from_midi127_hw(buf: bytearray, offset: int, value: int) -> None:
    """Map MIDI 0..127 to uint16 0..65535 (matches typical 0x6F preset span)."""
    if offset + 1 >= len(buf):
        return
    v = max(0, min(127, int(value)))
    x = int(round(v / 127.0 * 65535.0)) & 0xFFFF
    buf[offset] = x & 0xFF
    buf[offset + 1] = (x >> 8) & 0xFF


def _midi127_from_u16_le_hw(buf: bytes, offset: int) -> int:
    """Template read for blend: invert _u16_le_from_midi127_hw."""
    if offset + 1 >= len(buf):
        return 64
    x = min(65535, _u16_le_read(buf, offset))
    return min(127, max(0, int(round(x / 65535.0 * 127.0))))


def apply_pro800_patch_to_decoded(
    decoded: bytearray,
    patch: Pro800Patch,
    *,
    overlay: str = "blend_max",
) -> None:
    """Overlay mapped parameters; leaves unlisted bytes (e.g. name) unchanged.

    *overlay* ``blend_max``: per field, MIDI value is max(mapped, template, floor).
    Use for timbre-driven exports so template levels are not crushed.

    *overlay* ``patch_only``: write mapped MIDI only (with floors); use when morphing
    from a known template (e.g. bass → e-piano) so resonance/cutoff can go **down**
    as well as up. Writes use 0..65535 uint16 span (0x6F presets).

    Skips poly_mod (offset 43) until verified.
    """
    if overlay not in ("blend_max", "patch_only"):
        raise ValueError(f"unknown overlay mode: {overlay!r}")
    p = patch.params_0_127
    snap = bytes(decoded)

    def midi_for(key: str, off: int, floor: int = 0) -> int:
        v = max(0, min(127, int(p[key])))
        if overlay == "patch_only":
            return max(floor, v)
        tmpl = _midi127_from_u16_le_hw(snap, off)
        return max(v, tmpl, floor)

    _u16_le_from_midi127_hw(decoded, 19, midi_for("filter_cutoff", 19, 28))
    _u16_le_from_midi127_hw(decoded, 21, midi_for("filter_resonance", 21))
    _u16_le_from_midi127_hw(decoded, 23, midi_for("filter_env_amount", 23))
    _u16_le_from_midi127_hw(decoded, 25, midi_for("filter_release", 25))
    _u16_le_from_midi127_hw(decoded, 27, midi_for("filter_sustain", 27))
    _u16_le_from_midi127_hw(decoded, 29, midi_for("filter_decay", 29))
    _u16_le_from_midi127_hw(decoded, 31, midi_for("filter_attack", 31))
    _u16_le_from_midi127_hw(decoded, 33, midi_for("amp_release", 33))
    _u16_le_from_midi127_hw(decoded, 35, midi_for("amp_sustain", 35, 48))
    _u16_le_from_midi127_hw(decoded, 37, midi_for("amp_decay", 37))
    _u16_le_from_midi127_hw(decoded, 39, midi_for("amp_attack", 39))

    if len(decoded) > 48:
        _u16_le_from_midi127_hw(decoded, 45, midi_for("lfo_rate", 45))
        _u16_le_from_midi127_hw(decoded, 47, midi_for("lfo_depth", 47))
    if len(decoded) > 14:
        _u16_le_from_midi127_hw(decoded, 7, midi_for("osc1_level", 7, 52))
        _u16_le_from_midi127_hw(decoded, 13, midi_for("osc2_level", 13, 52))
    if len(decoded) > 83:
        _u16_le_from_midi127_hw(decoded, 82, midi_for("osc_detune", 82))
    if len(decoded) > 143:
        _u16_le_from_midi127_hw(decoded, 142, midi_for("noise_level", 142))


def build_syx_from_template_tweak(
    template_path: Path,
    *,
    cutoff_raw_delta: int = 0,
    resonance_raw_delta: int = 0,
    cutoff_u16: int | None = None,
    preset_index: int | None = None,
) -> bytes:
    """Copy a SynthTribe single-preset file and nudge decoded uint16 fields.

    Use *raw* deltas on the wire pair (little-endian uint16 at offsets 19 and 21).
    MIDI-style (+/- 12) scaling was unsafe: firmware 0x6F presets often store values
    above the 0..16383 range we use for 0..127 mapping; re-encoding via MIDI corrupted
    the packet and could silence the voice in SynthTribe.
    """
    packets = parse_pro800_dump(template_path)
    if not packets:
        raise ValueError(f"No PRO-800 SysEx packet found in {template_path}")
    src = packets[0]
    wire = src.payload
    dec, rem = unpack_pro800_7bit_payload(wire)
    if len(dec) % 7 != 0:
        raise ValueError(
            f"Template decoded length {len(dec)} is not a multiple of 7; choose another export"
        )
    idx = int(preset_index) if preset_index is not None else int(src.index)
    buf = bytearray(dec)

    if cutoff_u16 is not None:
        _u16_le_write(buf, 19, int(cutoff_u16))
    elif cutoff_raw_delta:
        cur = _u16_le_read(bytes(buf), 19)
        _u16_le_write(buf, 19, cur + int(cutoff_raw_delta))
    if resonance_raw_delta:
        cur = _u16_le_read(bytes(buf), 21)
        _u16_le_write(buf, 21, cur + int(resonance_raw_delta))

    new_wire = pack_pro800_7bit_payload(bytes(buf)) + rem
    return (
        bytes([0xF0])
        + _SYX_PREFIX
        + bytes([idx & 0x7F, 0x00])
        + new_wire
        + bytes([0xF7])
    )


def build_single_preset_syx(
    patch: Pro800Patch,
    template_path: Path,
    preset_index: int,
    *,
    overlay: str = "blend_max",
) -> bytes:
    """Clone wire layout from *template_path*, apply *patch*, set program index."""
    packets = parse_pro800_dump(template_path)
    if not packets:
        raise ValueError(f"No PRO-800 SysEx packet found in {template_path}")
    src = packets[0]
    wire = src.payload
    dec, rem = unpack_pro800_7bit_payload(wire)
    if len(dec) % 7 != 0:
        raise ValueError(
            f"Template decoded length {len(dec)} is not a multiple of 7; choose another export"
        )
    buf = bytearray(dec)
    apply_pro800_patch_to_decoded(buf, patch, overlay=overlay)
    new_wire = pack_pro800_7bit_payload(bytes(buf)) + rem
    return (
        bytes([0xF0])
        + _SYX_PREFIX
        + bytes([preset_index & 0x7F, 0x00])
        + new_wire
        + bytes([0xF7])
    )
