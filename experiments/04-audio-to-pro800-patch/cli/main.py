from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_mapping.mapping import analyze_timbre_profile, map_timbre_to_abstract
from devices.pro800.export import export_patch_cc_stream, export_patch_json, export_patch_syx
from devices.pro800.mapping import map_to_pro800
from devices.pro800.schema import Pro800Patch
from devices.pro800.sysex_encode import build_syx_from_template_tweak
from devices.pro800.sysex_tools import compare_dumps, summarize_dump
from devices.pro800.transport import (
    apply_patch_to_slot,
    capture_sysex_dump,
    list_midi_inputs,
    list_midi_outputs,
    send_patch_cc,
    send_sysex_file,
)
from sound_intents.resolver import load_registry, resolve_in_registry


def _load_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_generate(args: argparse.Namespace) -> int:
    profile = _load_profile(Path(args.profile))
    features = analyze_timbre_profile(profile)
    abstract = map_timbre_to_abstract(features)
    patch = map_to_pro800(abstract, patch_name=args.name)
    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}.json"
    export_patch_json(patch, out_path)
    print(f"Generated patch JSON: {out_path}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    if args.patch_json:
        raw = _load_profile(Path(args.patch_json))
        patch = Pro800Patch.from_export_dict(raw)
    else:
        profile = _load_profile(Path(args.profile))
        features = analyze_timbre_profile(profile)
        abstract = map_timbre_to_abstract(features)
        patch = map_to_pro800(abstract, patch_name=args.name)
    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        out_path = out_dir / f"{args.name}.json"
        export_patch_json(patch, out_path)
    elif args.format == "cc":
        out_path = out_dir / f"{args.name}.cc.json"
        export_patch_cc_stream(patch, out_path)
    else:
        out_path = out_dir / f"{args.name}.syx"
        tpl = Path(args.syx_template).expanduser() if args.syx_template else None
        export_patch_syx(
            patch,
            out_path,
            template_path=tpl,
            preset_index=args.preset_index,
            syx_overlay=args.syx_overlay,
        )
        if tpl is None or not tpl.is_file():
            print(
                "Note: no --syx-template; wrote placeholder .syx. "
                "Pass a SynthTribe single-preset export for hardware-loadable SysEx.",
                file=sys.stderr,
            )
    print(f"Exported {args.format}: {out_path}")
    return 0


def cmd_sound_export(args: argparse.Namespace) -> int:
    """Text intent → curated Pro800Patch → .syx (template clone; default patch_only)."""
    reg = load_registry(
        Path(args.registry).expanduser() if args.registry else None
    )
    try:
        intent_id, meta = resolve_in_registry(args.describe, reg)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    overlay = str(meta.get("syx_overlay", "patch_only"))
    if overlay not in ("blend_max", "patch_only"):
        print(
            f"Invalid syx_overlay in registry for {intent_id!r}: {overlay!r}",
            file=sys.stderr,
        )
        return 1

    rel_patch = meta.get("patch_file")
    if not rel_patch or not isinstance(rel_patch, str):
        print(f"Intent {intent_id!r} missing patch_file in registry.", file=sys.stderr)
        return 1

    patch_path = (ROOT / rel_patch).resolve()
    if not patch_path.is_file():
        print(f"Recipe patch JSON not found: {patch_path}", file=sys.stderr)
        return 1

    raw = _load_profile(patch_path)
    patch = Pro800Patch.from_export_dict(raw)

    tpl = Path(args.syx_template).expanduser()
    if not tpl.is_file():
        print(
            f"Warning: --syx-template is missing or not a file: {tpl}\n"
            "Without a real SynthTribe single-preset export, output is a placeholder .syx "
            "(not loadable). If you hear nothing on hardware, fix the template path first.",
            file=sys.stderr,
        )

    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}.syx"
    export_patch_syx(
        patch,
        out_path,
        template_path=tpl if tpl.is_file() else None,
        preset_index=args.preset_index,
        syx_overlay=overlay,
    )

    print(f"Resolved intent: {intent_id} (describe: {args.describe!r})")
    print(f"Syx overlay mode: {overlay}")
    print(f"Template: {tpl}")
    if meta.get("recommended_template"):
        print(f"Registry recommended_template: {ROOT / meta['recommended_template']}")
    print(f"Recipe patch JSON: {patch_path}")
    print(f"Output: {out_path}")
    notes = meta.get("notes")
    if isinstance(notes, str) and notes.strip():
        print(f"Recipe notes: {notes}")
    if reg.get("audibility_note") and isinstance(reg["audibility_note"], str):
        print(f"Audibility: {reg['audibility_note']}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    profile = _load_profile(Path(args.profile))
    features = analyze_timbre_profile(profile)
    abstract = map_timbre_to_abstract(features)
    patch = map_to_pro800(abstract, patch_name=args.name)
    port_used = send_patch_cc(
        patch,
        midi_channel=int(args.channel),
        output_port_contains=args.port_contains,
    )
    print(f"Sent patch '{patch.name}' to MIDI output: {port_used}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    profile = _load_profile(Path(args.profile))
    features = analyze_timbre_profile(profile)
    abstract = map_timbre_to_abstract(features)
    patch = map_to_pro800(abstract, patch_name=args.name)
    port_used, program_index = apply_patch_to_slot(
        patch=patch,
        slot=args.slot,
        midi_channel=int(args.channel),
        output_port_contains=args.port_contains,
        settle_ms=int(args.settle_ms),
    )
    print(
        f"Applied patch '{patch.name}' to slot {args.slot} "
        f"(program={program_index}) via MIDI output: {port_used}"
    )
    print("Note: persist to memory using STORE on hardware if needed.")
    return 0


def cmd_list_ports(_args: argparse.Namespace) -> int:
    outs = list_midi_outputs()
    ins = list_midi_inputs()
    print("MIDI inputs:")
    for name in ins:
        print(f"- {name}")
    print("MIDI outputs:")
    for name in outs:
        print(f"- {name}")
    if not ins and not outs:
        print("No MIDI ports found.")
        return 1
    return 0


def cmd_send_syx(args: argparse.Namespace) -> int:
    try:
        port_used = send_sysex_file(
            Path(args.file),
            output_port_contains=args.port_contains,
            inter_message_delay_s=float(args.delay),
            output_port_name=args.output_name,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Sent SysEx file '{args.file}' to MIDI output: {port_used}")
    return 0


def cmd_capture_syx(args: argparse.Namespace) -> int:
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    port_used, count = capture_sysex_dump(
        output_path=out_path,
        input_port_contains=args.port_contains,
        listen_seconds=float(args.seconds),
    )
    print(f"Captured {count} SysEx packet(s) from MIDI input: {port_used}")
    print(f"Output file: {out_path}")
    return 0


def cmd_inspect_syx(args: argparse.Namespace) -> int:
    path = Path(args.file)
    summary = summarize_dump(path, decode=bool(args.decode))
    print(json.dumps(summary, indent=2))
    return 0


def cmd_tweak_syx(args: argparse.Namespace) -> int:
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cu = args.cutoff_u16
    data = build_syx_from_template_tweak(
        Path(args.input).expanduser(),
        cutoff_raw_delta=0 if cu is not None else int(args.cutoff_raw_delta),
        resonance_raw_delta=int(args.resonance_raw_delta),
        cutoff_u16=cu,
        preset_index=args.preset_index,
    )
    out.write_bytes(data)
    msg = (
        f"cutoff uint16 = {cu}"
        if cu is not None
        else "raw uint16 nudge at decoded offsets 19/21"
    )
    print(f"Wrote {out} ({len(data)} bytes) - {msg}.")
    return 0


def cmd_compare_syx(args: argparse.Namespace) -> int:
    a = Path(args.a)
    b = Path(args.b)
    report = compare_dumps(a, b, decode=bool(args.decode))
    print(json.dumps(report, indent=2))
    if args.decode:
        dc = report.get("decoded_compare_packet_0") or {}
        n = int(dc.get("diff_byte_count_decoded") or 0)
        if n == 0:
            print("Result: decoded payloads match (first packet).")
        else:
            print("Result: decoded payloads differ (first packet).")
    elif report["identical_bytes"]:
        print("Result: dumps are byte-identical.")
    else:
        print("Result: dumps differ.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audio/timbre to PRO-800 patch tools (Phase 1).")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate patch JSON from timbre profile.")
    gen.add_argument("--profile", required=True, help="Path to timbre profile JSON.")
    gen.add_argument("--name", default="generated_patch")
    gen.set_defaults(func=cmd_generate)

    exp = sub.add_parser("export", help="Export patch payload in chosen format.")
    exp_src = exp.add_mutually_exclusive_group(required=True)
    exp_src.add_argument(
        "--profile",
        default=None,
        help="Path to timbre profile JSON (spectral features → map).",
    )
    exp_src.add_argument(
        "--patch-json",
        default=None,
        help="Path to Pro800Patch JSON (from generate); full params_0_127 control.",
    )
    exp.add_argument("--name", default="generated_patch")
    exp.add_argument("--format", choices=["json", "cc", "syx"], default="json")
    exp.add_argument(
        "--syx-template",
        default=None,
        help="SynthTribe single-preset .syx to clone wire layout (required for real SysEx).",
    )
    exp.add_argument(
        "--preset-index",
        type=int,
        default=None,
        help="Program index byte for SysEx (0–127); default = template's index.",
    )
    exp.add_argument(
        "--syx-overlay",
        choices=["blend_max", "patch_only"],
        default="blend_max",
        help="blend_max: max(patch, template) per field. patch_only: use patch values (morph templates).",
    )
    exp.set_defaults(func=cmd_export)

    snd = sub.add_parser("send", help="Send mapped patch to a MIDI output port.")
    snd.add_argument("--profile", required=True, help="Path to timbre profile JSON.")
    snd.add_argument("--name", default="generated_patch")
    snd.add_argument("--channel", type=int, default=0, help="MIDI channel [0-15].")
    snd.add_argument("--port-contains", default="PRO 800", help="Substring to match output port name.")
    snd.set_defaults(func=cmd_send)

    apl = sub.add_parser("apply", help="Select a slot and apply mapped patch parameters live.")
    apl.add_argument("--profile", required=True, help="Path to timbre profile JSON.")
    apl.add_argument("--name", default="generated_patch")
    apl.add_argument("--slot", default="A-03", help="Target slot, e.g. A-03 or 3.")
    apl.add_argument("--channel", type=int, default=0, help="MIDI channel [0-15].")
    apl.add_argument("--port-contains", default="PRO 800", help="Substring to match output port name.")
    apl.add_argument("--settle-ms", type=int, default=120, help="Delay after program change before CC send.")
    apl.set_defaults(func=cmd_apply)

    lsp = sub.add_parser("list-ports", help="List available MIDI output ports.")
    lsp.set_defaults(func=cmd_list_ports)

    ssyx = sub.add_parser("send-syx", help="Send a .syx file directly to a MIDI output.")
    ssyx.add_argument("--file", required=True, help="Path to SysEx file.")
    ssyx.add_argument(
        "--output-name",
        default=None,
        help="Exact MIDI output name from list-ports (e.g. 'PRO 800 1'). Overrides --port-contains.",
    )
    ssyx.add_argument("--port-contains", default="PRO 800", help="Substring to match output port name.")
    ssyx.add_argument("--delay", type=float, default=0.02, help="Inter-packet delay in seconds.")
    ssyx.set_defaults(func=cmd_send_syx)

    csyx = sub.add_parser("capture-syx", help="Capture incoming SysEx from a MIDI input port.")
    csyx.add_argument("--output", default=str(ROOT / "presets" / "captured_dump.syx"), help="Output SysEx path.")
    csyx.add_argument("--port-contains", default="PRO 800", help="Substring to match input port name.")
    csyx.add_argument("--seconds", type=float, default=10.0, help="Capture duration in seconds.")
    csyx.set_defaults(func=cmd_capture_syx)

    isyx = sub.add_parser("inspect-syx", help="Inspect a PRO-800 SysEx dump and print structure summary.")
    isyx.add_argument("--file", required=True, help="Path to SysEx file.")
    isyx.add_argument(
        "--decode",
        action="store_true",
        help="Unpack 7-bit payload and show decoded field hints (see patch_format/README.md).",
    )
    isyx.set_defaults(func=cmd_inspect_syx)

    tw = sub.add_parser(
        "tweak-syx",
        help="Clone a SynthTribe .syx and apply a tiny cutoff/resonance nudge (debug / A-B test).",
    )
    tw.add_argument("--input", required=True, help="Source single-preset .syx (e.g. SynthTribe export).")
    tw.add_argument(
        "--output",
        default=str(ROOT / "presets" / "solid_bass_variation.syx"),
        help="Where to write the new .syx.",
    )
    tw.add_argument(
        "--cutoff-u16",
        type=int,
        default=None,
        help="Set filter cutoff uint16 at decoded offset 19 (0-65535). E.g. 65520 is almost max. Overrides --cutoff-raw-delta.",
    )
    tw.add_argument(
        "--cutoff-raw-delta",
        type=int,
        default=2048,
        help="Add to filter cutoff uint16 LE at offset 19 (opens filter / brighter). Ignored if --cutoff-u16 is set.",
    )
    tw.add_argument(
        "--resonance-raw-delta",
        type=int,
        default=0,
        help="Add to resonance uint16 LE at decoded offset 21, optional.",
    )
    tw.add_argument(
        "--preset-index",
        type=int,
        default=None,
        help="Override SysEx program index byte; default = source file.",
    )
    tw.set_defaults(func=cmd_tweak_syx)

    sndx = sub.add_parser(
        "sound-export",
        help="Resolve a text sound intent (e.g. electric piano) and export template-based .syx.",
    )
    sndx.add_argument(
        "--describe",
        required=True,
        help='Phrase or alias, e.g. "electric piano", "e piano", "rhodes".',
    )
    sndx.add_argument(
        "--syx-template",
        required=True,
        help="SynthTribe single-preset .syx anchor (e.g. 28 solid bass.syx).",
    )
    sndx.add_argument(
        "--name",
        default="sound_export",
        help="Output basename under presets/ (default: sound_export → sound_export.syx).",
    )
    sndx.add_argument(
        "--registry",
        default=None,
        help="Optional path to registry.json (default: sound_intents/registry.json).",
    )
    sndx.add_argument(
        "--preset-index",
        type=int,
        default=None,
        help="SysEx program index byte (0–127); default = template's index.",
    )
    sndx.set_defaults(func=cmd_sound_export)

    dsyx = sub.add_parser("compare-syx", help="Compare two SysEx dumps and report byte/packet differences.")
    dsyx.add_argument("--a", required=True, help="Path to baseline SysEx file.")
    dsyx.add_argument("--b", required=True, help="Path to modified SysEx file.")
    dsyx.add_argument(
        "--decode",
        action="store_true",
        help="Compare first packet payloads after 7-bit decode (cutoff slice, etc.).",
    )
    dsyx.set_defaults(func=cmd_compare_syx)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

