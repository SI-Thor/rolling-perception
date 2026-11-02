# 2026-11-01 — Rust workspace verification on Thor (summary entry)

Canonical full text: `docs/THOR-VERIFICATION.md` — read it there;
this file is the results-index pointer, not a copy.

- **Machine:** thor (aarch64, Neoverse V3AE), cargo/rustc 1.99.1,
  workspace copied to `~/rolling-perception-play/rust/`.
- **Headline results:** `cargo test --release` **29/29 pass**
  (6 rolling + 23 substrate-core); CPU bench (120 cycles, 400 µs
  stagger): rolling TTFO **176.5 µs**, TTFO ratio **15.78×**, outputs
  5.0×, checksum `345101.1999` **bit-identical to x86_64**, batched-vs-
  rolling checksum delta 0.000000 on both architectures.
- **Caveat in canonical text:** a cosmetic `[profile.release]`
  workspace warning, harmless, removed in the repo copy.
