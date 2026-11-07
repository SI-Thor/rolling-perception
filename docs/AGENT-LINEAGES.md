# AGENT-LINEAGES — the world's agent systems, surveyed, and the slate for Lineages C, D, E

This document maps the substantial Minecraft-agent and agent-community
systems in the published literature onto one question: which of them can
live in our Paper world, as what, and at what cost. It then fixes the
fielding slate for Lineages C, D and E against the two lineages already
in the world — **A** (Craftmind reflex engine with pulse-authored
scripts) and **B** (a Voyager-pattern skill-library agent) — maximising
architectural diversity per unit of effort. The shared exam (the
settle-in curriculum), the scoreboard, and the skill pond are the
commons every lineage is fielded into; §4 names the knowledge formats
the pond should adopt, taken from the systems below.

Fielding constraints, stated once. A lineage lives in the world as a
**Paper protocol client** (a Mineflayer-class bot body) or it does not
live there at all: the server admits protocol clients and headed
clients, nothing else. Minds are reachable from the fleet's local
models and subscriptions, metered through the league governor. The
world box is a small purse; heavy bodies and heavy minds are placed on
the Thor, never on the world box.

## 1. The systems

### Project Sid / PIANO (Altera, 2024)

Architecture: ~10 modules run in parallel at different timescales —
memory, goal generation, social awareness, action awareness, talking,
skill execution — reading and writing one shared state, with a single
bottlenecked **Cognitive Controller** synthesising one coherent
decision stream so the agent never says one thing and does another.
Agents have no vision; perception is text/symbolic. At 500 agents the
runs produced specialised roles, a drafted-and-amended constitution,
tax votes, and memetic religion spread (Altera.AL et al.,
arXiv:2411.00114).

FIELDCRAFT: the *pattern* fields; the code does not. Sid is a research
report with partial code release, not a runnable agent. Its agents ran
in Altera's own harness, and runs above ~1,000 agents exceeded the
Minecraft **server's** limits — the world broke before the minds did.
Re-implementing PIANO on a Mineflayer body is a design exercise, not a
port; our tiered rotation already rhymes with it.

Steal: **the bottlenecked controller.** One slow decider broadcasting
coherence to fast parallel modules is the correct shape for any
lineage that both acts and talks — it is the direct cure for
says-one-thing-does-another.

### Voyager (Wang et al., NVIDIA/Caltech, 2023)

Architecture: a Mineflayer body driven entirely by code a frontier LLM
writes — an automatic curriculum proposes the next task from state, an
iterative prompting loop writes and repairs a JavaScript skill against
execution feedback, a self-verification critic judges success, and
verified skills enter an embedding-indexed library for reuse and
composition. No fine-tuning; learning is the library (arXiv:2305.16291).

FIELDCRAFT: **fields natively** — this is Lineage B. Protocol body,
subscription mind, no adaptation beyond version pinning and governor
metering.

Steal: **self-verification as a separate, named component.** Voyager's
own ablation prices it: removing the verifier cut discovered items by
73%. In pond terms, a skill is not a skill until a verifier that is
not its author has passed it.

### Ghost in the Minecraft — GITM (OpenGVLab / Shanghai AI Lab, 2023)

Architecture: three LLM roles over text. A **Decomposer** recursively
breaks a goal into a sub-goal tree guided by a text knowledge base
(wiki-derived recipes and tech-tree facts, consulted as data); a
**Planner** emits sequences from a *closed vocabulary* of structured
actions (craft, mine, equip, …) and records successful action lists
into a text memory; an **Interface** executes them. No learned
controller, no code generation, no GPU — the reference runs are CPU
only. It was the first system to obtain every item in the Overworld
tech tree (arXiv:2305.17144).

FIELDCRAFT: **fields with one bounded adaptation.** The
Decomposer/Planner/knowledge/memory are pure text and port unchanged.
The original Interface drove key/mouse-level control; ours replaces it
with Mineflayer executors implementing the same structured actions —
a finite, enumerable piece of work, because the vocabulary is closed
by design.

Steal: **knowledge as data files.** The tech tree and recipes live in
consultable text the planner retrieves, not in weights and not in
prompts-from-memory — facts are versioned, auditable, and shared by
every lineage that wants them.

### JARVIS-1 (CraftJarvis, 2023)

