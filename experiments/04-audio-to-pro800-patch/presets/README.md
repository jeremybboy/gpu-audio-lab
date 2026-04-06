# Presets Output

Generated artifacts are written here by API/CLI:

- `*.json` patch dumps
- `*.cc.json` MIDI CC stream payloads
- `*.syx` — see below

## Which `.syx` files SynthTribe will accept

SynthTribe expects **real Behringer PRO-800 SysEx** (same family as an **Export** from the app). A valid **single-preset** file usually:

- Starts with `F0 00 20 32 00 01 24 00 78` (not `… 32 7F 01 …`).
- Is **hundreds of bytes** for one program (often ~190–230 B depending on name/padding), **not** 26 bytes.

**Will fail in SynthTribe (“wrong file”):**

| Case | Why |
|------|-----|
| **Placeholder export** (no `--syx-template`) | Tiny ~26-byte file; header uses `7F 01` — workflow stub only, not loadable in SynthTribe. |
| **`*.json` / `*.cc.json`** | Not SysEx — use JSON/CC in our tools, not in SynthTribe import. |
| **Empty `*.syx` (0 bytes)** | Incomplete capture; re-capture or delete. |
| **Large bank dumps** (`pro800_dump_*.syx`, tens of kB) | Full-bank format — use SynthTribe’s **bank** import if it offers one, not the same UI as a **single preset** file. |

**Should work in SynthTribe** (same shape as your Downloads exports):

- Any **SynthTribe-exported** reference (e.g. `lofi synth pro 800.syx`, `28 solid bass.syx`).
- Our **`ear_test.syx`**, **`step2_test.syx`**, **`template_riser_preset_30.syx`** — built with `--syx-template` from a real export; **single-preset import** path in SynthTribe.

If a template-based file still errors, use the same **Import** action you use for files from Downloads, and ensure no other app has locked MIDI.

### `send-syx` fails with `MidiOutWinMM::openPort` (Windows)

Another program is almost always holding the **MIDI output** (very often **SynthTribe** or a DAW). **Quit** those apps completely, then run `send-syx` again. Only one app can open `PRO 800 1` at a time.

Use **`list-ports`** to copy the exact output name, then:

`send-syx --file … --output-name "PRO 800 1"`

(`--output-name` is preferred over substring matching when debugging.)

## Generating a real `.syx` (not a placeholder)

Pass a **SynthTribe single-preset** `.syx` as `--syx-template` (CLI) or place it under `presets/` and set `syx_template` in `/api/export` (basename only, e.g. `template_riser_preset_30.syx`).

**Tiny A/B test (no timbre profile):** `python …/cli/main.py tweak-syx --input path/to/export.syx --output presets/solid_bass_variation.syx` — either **add** to cutoff (`--cutoff-raw-delta`, default **+2048**) or set it explicitly (`--cutoff-u16 65532` ≈ max for a very open filter). Older MIDI-style tweaks could **lower** cutoff by mistake and sound silent.

Reference copies in this folder: `28_solid_bass_original.syx` (SynthTribe export from Downloads), `solid_bass_variation.syx` (same + small cutoff tweak).

