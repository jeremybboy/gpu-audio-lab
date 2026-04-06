# PRO-800 knob calibration — 2026-04-05

**Status:** Awaiting six hardware single-preset `.syx` files in this folder (see filenames below). After they exist, run the compares from the repo root and fill the results table.

**Reference:** [pro800syx.md](https://github.com/samstaton/pro800/blob/main/pro800syx.md)

## Expected files (same program slot)

| File | Change vs baseline |
|------|-------------------|
| `slotA12_00_baseline.syx` | — |
| `slotA12_01_vol_a.syx` | Vol A only |
| `slotA12_02_filt_env.syx` | Filt Env only |
| `slotA12_03_ae_decay.syx` | AE D only |
| `slotA12_04_lfo_freq.syx` | LFO Freq only |
| `slotA12_05_lfo_amt.syx` | LFO Amt only |

## Expected decoded offsets (uint16 LE)

| Control | Offset |
|---------|--------|
| Vol A | 7 |
| Filt Env | 23 |
| AE D | 37 |
| LFO Freq | 45 |
| LFO Amt | 47 |

## Commands (repo root)

```bash
python experiments/04-audio-to-pro800-patch/cli/main.py inspect-syx --decode --file experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_00_baseline.syx
```

```bash
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_00_baseline.syx --b experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_01_vol_a.syx
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_00_baseline.syx --b experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_02_filt_env.syx
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_00_baseline.syx --b experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_03_ae_decay.syx
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_00_baseline.syx --b experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_04_lfo_freq.syx
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_00_baseline.syx --b experiments/04-audio-to-pro800-patch/calibration_runs/2026-04-05/slotA12_05_lfo_amt.syx
```

JSON fields to note: `decoded_compare_packet_0.first_diff_decoded_offsets`, `diff_byte_count_decoded`, and per-offset values in decoded hex if you diff manually.

## Results (fill after capture)

| Knob | Pair | Expected offset(s) | Actual differing decoded offsets | Notes |
|------|------|--------------------|----------------------------------|-------|
| Vol A | 00 vs 01 | 7–8 | | |
| Filt Env | 00 vs 02 | 23–24 | | |
| AE D | 00 vs 03 | 37–38 | | |
| LFO Freq | 00 vs 04 | 45–46 | | |
| LFO Amt | 00 vs 05 | 47–48 | | |

## Appendix — raw tool output

_(Paste `compare-syx --decode` JSON or stdout here after runs.)_
