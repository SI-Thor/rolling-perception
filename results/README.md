# results/ — where measured results live

Every measured run that the README, PLAN, or a release cites must have
an entry here. Prose summaries in `docs/` and `experiments/` *point*
here (and to the raw logs); they are not themselves the record.

## Layout

```
results/
  README.md                 <- this file
  thor/
    2026-11-01-feasibility.md
    2026-11-01-thor-cuda-play.md
    2026-11-01-workspace-verification.md
    <YYYY-MM-DD>-<experiment>.md     <- every future Thor run
  x86/
    <YYYY-MM-DD>-<experiment>.md     <- dev-machine runs, same format
```

Rules:

1. **One file per run (or run series on one date).** Never edit a past
   result file to update numbers — add a new dated file and let the
   newer one supersede it explicitly.
2. **Each file states:** date/time + timezone, machine (hostname,
   architecture, GPU + compute capability if used), toolchain
   (rustc/nvcc versions), exact commands run, the headline numbers in a
   table, what was verified (test counts, checksums, sentinel checks),
   and any rig bug or caveat found *in that run*.
3. **Measured vs simulated never mix.** Modelled quantities (e.g. a
   slept sensor period) are labelled MODELLED in the same table they
   appear in.
4. **Failures are results.** A run that falsifies or weakens a claim
   gets a file here exactly like a win does.
5. Summaries may quote headline numbers from these files, with a link
   back. The file here is canonical; the summary is a pointer.

## Existing canonical sources (pre-results/ era, 2026-11-01)

The three `thor/` files in this folder are **summary entries** for the
first day's work; their canonical full texts remain where they were
written (do not duplicate them):

| Entry | Canonical full text |
|---|---|
| `thor/2026-11-01-feasibility.md` | `docs/FEASIBILITY.md` |
| `thor/2026-11-01-thor-cuda-play.md` | `experiments/thor-cuda/PLAYLOG.md` |
| `thor/2026-11-01-workspace-verification.md` | `docs/THOR-VERIFICATION.md` |

From the next run onward, write the result file here first and make
the prose a pointer to it.
