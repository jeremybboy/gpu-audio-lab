from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


def unpack_pro800_7bit_payload(data: bytes) -> tuple[bytes, bytes]:
    """Expand PRO-800 7-bit SysEx packing to 8-bit bytes.

    Each group is eight bytes: one MSB-holding control byte followed by seven
    7-bit data bytes. Bit *j* (LSB = j=0) of the control byte is the high bit
    of data byte *j*. See community notes:
    https://github.com/samstaton/pro800/blob/main/pro800syx.md
    """
    out = bytearray()
    i = 0
    while i + 8 <= len(data):
        control = data[i]
        for j in range(7):
            out.append(data[i + 1 + j] | (((control >> j) & 1) << 7))
        i += 8
    remainder = data[i:]
    return bytes(out), remainder


def pack_pro800_7bit_payload(decoded: bytes) -> bytes:
    """Inverse of unpack: encode 8-bit patch bytes for SysEx (length must be ×7)."""
    if len(decoded) % 7 != 0:
        raise ValueError(
            f"decoded patch length must be a multiple of 7, got {len(decoded)}"
        )
    out = bytearray()
    for i in range(0, len(decoded), 7):
        chunk = decoded[i : i + 7]
        control = 0
        lows: list[int] = []
        for j, byte in enumerate(chunk):
            control |= ((byte >> 7) & 1) << j
            lows.append(byte & 0x7F)
        out.append(control)
        out.extend(lows)
    return bytes(out)


def decoded_patch_field_hints(decoded: bytes) -> dict:
    """Slice hints aligned to pro800syx.md table (decoded offsets, not wire bytes)."""
    hints: dict = {"decoded_length": len(decoded)}
    if len(decoded) > 4:
        v = decoded[4]
        hints["version_byte_at_decoded_offset_4"] = f"0x{v:02x}"
        if v == 0x6E:
            hints["version_note"] = "firmware ≤1.2.7 (per community table)"
        elif v == 0x6F:
            hints["version_note"] = "firmware ≥1.3.6 (per community table)"
    if len(decoded) > 21:
        hints["cutoff_bytes_decoded_offsets_19_20"] = decoded[19:21].hex()
        hints["resonance_bytes_decoded_offsets_21_22"] = decoded[21:23].hex()
    if len(decoded) > 40:
        hints["amp_env_release_slice_decoded_33_40"] = decoded[33:41].hex()
    return hints


@dataclass
class SysexPacket:
    index: int
    raw: bytes

    @property
    def length(self) -> int:
        return len(self.raw)

    @property
    def payload(self) -> bytes:
        # Header: F0 00 20 32 00 01 24 00 78 <index>
        return self.raw[11:-1]

    @property
    def tail_ascii(self) -> str:
        tail = self.payload[-20:]
        chars = [chr(x) if 32 <= x < 127 else " " for x in tail]
        return "".join(chars).strip()


def split_sysex_packets(blob: bytes) -> list[bytes]:
    packets: list[bytes] = []
    i = 0
    while i < len(blob):
        if blob[i] != 0xF0:
            i += 1
            continue
        j = i + 1
        while j < len(blob) and blob[j] != 0xF7:
            j += 1
        if j >= len(blob):
            break
        packets.append(blob[i : j + 1])
        i = j + 1
    return packets


def parse_pro800_dump(path: Path) -> list[SysexPacket]:
    blob = path.read_bytes()
    packets = split_sysex_packets(blob)
    out: list[SysexPacket] = []
    for raw in packets:
        if len(raw) < 12:
            continue
        if tuple(raw[1:9]) != (0x00, 0x20, 0x32, 0x00, 0x01, 0x24, 0x00, 0x78):
            # Keep parser conservative to expected dump family.
            continue
        out.append(SysexPacket(index=int(raw[9]), raw=raw))
    return out


def summarize_dump(path: Path, *, decode: bool = False) -> dict:
    packets = parse_pro800_dump(path)
    lens = Counter(p.length for p in packets)
    indexes = sorted({p.index for p in packets})
    preview = [
        {"index": p.index, "length": p.length, "tail_ascii": p.tail_ascii}
        for p in packets[:12]
    ]
    out: dict = {
        "path": str(path),
        "packet_count": len(packets),
        "unique_lengths": dict(sorted(lens.items())),
        "index_min": min(indexes) if indexes else None,
        "index_max": max(indexes) if indexes else None,
        "unique_index_count": len(indexes),
        "preview": preview,
    }
    if decode and packets:
        dec_parts: list[dict] = []
        for p in packets[:4]:
            raw_pl = p.payload
            dec, rem = unpack_pro800_7bit_payload(raw_pl)
            entry = {
                "packet_index": p.index,
                "wire_payload_length": len(raw_pl),
                "decoded_length": len(dec),
                "remainder_length": len(rem),
                "remainder_hex_preview": rem[:8].hex() if rem else "",
                "decoded_hex_head": dec[:24].hex(),
                **decoded_patch_field_hints(dec),
            }
            dec_parts.append(entry)
        out["decoded_preview"] = dec_parts
        out["decode_reference"] = (
            "https://github.com/samstaton/pro800/blob/main/pro800syx.md"
        )
    return out


