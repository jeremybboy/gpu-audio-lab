# Patch Format Notes

This folder documents format-level details independent of mapping logic.

Phase 1:

- JSON patch payload is canonical for inspection/debugging.
- CC stream export is the transport-safe baseline.
- SysEx export is implemented as placeholder bytes until the exact PRO-800 SysEx
  table and checksum rules are confirmed on hardware.

## Reference layout (decoded patch bytes)

Community reverse-engineered map (7-bit packed on the wire; **decode first**):

- [https://github.com/samstaton/pro800/blob/main/pro800syx.md](https://github.com/samstaton/pro800/blob/main/pro800syx.md)

Experiment tooling: `inspect-syx --decode` and `compare-syx --decode` unpack the
payload region of single-preset dumps and report a short slice summary (e.g.
version byte, cutoff bytes at decoded offsets 19–20) for verification against
that table — without changing the audio→patch mapping pipeline.

