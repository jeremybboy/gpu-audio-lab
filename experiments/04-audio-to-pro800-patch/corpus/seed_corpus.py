from __future__ import annotations

"""Generate presets_corpus.jsonl (100+ rows) from recipe patches + phrase variants."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "corpus" / "presets_corpus.jsonl"

# (patch_file relative to ROOT, list of families to tag rows for viz)
PATCH_FAMILIES: list[tuple[str, list[str]]] = [
    ("presets/epiano_from_solid_bass_patch.json", ["keys", "mallet"]),
    ("presets/bass_basic_patch.json", ["bass", "drums"]),
    ("presets/electric_guitar_patch.json", ["guitar", "lead", "brass"]),
    ("presets/juno_type_patch.json", ["pad", "fx"]),
    ("presets/acid_bass_patch.json", ["acid"]),
    ("presets/acid_bass_v2_patch.json", ["acid"]),
]

PHRASES: dict[str, list[str]] = {
    "keys": [
        "electric piano",
        "rhodes style keys",
        "tine electric keyboard",
        "bright piano pad",
        "e-piano bell",
        "wurly-ish digital",
        "soft keys patch",
        "keyboard for chords",
        "digital piano layer",
        "ivory electric keys",
        "studio epiano",
        "vintage keys sound",
    ],
    "mallet": [
        "marimba like",
        "mallet percussion vibe",
        "wooden keys pluck",
        "vibraphone-ish synth",
        "xylo bright hit",
        "orchestral mallet",
        "metallic mallet tone",
        "plucky tuned bars",
        "bell mallet attack",
        "percussive keys",
        "gamelan hint",
        "rubber mallet feel",
    ],
    "bass": [
        "solid bass",
        "sub bass line",
        "warm low end",
        "round bass guitar-ish",
        "mono bass synth",
        "deep bass patch",
        "club bass",
        "fundamental bass",
        "simple bass sound",
        "bottom octave weight",
        "bass for edm",
        "fat low bass",
    ],
    "drums": [
        "kick-like thump",
        "percussive bass hit",
        "drum body low",
        "808-ish length",
        "punchy drum bass",
        "electronic kick layer",
        "short percussive boom",
        "drum machine low",
        "trap sub knock",
        "percussion low tone",
        "rhythmic low hit",
        "drum synth approximation",
    ],
    "guitar": [
        "electric guitar pluck",
        "strat style lead",
        "picked guitar string",
        "guitar chord stab",
        "clean guitar edge",
        "guitar hero lead",
        "six string pluck",
        "country guitar twang",
        "rock guitar tone",
        "guitar-ish mono",
        "fingerpicked vibe",
        "guitar for riffs",
    ],
    "lead": [
        "mono synth lead",
        "screaming lead",
        "bright solo lead",
        "cutting lead line",
        "dance lead synth",
        "supersaw style lead",
        "sharp lead patch",
        "lead for melody",
        "aggressive lead",
        "thin piercing lead",
        "pop lead synth",
        "hook lead sound",
    ],
    "brass": [
        "brass stab synth",
        "horn section-ish",
        "bright brass lead",
        "fanfare brassy",
        "trumpet-like bite",
        "synth brass pad",
        "orchestral brass hint",
        "bold brass tone",
        "80s brass stab",
        "resonant brassy filter",
        "brass for stabs",
        "metallic brass lead",
    ],
    "pad": [
        "lush juno pad",
        "wide synth pad",
        "warm string pad",
        "ambient pad wash",
        "chorus pad sound",
        "poly pad layer",
        "dreamy pad",
        "analog style pad",
        "slow attack pad",
        "shimmer pad",
        "vintage poly pad",
        "hold pad chords",
    ],
    "fx": [
        "sweeping fx pad",
        "noise riser texture",
        "weird synth texture",
        "fx bed soundscape",
        "sci fi atmosphere",
        "modulated texture",
        "whoosh pad",
        "experimental pad",
        "sound design layer",
        "airy texture pad",
        "motion fx tone",
        "evolving pad fx",
    ],
    "acid": [
        "acid bassline",
        "303 squelch",
        "tb style sequence",
        "resonant acid",
        "squelchy mono",
        "techno acid",
        "low acid pulse",
        "filter drive bass",
        "acid house bass",
        "sharp resonant line",
        "sequencer acid",
        "distorted acid tone",
    ],
}


def generate_rows() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for patch_file, families in PATCH_FAMILIES:
        for family in families:
            phrases = PHRASES.get(family, [family])
            for i, phrase in enumerate(phrases):
                n += 1
                rid = f"{family}_{Path(patch_file).stem}_{i+1:02d}"
                rows.append(
                    {
                        "id": rid,
                        "family": family,
                        "text_chunks": [phrase, f"{phrase} synth", f"pro800 {family}"],
                        "patch_file": patch_file,
                        "syx_overlay": "patch_only",
                        "recommended_template_basename": "28 solid bass.syx",
                        "label": phrase[:48],
                    }
                )
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_rows()
    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} corpus rows to {OUT}")


if __name__ == "__main__":
    main()