Architecture: a multimodal LLM planner (visual input via a
MineCLIP-chained model) dispatching sub-goals to learned
goal-conditioned controllers (STEVE-1 class), augmented with a
**multimodal memory** storing (situation, plan, outcome) triples of
successful planning experiences, retrieved to seed new plans. 200+
tasks; roughly 5× the prior state of the art's reliability on
ObtainDiamondPickaxe, with the gain attributed mainly to memory
retrieval (arXiv:2311.05997).

FIELDCRAFT: **half fields.** The planner and the memory store are
text-and-retrieval and port directly. The controllers do not — they
are pixel policies that need a headed client body. A fielded
JARVIS-pattern lineage therefore runs the planner over scripted
executors and accepts a lower ceiling on motor novelty in exchange
for the memory machinery.

Steal: **the (situation, plan, outcome) triple as the unit of
experience.** It is the most portable knowledge format in this survey:
lineage-agnostic, evidence-carrying, and directly retrievable by any
other lineage's planner.

### STEVE-1 (Lifshitz et al., 2023) and MrSteve (Park et al., ICLR 2025)

Architecture: STEVE-1 is an instruction-tuned VPT — a behaviour prior
trained by behaviour cloning on ~70k hours of video, conditioned on
goals through a MineCLIP latent space via a text→latent prior —
following short text/visual instructions at 20 Hz from pixels
(arXiv:2306.00937). MrSteve keeps that controller and repairs its
known defect, a 128-step FIFO memory, with **Place Event Memory**: an
episodic index of what happened, where, and when, clustered over
places and events, which the agent consults to alternate exploration
and task-solving (arXiv:2411.06736).

FIELDCRAFT: **does not field as a protocol client.** Both are pixel
policies requiring a real client body and continuous GPU inference.
The only seat for one in our fleet is a headed client driven by the
policy — a separate programme (see Lineage F, deferred).

Steal: **Place Event Memory.** A what-where-when index is precisely
what a shared world ledger wants to be when it grows up: every pond
entry and scoreboard event should carry place and time keys so any
lineage can ask "what happened near the river, ever".

### MineDojo and VPT (Fan et al., 2022; Baker et al., 2022)

Architecture: MineDojo is an environment and knowledge framework —
thousands of tasks plus an internet-scale corpus (videos, wiki,
Reddit) — whose signature agent technique is MineCLIP, a
video-language model used as a *learned reward function* for RL
(arXiv:2206.08853). VPT is OpenAI's foundation behaviour prior:
behaviour cloning over internet video labelled by a learned inverse
dynamics model, the substrate STEVE-1 and the JARVIS controllers are
built on (arXiv:2206.11795).

FIELDCRAFT: **neither fields.** MineDojo is a laboratory, not an
agent; VPT is a pixel policy under the same verdict as STEVE-1. Both
are cited here because half the field stands on them.

Steal: **the learned judge.** MineCLIP's trick — score behaviour by
video-language alignment with a stated goal — is an automated
scoreboard judge: footage in, verdict out, no hand-written checker.
Our perception stack already produces the footage and the embeddings
such a judge would consume.

### Generative Agents — Smallville (Park et al., 2023)

Architecture: each agent is a **memory stream** (an append-only
natural-language log of observations, plans and reflections) with
retrieval scored by recency, self-rated importance, and relevance;
periodic **reflection** synthesises higher-level conclusions back into
the stream; behaviour is a day-plan recursively decomposed into
hours and moments, revised on interruption. Twenty-five agents in a
2D town produced unscripted social coordination (the Valentine's Day
party) from one seeded intention (arXiv:2304.03442).

FIELDCRAFT: **the architecture fields; nothing else does.**
Smallville has no Minecraft body — its world is a sprite sim with
symbolic affordances. Porting means writing the verb bridge between
plan steps and a Mineflayer body, and accepting Park's documented
cost curve: full memory-stream cognition for 25 agents for two days
was thousands of dollars in 2023 tokens, so this lineage lives or
dies by governor metering and duty-cycling.

Steal: **reflection as a written, retrievable artefact.** A lineage
that periodically publishes "what I have concluded about this world
and its inhabitants" gives every other lineage's smith a diary to
mine — the cheapest cross-lineage learning channel that exists.

### Odyssey (Liu et al., ZJU VIPA, IJCAI 2025)

