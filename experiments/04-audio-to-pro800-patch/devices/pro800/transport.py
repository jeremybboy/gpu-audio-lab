from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import mido

from devices.pro800.export import CC_MAP
from devices.pro800.schema import Pro800Patch


def list_midi_outputs() -> list[str]:
    return list(mido.get_output_names())


def list_midi_inputs() -> list[str]:
    return list(mido.get_input_names())


def resolve_output_port(
    preferred: Optional[str] = None,
    *,
    exact_name: Optional[str] = None,
) -> str:
    outputs = list_midi_outputs()
    if not outputs:
        raise RuntimeError("No MIDI output ports available.")
    if exact_name is not None:
        if exact_name in outputs:
            return exact_name
        lines = "\n  ".join(outputs)
        raise RuntimeError(
            f"MIDI output {exact_name!r} not found. Available outputs:\n  {lines}"
        )
    if preferred:
        for name in outputs:
            if preferred in name:
                return name
        raise RuntimeError(f"No MIDI output matching '{preferred}'. Available: {outputs}")
    for name in outputs:
        if "PRO 800" in name.upper():
            return name
    return outputs[0]


_MIDI_OUTPUT_OPEN_HELP = (
    "Could not open MIDI output (Windows: MidiOutWinMM::openPort).\n"
    "Common fix: quit SynthTribe, your DAW, and any other app using the PRO-800, "
    "then retry. Only one program can hold the port at a time.\n"
    "Also try: unplug/replug USB, power-cycle the PRO-800.\n"
)


def resolve_input_port(preferred: Optional[str] = None) -> str:
    inputs = list_midi_inputs()
    if not inputs:
        raise RuntimeError("No MIDI input ports available.")
    if preferred:
        for name in inputs:
            if preferred in name:
                return name
        raise RuntimeError(f"No MIDI input matching '{preferred}'. Available: {inputs}")
    for name in inputs:
        if "PRO 800" in name.upper():
            return name
    return inputs[0]


def patch_to_cc_messages(patch: Pro800Patch, midi_channel: int = 0) -> list[mido.Message]:
    messages: list[mido.Message] = []
    for key, value in patch.params_0_127.items():
        if key not in CC_MAP:
            continue
        messages.append(
            mido.Message(
                "control_change",
                channel=int(midi_channel),
                control=int(CC_MAP[key]),
                value=int(max(0, min(127, int(value)))),
            )
        )
    return messages


def parse_slot_to_program(slot: str) -> int:
    s = slot.strip().upper()
    # Accept forms like "A-03", "A03", "03", "3".
    if s.startswith("A-"):
        s = s[2:]
    elif s.startswith("A"):
        s = s[1:]
    try:
        n = int(s)
    except ValueError as exc:
        raise RuntimeError(f"Invalid slot '{slot}'. Expected A-01..A-100 or numeric.") from exc
    if n < 1 or n > 100:
        raise RuntimeError(f"Invalid slot '{slot}'. Range is 1..100.")
    return n - 1


def select_program(
    program_index: int,
    midi_channel: int = 0,
    output_port_contains: Optional[str] = None,
) -> str:
    if program_index < 0 or program_index > 127:
        raise RuntimeError(f"Program index out of range: {program_index} (must be 0..127).")
    port_name = resolve_output_port(output_port_contains)
    with mido.open_output(port_name) as port:
        port.send(
            mido.Message(
                "program_change",
                channel=int(midi_channel),
                program=int(program_index),
            )
        )
    return port_name


def send_patch_cc(
    patch: Pro800Patch,
    midi_channel: int = 0,
    output_port_contains: Optional[str] = None,
) -> str:
    port_name = resolve_output_port(output_port_contains)
    messages = patch_to_cc_messages(patch, midi_channel=midi_channel)
    with mido.open_output(port_name) as port:
        # Safety message: all notes off before parameter updates.
        port.send(mido.Message("control_change", channel=int(midi_channel), control=123, value=0))
        for msg in messages:
            port.send(msg)
    return port_name


def apply_patch_to_slot(
    patch: Pro800Patch,
    slot: str,
    midi_channel: int = 0,
    output_port_contains: Optional[str] = None,
    settle_ms: int = 120,
) -> tuple[str, int]:
    program_index = parse_slot_to_program(slot)
    port_name = resolve_output_port(output_port_contains)
    messages = patch_to_cc_messages(patch, midi_channel=midi_channel)
    with mido.open_output(port_name) as port:
        port.send(mido.Message("program_change", channel=int(midi_channel), program=program_index))
        if settle_ms > 0:
            time.sleep(float(settle_ms) / 1000.0)
        port.send(mido.Message("control_change", channel=int(midi_channel), control=123, value=0))
        for msg in messages:
            port.send(msg)
    return port_name, program_index


def _read_syx_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if not raw:
        raise RuntimeError(f"SysEx file is empty: {path}")
    # Many .syx files are concatenated SysEx packets. We send packet-by-packet.
    if raw[0] != 0xF0 or raw[-1] != 0xF7:
        raise RuntimeError(f"File does not appear to be SysEx (must start F0/end F7): {path}")
    return raw


def send_sysex_file(
    path: Path,
    output_port_contains: Optional[str] = None,
    inter_message_delay_s: float = 0.02,
    *,
    output_port_name: Optional[str] = None,
) -> str:
    raw = _read_syx_bytes(path)
    if output_port_name is not None:
        port_name = resolve_output_port(exact_name=output_port_name)
    else:
        port_name = resolve_output_port(output_port_contains)

    # Split a concatenated syx stream on F7 boundaries.
    packets: list[list[int]] = []
    current: list[int] = []
    for b in raw:
        current.append(int(b))
        if b == 0xF7:
            packets.append(current)
            current = []
    if current:
        packets.append(current)

    try:
        with mido.open_output(port_name) as port:
            for packet in packets:
                if not packet or packet[0] != 0xF0 or packet[-1] != 0xF7:
                    continue
                # mido expects the sysex message body without F0/F7.
                body = packet[1:-1]
                port.send(mido.Message("sysex", data=body))
                if inter_message_delay_s > 0:
                    time.sleep(inter_message_delay_s)
    except Exception as exc:
        raise RuntimeError(
            f"{_MIDI_OUTPUT_OPEN_HELP}\nAttempted port: {port_name!r}\n"
        ) from exc
    return port_name


def capture_sysex_dump(
    output_path: Path,
    input_port_contains: Optional[str] = None,
    listen_seconds: float = 10.0,
) -> tuple[str, int]:
    port_name = resolve_input_port(input_port_contains)
    captured_packets: list[list[int]] = []
    deadline = time.time() + max(0.1, float(listen_seconds))
    with mido.open_input(port_name) as port:
        while time.time() < deadline:
            msg = port.poll()
            if msg is None:
                time.sleep(0.01)
                continue
            if msg.type == "sysex":
                packet = [0xF0] + list(msg.data) + [0xF7]
                captured_packets.append(packet)

    if not captured_packets:
        output_path.write_bytes(b"")
        return port_name, 0

    blob = bytes(x for packet in captured_packets for x in packet)
    output_path.write_bytes(blob)
    return port_name, len(captured_packets)

