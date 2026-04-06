# 04-audio-to-pro800-patch

Web-first experiment for inverse sound design:

- Input: an audio sample (or manual timbre profile)
- Output: a PRO-800-oriented patch parameter set and export artifacts

Phase 1 focuses on deterministic mapping and transport, not ML.

## Goals

- Define a normalized parameter schema
- Extract lightweight timbre features from audio
- Map timbre features to subtractive synth controls deterministically
- Map abstract controls to PRO-800 patch parameters
- Export patch artifacts (`.json`, CC list, placeholder SysEx workflow)

## Scope (Phase 1)

- No deep learning
- No physical modeling
- No real-time audio synthesis
- Hardware-friendly patch generation with clear explainability

## Layout

- `docs/` technical specs and milestones
- `timbre_profiles/` manual profile examples (oud, qanun, ney)
- `core_mapping/` schema + deterministic mapping logic
- `devices/pro800/` PRO-800 parameter mapping and export helpers
- `cli/` command-line entry points
- `presets/` generated output artifacts

## Quickstart

```bash
python -m pip install flask numpy librosa soundfile mido
python experiments/04-audio-to-pro800-patch/app.py
```

CLI examples:

```bash
python experiments/04-audio-to-pro800-patch/cli/main.py generate --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json
python experiments/04-audio-to-pro800-patch/cli/main.py export --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json --format cc
python experiments/04-audio-to-pro800-patch/cli/main.py export --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json --format syx --syx-template path/to/synthtribe_single_preset.syx
python experiments/04-audio-to-pro800-patch/cli/main.py list-ports
python experiments/04-audio-to-pro800-patch/cli/main.py send --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json --port-contains "PRO 800"
python experiments/04-audio-to-pro800-patch/cli/main.py apply --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json --slot A-03 --port-contains "PRO 800"
python experiments/04-audio-to-pro800-patch/cli/main.py send-syx --file experiments/04-audio-to-pro800-patch/presets/your_patch.syx --port-contains "PRO 800"
python experiments/04-audio-to-pro800-patch/cli/main.py capture-syx --output experiments/04-audio-to-pro800-patch/presets/captured_dump.syx --seconds 12
python experiments/04-audio-to-pro800-patch/cli/main.py inspect-syx --file experiments/04-audio-to-pro800-patch/presets/captured_dump.syx
python experiments/04-audio-to-pro800-patch/cli/main.py inspect-syx --decode --file path/to/SynthTribe_export.syx
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --a experiments/04-audio-to-pro800-patch/presets/pro800_dump_A.syx --b experiments/04-audio-to-pro800-patch/presets/pro800_dump_B.syx
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a path/to/preset_A.syx --b path/to/preset_B.syx
```

## Notes

- `inspect-syx --decode` / `compare-syx --decode` unpack the community 7-bit layout and surface hints (e.g. cutoff bytes); see `patch_format/README.md`.
- PRO-800 SysEx format details are intentionally isolated so they can be swapped once format validation is finalized.
- This experiment is designed so audio-driven extraction can be replaced by manual or hybrid profiles later.
- `send-syx` and `capture-syx` now support a real SysEx transport workflow to validate patch dumps from hardware.