Architecture: a planner-actor-critic LLM agent over a **curated**
skill library — 40 primitive skills and 183 compositional skills, all
Mineflayer JavaScript — with domain knowledge supplied by a LLaMA-3
fine-tuned on 390k wiki-derived QA pairs (MineMA), reaching
near-frontier performance with an open model (arXiv:2407.15325).

FIELDCRAFT: **fields — and endows the commons.** The library is open,
Mineflayer-native JavaScript; the model weights are public. As a
lineage it sits in B's family (skill libraries), so its highest use
is not another seat but a **pond endowment**: 223 pre-built,
human-audited skills any lineage may adopt on day one, each carrying
Odyssey's own provenance.

Steal: **the primitive/compositional split.** Few primitives, many
named compositions. It is the pond's hygiene rule: compositions are
the shareable unit; primitives stay few, stable, and audited.

### Also surveyed, briefly

- **Steve** (YuvDwi; digested in CRAFTMIND-MAP.md): a Forge mod
  running agents as in-world entities under one whole-plan cloud call
  per command. Does not field — modded body on server *and* clients —
  and stands as the survey's cautionary pole: maximal deliberation,
  no spend accounting, no learning loop.
- **MineAgent** (MineDojo's RL baseline): a pixel/RL agent that
  scores near zero on hard-exploration tasks in independent
  reproductions; cited only to close the RL branch of the family
  tree.
- **Optimus-1** (2024): a JARVIS descendant replacing flat memory
  with a hierarchical knowledge graph plus an experience pool —
  evidence the memory format, not the planner, is where this family's
  progress is happening. Supports the Lineage E bet below.

## 2. The slate

Lineages A and B field a reflex school and a code school. The slate
below adds a *deliberation* school, a *social* school, and a *memory*
school — three axes neither A nor B varies — and defers the one
remaining axis (learned motor priors) with its reason stated.

| Lineage | Pattern | Body | Mind placement | Learning loop | Effort |
|---|---|---|---|---|---|
| C — Deliberator | GITM | Mineflayer + closed structured-action executors | Thor, local coder via governor, pulse-rate | Successful action lists → text memory | One long evening – a weekend |
| D — Villager | Smallville | Mineflayer + fixed survival substrate | World box, duty-cycled 1–2B; reflection escalates to Thor | Memory stream + reflection rewrites plans | Days (2–4 evenings) |
| E — Archivist | JARVIS-1 | Mineflayer + scripted executors | Thor; planner + retrieval over the triple store | (Situation, plan, outcome) triples accumulate | Days (2–3 evenings) |
| F — Pixel body | VPT / STEVE-1 | Headed client driven by a learned policy | Thor GPU, 20 Hz inference stream | None at fielding (frozen prior) | Deferred — separate programme |

### Lineage C — the Deliberator (GITM-pattern)

A Mineflayer body whose entire action surface is a closed vocabulary
of structured actions, planned over by a Decomposer/Planner pair
consulting the shared text knowledge base. No code is ever generated;
the mind composes only what the body provably knows how to do.

- **Distinctive strength:** long-horizon reliability per unit of
  mind-spend. GITM finished the tech tree on CPU with text files;
  on the settle-in exam this is the lineage most likely to be boring
  and finished while others are still repairing scripts.
- **Distinctive failure mode:** the vocabulary ceiling. Anything the
  action set cannot express does not exist for this agent, and when
  world state diverges from plan assumptions it replans from the same
  closed set — it will fail *legibly*, in the open, at the same wall
  repeatedly.
- **What it teaches the others:** its successful action lists are
  pond-ready recipes in the exact form A and B can execute. If C's
  boring reliability beats B's code freedom on the scoreboard per
  governor-second, the commons learns something true about where
  freedom is worth its cost.

### Lineage D — the Villager (Smallville-pattern)

A Mineflayer body with a deliberately thin fixed skill substrate,
whose mind is a memory stream with scored retrieval, scheduled
reflection, and a day-plan decomposed to the hour. It is the only
lineage whose primary optimisation target is *being a someone* —
continuity of self, relationships tracked across days, conclusions
drawn and revised.

- **Distinctive strength:** social legibility. It narrates itself,
  remembers the other citizens as individuals, and generates the
  in-world social signal (greetings, requests, gossip, grudges) that
  makes a world of agents read as a community rather than a benchmark.
  It is also the natural first citizen of the world box's own slow
  mind: its tempo is the world's tempo, and it fits the measured
  memory purse duty-cycled.
- **Distinctive failure mode:** competence. Generative agents are
  documented to fumble spatial and mechanical norms; this one will
  die charmingly and often early on, and its per-decision cost is the
  highest in the slate unless the governor holds it to a pulse.
- **What it teaches the others:** its reflections are published
  diary. A and B's smiths gain a readable account of the world —
  who is reliable, where the danger is, what changed — written by
  the only resident whose job is noticing. If cooperation in this
  world ever pays, D is where the request that starts it will come
  from.

### Lineage E — the Archivist (JARVIS-pattern)

A Mineflayer body with scripted executors, planned over by an LLM
whose context is seeded by retrieval from a growing store of
(situation, plan, outcome) triples — situations keyed by the world
digest and place/time indices, in MrSteve's what-where-when shape.
It begins stupid and becomes, measurably, less stupid in exactly the
situations it has survived before.

- **Distinctive strength:** compounding reliability. JARVIS-1's
  headline gain came from retrieval, not from a better planner; this
  is the only lineage whose exam performance is *expected* to improve
  run over run on identical machinery, which the scoreboard can show
  as a slope rather than a score.
- **Distinctive failure mode:** the cold start and the confident
  mismatch. Early, the store is empty and the lineage is a planner
  with amnesia; later, a retrieved plan whose situation only
  resembles the present one will be executed with borrowed
  confidence. Its failures will look like superstition.
- **What it teaches the others:** the triple store *is* a pond
  format candidate. If E's triples prove retrievable-useful to C's
  planner or B's curriculum, the commons has found its interchange
  unit; if they only ever help E, that is also a finding, priced at
  one lineage.

### Lineage F — deferred, with the reason

A learned pixel-policy body (VPT/STEVE-1 class) is the one major
architectural axis the slate omits, deliberately. It requires a
headed client driven at policy rate with GPU inference streamed from
the Thor — a real programme with its own seat, its own failure
budget, and a claim on the world box's scarcest resource (the one
headed client the box can afford is currently the camera). It is
noted here so the omission is a decision on record, not an oversight:
when the camera seat and the policy seat can be the same seat, F
reopens.

