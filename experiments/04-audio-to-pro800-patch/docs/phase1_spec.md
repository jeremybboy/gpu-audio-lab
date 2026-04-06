# Phase 1 Technical Spec

## Objective

Build an explainable pipeline that converts an input audio sample or timbre profile into a PRO-800-compatible patch representation.

## Architecture

1. `audio -> timbre_features`
2. `timbre_features -> abstract_subtractive_params`
3. `abstract_subtractive_params -> pro800_patch`
4. `pro800_patch -> export (json / cc / syx placeholder → real syx when encoded)`
5. `validated_syx_file -> pro800_transport (send/capture)`

## Transport & ground truth (locked)

**North star (product):** The web app should eventually cover **SynthTribe-class** workflows: connect to the PRO-800, **import/export** patch data, and treat the computer as the patch librarian—**USB MIDI** is the expected path from browser/PC to the synth.

**Interim testing:** It is acceptable to use the **standalone SynthTribe app** for manual import/export while the web stack catches up. Our repo still targets the same artifacts (especially **single-preset `.syx`**) so behavior stays aligned.

**Environment (authoritative for this experiment):** **Windows**, **PRO-800 over USB MIDI** as default; 5-pin MIDI is optional if needed later.

**Validation status:** Sending a **real SynthTribe-exported `.syx`** (e.g. via our `send-syx` path) **clearly changes** the sound to that preset—so SysEx delivery is a **proven** path on this setup.

**Ground truth definition:** **Perceptual (B)** — success means **you hear the intended preset** after load. **SysEx** is the primary mechanism to get patches onto the hardware. **Decoded `.syx` layout** (7-bit unpack + community offset table) is for **development, regression, and diffing**, not a substitute for listening.

**CC streams:** Remain secondary until NRPN/CC numbers are verified against this unit; do not treat CC-alone apply as canonical truth.

## API Contract (Phase 1)

### `GET /api/health`

- Returns service status and version.

### `POST /api/analyze`

- Input: multipart audio file (`wav`, `aiff`, `flac`) or JSON timbre profile.
- Output:
  - `spectral_centroid_mean`
  - `spectral_rolloff_mean`
  - `attack_time_s`
  - `harmonic_to_noise_ratio`
  - `vibrato_rate_hz` (coarse estimate, optional in Phase 1)

### `POST /api/map`

- Input: timbre features JSON.
- Output: abstract subtractive params (0..1 normalized), plus PRO-800 mapped params (0..127).

### `POST /api/export`

- Input: PRO-800 mapped params + format (`json|cc|syx`).
  - For `syx`, optional `syx_template`: basename of a file under `presets/` (single-preset SynthTribe export to clone layout).
  - Optional `preset_index` (int): SysEx program index byte; default = template’s index.
- Output:
  - `json`: structured patch payload
  - `cc`: ordered CC stream payload
  - `syx`: hardware-style single-preset SysEx when `syx_template` resolves; otherwise legacy placeholder bytes

### `POST /api/sysex/send`

- Input: filesystem path to `.syx` file + optional port filter.
- Output: MIDI output port used for send.

### `POST /api/sysex/capture`

- Input: capture duration + optional input port filter + output path.
- Output: packet count and captured `.syx` file path.

### Verification pipeline (recommended)

1. Capture baseline dump `A`.
2. Apply one known change.
3. Capture dump `B`.
4. Compare `A` vs `B` with byte/packet diff report.

## Abstract Parameter Schema (0..1)

- `osc1_level`, `osc2_level`, `noise_level`
- `osc_detune`, `osc_mix_bias`
- `filter_cutoff`, `filter_resonance`, `filter_env_amount`
- `amp_attack`, `amp_decay`, `amp_sustain`, `amp_release`
- `filter_attack`, `filter_decay`, `filter_sustain`, `filter_release`
- `lfo_rate`, `lfo_depth`
- `poly_mod_amount`

## Deterministic Mapping Rules (Phase 1)

- Brightness (`spectral_centroid_mean`) -> filter cutoff
- Harmonic/noise ratio -> noise level (inverse relation)
- Attack time -> amp/filter attack
- Spectral spread/rolloff -> resonance and filter env amount
- Vibrato estimate -> LFO rate/depth

All mappings use bounded piecewise-linear transforms for interpretability.

## PRO-800 Device Mapping

- Map normalized values to 0..127 integer parameter space.
- Keep device-specific parameter IDs isolated in `devices/pro800`.
- Preserve a stable default patch baseline and apply deltas from mapped values.

## Milestones

1. Confirm/lock PRO-800 parameter table for JSON+CC mapping
2. Implement static mapping and generate `oud` patch
3. Export and hardware smoke test
4. Add SysEx send/capture loop and collect real hardware dumps
5. Add dump comparison pipeline to validate real changes
6. Add `qanun` and `ney` references
7. Add CLI batch generation

## Success Criteria

- Patch artifact is generated and parseable
- Patch can be transferred; **canonical path is SysEx** to the PRO-800 (USB); CC stream remains auxiliary until mapped on hardware
- **Loaded preset matches intent by ear** (perceptual ground truth), with SysEx byte tools supporting debug
- Timbre is subjectively recognizable
- Output params remain editable and stable across repeated exports

