from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devices.pro800.sysex_tools import pack_pro800_7bit_payload, unpack_pro800_7bit_payload


def test_unpack_zero_control_preserves_low_seven_bits() -> None:
    group = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
    dec, rem = unpack_pro800_7bit_payload(group)
    assert rem == b""
    assert dec == bytes(range(1, 8))


def test_unpack_sets_high_bits_from_control_byte() -> None:
    # All seven data bytes zero; control has bits 0..6 set -> each output 0x80
    group = bytes([0x7F] + [0x00] * 7)
    dec, rem = unpack_pro800_7bit_payload(group)
    assert rem == b""
    assert dec == bytes([0x80] * 7)


def test_unpack_two_groups() -> None:
    g1 = bytes([0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # first byte 0x81
    g2 = bytes([0x00, 0x7F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    dec, rem = unpack_pro800_7bit_payload(g1 + g2)
    assert rem == b""
    assert dec[0] == 0x81
    assert dec[7] == 0x7F


def test_remainder_when_not_multiple_of_eight() -> None:
    dec, rem = unpack_pro800_7bit_payload(bytes([0x00, 0x01, 0x02]))
    assert dec == b""
    assert rem == bytes([0x00, 0x01, 0x02])


def test_pack_unpack_roundtrip_random_seven() -> None:
    import os

    decoded = os.urandom(14)
    wire = pack_pro800_7bit_payload(decoded)
    dec2, rem = unpack_pro800_7bit_payload(wire)
    assert rem == b""
    assert dec2 == decoded


def test_pack_unpack_roundtrip_preserves_wire_remainder() -> None:
    decoded = bytes(range(7, 14))  # 7 bytes
    wire_body = pack_pro800_7bit_payload(decoded) + bytes([0xAB, 0xCD])
    dec2, rem = unpack_pro800_7bit_payload(wire_body)
    assert dec2 == decoded
    assert rem == bytes([0xAB, 0xCD])
    assert pack_pro800_7bit_payload(dec2) + rem == wire_body


if __name__ == "__main__":
    test_unpack_zero_control_preserves_low_seven_bits()
    test_unpack_sets_high_bits_from_control_byte()
    test_unpack_two_groups()
    test_remainder_when_not_multiple_of_eight()
    test_pack_unpack_roundtrip_random_seven()
    test_pack_unpack_roundtrip_preserves_wire_remainder()
    print("sysex decode tests passed.")
