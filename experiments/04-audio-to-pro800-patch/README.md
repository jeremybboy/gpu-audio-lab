# 04 — Audio / timbre → Behringer PRO-800 patch

Turn **what you hear** (or a hand-built **timbre profile**) into **patch parameters** you can load on a **Behringer PRO-800**—starting with **explainable, deterministic** rules, not a black-box model.

## What this is

- **Goal:** A small **pipeline** and (eventually) a **web-style** workflow: profile or analyze audio → map to a normalized **subtractive** control set → map to **PRO-800**-shaped data → export **JSON**, **CC lists**, and **real single-preset SysEx** when you supply a **SynthTribe-style template** `.syx`.
- **Ground truth for “did it load?”** Perceptual: you **hear** the change after import or `send-syx`. **Decoded SysEx** diffs are for debugging and calibration (see `patch_format/README.md` and community [pro800syx.md](https://github.com/samstaton/pro800/blob/main/pro800syx.md)).
- **Hardware:** Developed against **USB MIDI** on Windows; **SynthTribe** is a supported path for import/export alongside our CLI.

## Pipeline (conceptual)

```
audio sample OR JSON timbre profile
        → timbre features (centroid, rolloff, attack, HNR, …)
        → abstract subtractive params (0…1)
        → Pro800Patch (0…127 integers)
        → export: JSON | CC stream | .syx (template-based real SysEx)
```

## What’s implemented (Phase 1)

| Piece | Role |
|-------|------|
| **`core_mapping/`** | Feature extraction from profiles; deterministic map to abstract params |
| **`devices/pro800/`** | `Pro800Patch` schema; map abstract → device; **CC** export (numbers still **unverified** on hardware) |
| **SysEx** | **7-bit pack/unpack**; **single-preset** packet build from a **template** file; **`tweak-syx`** for tiny edits (e.g. cutoff as raw `uint16` or delta) for A/B tests |
| **`app.py`** | Flask API: analyze, map, export, **`/api/export_sound`**, **`/api/export_from_profile`**, serve UI at **`/`**; MIDI / SysEx |
| **Repo `docs/`** | Static web UI (same files served by Flask locally; **GitHub Pages** preview) |
| **`cli/main.py`** | `generate`, `export`, `send`, `apply`, **`sound-export`**, `send-syx`, `capture-syx`, `inspect-syx`, `compare-syx`, **`tweak-syx`** |
| **`sound_intents/`** | Text phrase → curated patch recipe (conservative template morphs; see registry notes) |
| **`corpus/`** | **Open-text** preset retrieval: seeded JSONL, offline **`build_index.py`**, PCA 2D viz + cosine match; **extends** (does not replace) the registry |
| **`.vscode/tasks.json`** (repo root) | Optional **Run Task** flows for export / send without typing paths |

**Not** in scope yet: ML timbre matching, physical modeling, guaranteed **“sounds like the reference clip”** (that’s later tuning). **Full** knob-by-knob SysEx mapping is **ongoing** (calibrate with same-slot, single-parameter captures).

### Phase 1 (what works today)

- **Timbre profile** (JSON or audio via `/api/analyze`) → `/api/map` → **`/api/export`** with `format: "syx"` and a **`syx_template`** basename under `presets/`.
- **Hand-authored patch JSON** → CLI **`export --patch-json`** or build `patch` client-side and POST **`/api/export`**.
- **Text / phrase → `.syx`:** CLI **`sound-export`** or **`POST /api/export_sound`** (`describe`, `syx_template`, optional `name`) using **`sound_intents/registry.json`** and per-intent **`syx_overlay`** (usually **`patch_only`** for recipe morphs).
- **One-shot profile → `.syx`:** **`POST /api/export_from_profile`** with `profile`, `syx_template`, optional **`syx_overlay`** (default **`blend_max`** for timbre-driven maps).
- **SysEx:** template clone, **`blend_max`** vs **`patch_only`**, full-span uint16 apply path for audibility (see `devices/pro800/sysex_encode.py`).

## Layout

| Path | Contents |
|------|----------|
| `docs/phase1_spec.md` | API contract, transport / ground-truth notes, milestones |
| `patch_format/` | SysEx vs JSON notes |
| `timbre_profiles/` | Example JSON profiles (oud, qanun, ney, …) |
| `core_mapping/` | Schemas + deterministic mapping |
| `devices/pro800/` | PRO-800 mapping, export, **SysEx encode**, MIDI transport |
| `cli/` | Command-line entrypoint |
| `sound_intents/` | `registry.json` + resolver (phrase → intent → recipe patch path) |
| `presets/` | Output area (gitignored: `*.syx`, `*.cc.json`); see `presets/README.md` |
| Repo root **`docs/`** | Static **web UI** for export forms; enable **GitHub Pages** on `/docs` for a public **preview** (API still local) |

## Try it (web UI + API)

```bash
# From repo root, venv activated
python -m pip install flask numpy librosa soundfile mido python-rtmidi
cd experiments/04-audio-to-pro800-patch
python app.py
# Browser: http://127.0.0.1:5055/
```

Place a real SynthTribe single-preset file at **`presets/28 solid bass.syx`** (or another basename) so **Describe sound** and **profile** downloads produce loadable SysEx.

### Open-text corpus (embedding retrieval + PCA map)

The **registry** (`sound_intents/registry.json`) and **`POST /api/export_sound`** stay the curated, **closed-world** path. The **corpus** adds **any-string** matching over 100+ rows (phrase variants × recipes) with the **same** `.syx` export stack (`export_patch_syx`, recipe JSON, template basename).

1. Install extra deps (sentence-transformers pulls PyTorch if needed):

   ```bash
   python -m pip install -r experiments/04-audio-to-pro800-patch/requirements-corpus.txt
   ```

2. (Optional) Regenerate the JSONL: `python corpus/seed_corpus.py` from `experiments/04-audio-to-pro800-patch/`.

3. Build the index (writes **`corpus/_index/`**, gitignored; downloads the default embedding model on first run):

   ```bash
   cd experiments/04-audio-to-pro800-patch
   python corpus/build_index.py
   ```

4. Run **`python app.py`** and open **`http://127.0.0.1:5055/corpus.html`**.

**API:** `GET /api/corpus/viz`, `POST /api/corpus/match` (`query`, `k`), `POST /api/corpus/export` (`preset_id` or `query`, optional `syx_template`, `name`, `preset_index`, `syx_overlay`). If the index is missing, these return **503** with a pointer to `build_index.py`.

**Env:** Optional **`CORPUS_EMBED_MODEL`** — must match the model used to build `corpus/_index/` (dimension + PCA). Default index build uses **`all-MiniLM-L6-v2`**. OpenAI or other providers are not wired in this MVP; keep API keys out of the repo.

**Limits:** Query coordinates are a **PCA projection** of the query embedding (same transform as presets). **Real SysEx** still needs a **template** `.syx` under `presets/`; encoding remains a **partial** parameter overlay (see Phase 1 notes above).

### GitHub Pages (static preview only)

- In the GitHub repo: **Settings → Pages → Build and deployment → Branch `main` / folder `/docs`**.
- Site URL pattern: **`https://jeremybboy.github.io/gpu-audio-lab/`** (replace owner/repo if forked).
- **GitHub Pages cannot run Flask.** The hosted page is for **UI + instructions**. Real **`POST /api/export_sound`** only works when you open **`http://127.0.0.1:5055/`** after starting **`python app.py`** (same-origin). A public `github.io` page cannot reliably call your laptop’s API.

## Quickstart (API only)

```bash
# From repo root, with venv activated
python -m pip install flask numpy librosa soundfile mido python-rtmidi
python experiments/04-audio-to-pro800-patch/app.py
```

CLI (examples):

```bash
python experiments/04-audio-to-pro800-patch/cli/main.py generate --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json
python experiments/04-audio-to-pro800-patch/cli/main.py export --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json --format json
python experiments/04-audio-to-pro800-patch/cli/main.py export --profile experiments/04-audio-to-pro800-patch/timbre_profiles/oud.json --format syx --syx-template path/to/synthtribe_single_preset.syx
python experiments/04-audio-to-pro800-patch/cli/main.py export --patch-json experiments/04-audio-to-pro800-patch/presets/my_patch.json --name my_patch --format syx --syx-template path/to/synthtribe_single_preset.syx
python experiments/04-audio-to-pro800-patch/cli/main.py tweak-syx --input path/to/preset.syx --output experiments/04-audio-to-pro800-patch/presets/variation.syx --cutoff-u16 65532
python experiments/04-audio-to-pro800-patch/cli/main.py list-ports
python experiments/04-audio-to-pro800-patch/cli/main.py send-syx --file path/to/file.syx --output-name "PRO 800 1"
python experiments/04-audio-to-pro800-patch/cli/main.py compare-syx --decode --a preset_A.syx --b preset_B.syx
```

### Sound intents (text → `.syx`)

Recipes are **small, hand-curated morphs** from a **known-loud** SynthTribe template (e.g. `presets/28 solid bass.syx`). They use **`patch_only`** SysEx overlay by default so parameters can move **down** (e.g. less resonance) without `blend_max` fighting the goal. Random or zero-heavy patches often produce **silence** on hardware; extend `sound_intents/registry.json` conservatively.

```bash
python experiments/04-audio-to-pro800-patch/cli/main.py sound-export \
  --describe "electric piano" \
  --syx-template "experiments/04-audio-to-pro800-patch/presets/28 solid bass.syx" \
  --name my_epiano
```

## First iteration — scope and next phases

What ships today (template-based SysEx, timbre profiles, **text / sound-intent → `.syx`**, minimal web UI) is a **first iteration**: it proves the path from **description or hand-tuned recipes** to a **loadable preset**, not a finished sound-design product.

**Reserved for later phases (important gaps):**

1. **Accuracy and expressiveness** — Audio from generated `.syx` files is not yet **tightly controlled** or **modular**: partial SysEx overlay, coarse recipes, and limited parameters vs the full patch map mean the sonic palette is still narrow compared with the hardware. Future work: richer encoding, more fields, hardware validation, tighter feedback loops.

2. **Sound → SysEx (audio in, preset out)** — The practical **text-to-`.syx`** path (sound intents) is the starting point. **Audio-to-`.syx`** with stronger **audio information retrieval** (richer features, similarity, optional learning) is a **more advanced** phase and should stay scoped so Phase 1 stays maintainable.

## Notes

- **Real `.syx`** requires a **SynthTribe single-preset** export as `--syx-template` (clone wire layout). **Placeholder** `.syx` is only used when no template is given (not loadable in SynthTribe).
- **`inspect-syx --decode` / `compare-syx --decode`** unpack the community 7-bit layout; see `patch_format/README.md`.
- **Cutoff / continuous params:** firmware **0x6F** presets may store **large** `uint16` values; use **raw** `--cutoff-u16` / `--cutoff-raw-delta` in `tweak-syx` rather than MIDI-only shortcuts when A/B testing.
- Audio-driven extraction can be swapped for **manual profiles** or hybrid flows later.
