"""Decode pair_XX/source.syx first packet -> pair_XX/patch.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # paired_v1/


def main() -> None:
    sys.path.insert(0, str(ROOT.parents[1]))  # 04-audio-to-pro800-patch/
    from devices.pro800.sysex_encode import sysex_packet_to_patch
    from devices.pro800.sysex_tools import parse_pro800_dump

    for i in range(1, 11):
        pid = f"pair_{i:02d}"
        syx = ROOT / pid / "source.syx"
        if not syx.is_file():
            print("skip", pid, "(no source.syx)")
            continue
        pkts = parse_pro800_dump(syx)
        if not pkts:
            print("skip", pid, "(no packets)")
            continue
        patch = sysex_packet_to_patch(pkts[0], name=pid)
        out = ROOT / pid / "patch.json"
        out.write_text(json.dumps(patch.to_dict(), indent=2), encoding="utf-8")
        print("wrote", out)


if __name__ == "__main__":
    main()
