# La-JEPA Replication Spike — VERDICT (filed 2026-11-08, closing the PENDING item)

*Paper: Clement et al., "La-JEPA: Compact Robot Policies with Latent World
Modeling", arXiv 2611.08156 (Nov 2026). Official repo empty at audit; no
official weights — minimal faithful re-implementation. Full record: Thor
`~/la-jepa-spike/` (METHODS.md pre-registration, README.md write-up,
results/variant_{A,B,C}.json). Pre-registration written before training;
kill criterion not edited after results.*

## Verdict (one sentence)

The portable claim is **MIXED, and its feature-space half is DEAD on our
bench**: the future-prediction loss helps OOD as the paper says (B beats A
OOD), but the VAE-latent arm beat the JEPA arm OOD by ~8.6x — the opposite
of the paper's headline direction — under our photometric-only OOD arm,
which is a narrower shift than the paper's layout/object/camera suite, so
the JEPA-vs-VAE question is settled negatively *for this bench and this
OOD regime*, not for the paper's.

## Arms completed (all three; identical data/splits/budget, seed 42, 3,000 updates)

Proxy: open-loop action-chunk MSE on LIBERO-Spatial demos
(nvidia/LIBERO_LeRobot_v3; 432 episodes as converted, 382 train / 50 test;
7,456 train windows, 501 test windows; agentview only). OOD = test-time-only
photometric perturbation (brightness/contrast/wash/blur); future targets
always unperturbed. Train-mean yardstick IID MSE 0.291.

| Arm | Representation | Future loss | IID MSE | OOD MSE | OOD/IID |
|---|---|---|---|---|---|
| A | V-JEPA 2 frozen | no | 0.0721 | 1.0627 | 14.7x |
| B | V-JEPA 2 frozen | yes | 0.0746 | 0.8229 | 11.0x |
| C | conv VAE (ours, 2,000 upd, loss 0.0017) | yes | 0.0829 | 0.0959 | 1.16x |

## Against the pre-registered kill criterion

- Future-prediction half: kill condition (1) was B_OOD >= A_OOD. B_OOD
  0.8229 < A_OOD 1.0627 (-22.6% relative) => NOT dead; supported at proxy
  fidelity on the final-step reading, with IID slightly worse (+3.4%).
  Caveat kept in the record: at step 500 A was better OOD than B
  (0.4258 vs 0.4437); both JEPA arms drift badly OOD as they fit IID
  (A 0.4258 -> 1.0627; B 0.4437 -> 0.8229) while IID plateaus ~0.071-0.075.
  C shows no such drift (0.0949 -> 0.0959).
- Feature-space half: pre-registered test was dead if C_OOD <= B_OOD.
  0.0959 <= 0.8229 => DEAD on our bench. Working hypothesis (labelled as
  such): a per-frame reconstruction VAE is unusually robust to exactly
  photometric shifts, while frozen JEPA patch features move substantially
  under them; the paper's JEPA advantage concentrates in layout/object/
  camera shifts this proxy cannot produce.

Paper numbers (their bench, S policy, for scale only — never same-scale):
future loss +2.12 pp LIBERO-Plus, +7.0/+3.7 RoboTwin; JEPA vs VAE features
+2.0 IID/+6.0 OOD LIBERO, +15.9/+16.0 RoboTwin.

Relation to the fleet's earlier JEV result: that was JEPA-as-DESCRIPTION
failing (play-footage embeddings measured the camera; transcript 6/7,
I-JEPA 0/7, V-JEPA 1/7). This spike is JEPA-as-CONTROL-substrate. Neither
predicts the other; this mixed verdict does not rehabilitate the
description use.

## What a future attempt would need that this one didn't have

1. The real LIBERO simulator stack (MuJoCo 3.3.2 pinned) for closed-loop
   success rates, with the paper's corrected LIBERO-Plus instructions.
2. V-JEPA 2.1 weights (we used the rack's V-JEPA 2) and both cameras.
3. ~150k-update budget (we ran 3k, ~2%) and >= 3 seeds — the step-500 vs
   step-2999 A/B OOD flip shows single-checkpoint, single-seed readings
   are fragile.
4. An OOD suite with layout/object/camera variation, not photometric-only
   perturbation — the regime where the paper's headline actually lives.
5. The paper's dual-DiT flow-matching architecture if mechanism-level
   fidelity is wanted (we preserved the mechanism — shared-trunk
   predictive supervision, actions never attending future — with a plain
   transformer trunk and a learned task embedding in place of FLAN-T5).

## Process note (for the record)

A/B completed cleanly 2026-11-08 ~12:36 AKST. Variant C took the rest of
the day: recurrent unexplained SIGTERM kills of long Thor jobs (killer
never identified), a `train_vae.py` destroyed by successive shell patches
(recovered by clean rewrite), and the root-cause bug — a window's
contiguous frame span is 47 frames (16 ctx + 15 gap + 16 future);
concatenating and reshaping to 32 silently truncated/misaligned it.
Encoding ctx and future as separate 16-frame clips (as the JEPA extractor
always did) fixed it; encode then completed in 434 s.
