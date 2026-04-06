from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import mido

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_mapping.mapping import analyze_timbre_profile, map_timbre_to_abstract
from devices.pro800.mapping import map_to_pro800
from devices.pro800.transport import patch_to_cc_messages, resolve_output_port


def main() -> None:
    profile_path = ROOT / "timbre_profiles" / "diagnostic_extreme.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    patch = map_to_pro800(
        map_timbre_to_abstract(analyze_timbre_profile(profile)),
        patch_name="overwrite_a02_extreme",
    )

    port_name = resolve_output_port("PRO 800")
    print(f"Using output: {port_name}")
    print("Target preset index: 1 (A-02 if A-01 starts at 0)")

    with mido.open_output(port_name) as out:
        for ch in range(16):
            out.send(mido.Message("program_change", channel=ch, program=1))
            out.send(mido.Message("control_change", channel=ch, control=123, value=0))
            for msg in patch_to_cc_messages(patch, midi_channel=ch):
                out.send(msg)
            time.sleep(0.05)

    print("Overwrite test messages sent on channels 1..16.")
    print("If you want the overwrite persistent, store/save on the synth now.")


if __name__ == "__main__":
    main()