## 3. What the commons adopts

Four formats, each taken from the system that proved it:

1. **Skills are code + description + a verifier's pass** (Voyager),
   organised as few primitives and many named compositions (Odyssey,
   whose 223-skill library is the pond's founding endowment).
2. **Experience is (situation, plan, outcome) triples** (JARVIS-1),
   keyed by what-where-when (MrSteve), so retrieval is by resemblance
   *and* by place.
3. **Facts are data files** (GITM): recipes, tech tree, and world
   facts live in consultable text every lineage reads — never baked
   into one lineage's weights or prompts alone.
4. **Reflections are published** (Smallville): any lineage may write
   diary; every smith may read it. Cross-lineage learning begins as
   reading, and only later, if the scoreboard justifies it, as
   adoption.

And one judge: footage-scored verdicts in the MineCLIP pattern —
the scoreboard's automated half reads what the camera saw, so that
"did it settle in" is answered from the world's record, not from any
lineage's self-report.

## Sources

Altera.AL et al., *Project Sid*, arXiv:2411.00114 (2024) ·
Wang, G. et al., *Voyager*, arXiv:2305.16291 (2023) ·
Zhu, X. et al., *Ghost in the Minecraft (GITM)*, arXiv:2305.17144 (2023) ·
Wang, Z. et al., *JARVIS-1*, arXiv:2311.05997 (2023) ·
Lifshitz, S. et al., *STEVE-1*, arXiv:2306.00937 (2023) ·
Park, J. et al., *MrSteve*, arXiv:2411.06736 (ICLR 2025) ·
Fan, L. et al., *MineDojo*, arXiv:2206.08853 (2022) ·
Baker, B. et al., *Video PreTraining (VPT)*, arXiv:2206.11795 (2022) ·
Park, J.S. et al., *Generative Agents*, arXiv:2304.03442 (UIST 2023) ·
Liu, S. et al., *Odyssey*, arXiv:2407.15325 (IJCAI 2025) ·
House studies: CRAFTMIND-MAP.md, STUDY-CUA-MASTER.md (this repo).