def _packet_diff_positions(a: bytes, b: bytes) -> list[int]:
    limit = min(len(a), len(b))
    out = [i for i in range(limit) if a[i] != b[i]]
    if len(a) != len(b):
        out.extend(range(limit, max(len(a), len(b))))
    return out


def _compare_decoded_first_packets(pa: SysexPacket, pb: SysexPacket) -> dict:
    da, ra = unpack_pro800_7bit_payload(pa.payload)
    db, rb = unpack_pro800_7bit_payload(pb.payload)
    limit = min(len(da), len(db))
    diff_pos = [i for i in range(limit) if da[i] != db[i]]
    if len(da) != len(db):
        diff_pos.extend(range(limit, max(len(da), len(db))))
    cutoff_diff = None
    if len(da) > 21 and len(db) > 21:
        cutoff_diff = {
            "a": da[19:21].hex(),
            "b": db[19:21].hex(),
            "bytes_differ": da[19:21] != db[19:21],
        }
    return {
        "mode": "decoded_payload",
        "decode_reference": "https://github.com/samstaton/pro800/blob/main/pro800syx.md",
        "length_decoded_a": len(da),
        "length_decoded_b": len(db),
        "remainder_len_a": len(ra),
        "remainder_len_b": len(rb),
        "diff_byte_count_decoded": len(diff_pos),
        "first_diff_decoded_offsets": diff_pos[:24],
        "cutoff_decoded_offsets_19_20": cutoff_diff,
        "hints_a": decoded_patch_field_hints(da),
        "hints_b": decoded_patch_field_hints(db),
    }


def compare_dumps(path_a: Path, path_b: Path, *, decode: bool = False) -> dict:
    blob_a = path_a.read_bytes()
    blob_b = path_b.read_bytes()
    packets_a = parse_pro800_dump(path_a)
    packets_b = parse_pro800_dump(path_b)

    if decode and packets_a and packets_b:
        return {
            "file_a": str(path_a),
            "file_b": str(path_b),
            "sha256_a": hashlib.sha256(blob_a).hexdigest(),
            "sha256_b": hashlib.sha256(blob_b).hexdigest(),
            "identical_bytes": blob_a == blob_b,
            "decoded_compare_packet_0": _compare_decoded_first_packets(
                packets_a[0], packets_b[0]
            ),
        }

    changed_packets = []
    for i, (pa, pb) in enumerate(zip(packets_a, packets_b)):
        if pa.raw == pb.raw:
            continue
        diff_pos = _packet_diff_positions(pa.raw, pb.raw)
        changed_packets.append(
            {
                "packet_ordinal": i,
                "index_a": pa.index,
                "index_b": pb.index,
                "length_a": len(pa.raw),
                "length_b": len(pb.raw),
                "diff_byte_count": len(diff_pos),
                "first_diff_positions": diff_pos[:16],
            }
        )

    # If packet counts differ, include trailing packets as changed.
    if len(packets_a) != len(packets_b):
        longer = packets_a if len(packets_a) > len(packets_b) else packets_b
        side = "a" if len(packets_a) > len(packets_b) else "b"
        for j in range(min(len(packets_a), len(packets_b)), len(longer)):
            p = longer[j]
            changed_packets.append(
                {
                    "packet_ordinal": j,
                    f"index_{side}": p.index,
                    f"length_{side}": len(p.raw),
                    "diff_byte_count": len(p.raw),
                    "first_diff_positions": list(range(min(16, len(p.raw)))),
                }
            )

    return {
        "file_a": str(path_a),
        "file_b": str(path_b),
        "size_a": len(blob_a),
        "size_b": len(blob_b),
        "sha256_a": hashlib.sha256(blob_a).hexdigest(),
        "sha256_b": hashlib.sha256(blob_b).hexdigest(),
        "identical_bytes": blob_a == blob_b,
        "packet_count_a": len(packets_a),
        "packet_count_b": len(packets_b),
        "changed_packet_count": len(changed_packets),
        "changed_packets": changed_packets[:64],
    }

