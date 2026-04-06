from __future__ import annotations

"""Build SynthTribe-style single-preset PRO-800 SysEx from a template + Pro800Patch.

Decoded byte offsets follow the community table:
https://github.com/samstaton/pro800/blob/main/pro800syx.md

Continuous 0..127 parameters are scaled to 0..16383 and stored little-endian uint16.
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
    """Inverse of _u16_le_from_midi127 (same 0..16383 scale as writes)."""
    if offset + 1 >= len(buf):
        return 64
    x = _u16_le_read(buf, offset)
    # Hardware often stores values >16383 in the pair; clamp to the same range we
    # use when writing from MIDI 0..127 so round-trip stays consistent.
    x = min(16383, x)
    return min(127, max(0, int(round(x / 16383.0 * 127.0))))


def apply_pro800_patch_to_decoded(decoded: bytearray, patch: Pro800Patch) -> None:
    """Overlay mapped parameters; leaves unlisted bytes (e.g. name) unchanged.

    Blends each written field with the template snapshot using max(mapped, template).
    That keeps audibility when the timbre map would land below a working preset's
    oscillator levels or sustain. Skips poly_mod (offset 43) until that offset is
    verified — it previously risked killing the voice.
    """
    p = patch.params_0_127
    snap = bytes(decoded)

    def blend(key: str, off: int, floor: int = 0) -> int:
        return max(int(p[key]), _midi127_from_u16_le(snap, off), floor)

    _u16_le_from_midi127(decoded, 19, blend("filter_cutoff", 19, 28))
    _u16_le_from_midi127(decoded, 21, blend("filter_resonance", 21))
    _u16_le_from_midi127(decoded, 23, blend("filter_env_amount", 23))
    _u16_le_from_midi127(decoded, 25, blend("filter_release", 25))
    _u16_le_from_midi127(decoded, 27, blend("filter_sustain", 27))
    _u16_le_from_midi127(decoded, 29, blend("filter_decay", 29))
    _u16_le_from_midi127(decoded, 31, blend("filter_attack", 31))
    _u16_le_from_midi127(decoded, 33, blend("amp_release", 33))
    _u16_le_from_midi127(decoded, 35, blend("amp_sustain", 35, 48))
    _u16_le_from_midi127(decoded, 37, blend("amp_decay", 37))
    _u16_le_from_midi127(decoded, 39, blend("amp_attack", 39))

    if len(decoded) > 48:
        _u16_le_from_midi127(decoded, 45, blend("lfo_rate", 45))
        _u16_le_from_midi127(decoded, 47, blend("lfo_depth", 47))
    if len(decoded) > 14:
        _u16_le_from_midi127(decoded, 7, blend("osc1_level", 7, 52))
        _u16_le_from_midi127(decoded, 13, blend("osc2_level", 13, 52))
    if len(decoded) > 83:
        _u16_le_from_midi127(decoded, 82, blend("osc_detune", 82))
    if len(decoded) > 143:
        _u16_le_from_midi127(decoded, 142, blend("noise_level", 142))


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
    apply_pro800_patch_to_decoded(buf, patch)
    new_wire = pack_pro800_7bit_payload(bytes(buf)) + rem
    return (
        bytes([0xF0])
        + _SYX_PREFIX
        + bytes([preset_index & 0x7F, 0x00])
        + new_wire
        + bytes([0xF7])
    )
