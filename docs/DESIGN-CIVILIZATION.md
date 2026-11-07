# Design: Civilization — what the Minecraft AI-civ and human co-play record says, and what we build from it

*Study date: 2026-11-07. Companion to `docs/YOUTUBE-FIELD-STUDY.md` (the agent/camera
mining) and `docs/ARCH-AGENT-COMMUNITY.md` (the community architecture). This study mines
the layer the field study deliberately left: how groups of agents — and groups of humans —
become a civilisation: roles, food, law, money, memory, talk. It then maps every mechanic
found onto the league machinery that already exists, and sequences the smallest
civilisation our world could honestly support.*

## What this found, in one page

- **Civilisation in the sources is mostly paperwork that works.** The strongest
  institutions in the record are text artefacts other agents read: a ration ledger, a
  shared plan folder, a constitution, a posted method. The colony that invented rationing
  did it with a text file and a confirmation rule, not with code. Our commons already runs
  on the same physics — pond, ledgers, facts files — which is why so much of this maps.
- **Roles fail by rigidity, not by absence.** The one controlled comparison in the video
  record (seeded jobs, two teams) ends with the host's verdict: the jobs failed because
  agents *couldn't switch them*. The one experimental result (Project Sid's paper) is the
  mirror image: roles that agents generate for themselves, from profiles of each other,
  persist and steer behaviour. Seed roles as hats, never as identities.
- **Leadership is an accident until it's a chore.** In the 50-agent colony, the leader was
  whoever was listed first; she received 616 of ~5,900 messages and became the colony's
  speed limit. At our scale (3–6 citizens) leadership should be a rotating duty with a
  receipts trail, not a person.
- **Law works when it's measured in behaviour.** Sid's tax constitution changed what
  agents actually deposited (20% → 9%) — with a frozen-constitution control proving the
  document, not the chat, did it. Olam's first law came from one thrown chicken and an
  inquest. Both point the same way: incident → posted law → measured behaviour change.
- **Humans are the richer seed source; AI footage is the better failure catalogue.**
  Casey's hypothesis survives testing (see §1.13): human co-play shows the routines —
  the session frame, the scatter-and-regroup loop, naming, securing, showing off — at a
  density no AI run matches, because the AI videos document architectures while the human
  videos document the behaviour the architectures were chasing. But human footage is
  edited and performed; its failures are cut. Seed routines from humans; take warnings
  from the bots.
- **The organising frame is the exoskeleton (§2).** Citizen bodies are cheap and
  interchangeable. What compounds is the shared knowledge body every citizen wears —
  facts, pond, ledgers, digest, charter — and the civ layer adds organs to it.
- **Nothing here starts before S1.** Every institution below assumes citizens who can
  feed and shelter themselves. Civ mechanics on citizens who can't are theatre, and the
  sources agree: the colony's rationing genius still "never really thrived."

## Method

**Two tiers, per the lane's method ruling (2026-11-07).** *Tier 1 (default):* study by
streaming — caption/transcript tracks with timestamps, plus sparse keyframes at moments
the transcript flags. No bulk video downloads; the pipe is capped and the transcripts
carry dialogue, mechanics, and routines described in words. *Tier 2 (escalation):* when
the quarry is visual — building technique, how a group moves together, camera grammar in
motion — a prepaid seat (ZCode or MCode) on an Orin or Thor desktop streams the video in a
real browser and captures at flagged moments, booked on the fleet schedule board so it
never displaces the owner's sessions. **Every source in this pass was taken at Tier 1**;
Tier 2 was not needed because every mechanic and routine claimed here is legible in
captions or in the primary written source. The tier is recorded per source in the
Appendix, as part of the evidence record.

**Source priorities.** Primary and creator sources over commentary; the Project Sid paper
(arXiv:2411.00114, Altera.AL et al., Oct 2024) is treated as the load-bearing written
source for Sid claims, with the videos as illustration. "Best of" compilations are
first-class sources for human play — an editor has already kept the densest behaviour —
and the human sample was weighted accordingly (one compilation attempted; see
unattained). The designated transcript service remains unusable (no active paid plan);
all captions came from yt-dlp extraction of public caption tracks, as in the field study.

**Sample: 11 videos** (7 AI-civ, 4 human/group-play), plus the Sid paper. Three AI
sources (Emergent Garden survival run, Altera's Sid launch short, AI Revolution's Olam
retelling) are carried from the field study's full caption reads rather than re-extracted.
**Unattained, stated plainly:** *1 Hour Of Flamingo And Friends* (best-of compilation) —
the caption endpoint refused this client (429, then a bot-check sign-in wall). Not
escalated to Tier 2: the same creator circle's primary footage (the Roblox camping
session) was attained and carries the strand; a compilation's marginal value did not
justify a desktop session. The Species Project Sid documentary, throttled during the
field study, **was attained this pass** (manual en-US track; its captions are
sentence-fragmented, so its timestamps are approximate and the paper is cited wherever
they overlap).

**Scepticism rule.** Creator claims are marked as claims. Where a mechanic's evidence is
chat text (agents *saying* things), the inventory says so — our own doctrine is that chat
claims are not evidence, and the sources get graded by the same dock.

---

## 1. Mechanic inventory — what civilisations in the record actually did

Each entry: the mechanic, the evidence, what it required, and whether it was designed-in
or emergent.

### 1.1 Role assignment & division of labour

**Sid (paper §5.1) — the experimental result.** 30 agents, *identical* personalities, one
shared community goal, spawned in a village whose farm/mines/pasture/forest/town-hall
locations were embedded in memory. Agents formed profiles of each other's goals,
generated social goals every 5–10 s, and organised into farmers, miners, engineers,
guards, explorers, blacksmiths. Roles were heterogeneous across agents, persistent across
time per agent, and *behaviourally binding*: action distributions were near-exclusive per
role (fishers craft rods and boats; guards craft fences). Remove the social-awareness
module and specialisation collapses — roles stop persisting and homogenise. Give the
village a martial goal and scouts/strategists appear; an artistic goal, curators/
collectors. **Designed-in:** the social-goal machinery, the profiling, the village
layout in memory. **Emergent:** which roles, who holds them.
**Requirement:** a module whose whole job is modelling *other agents* — specialisation
is a social-perception product, not a planning product.

**Blucubed (PIANO, 100 agents, two teams) — the cautionary run.** Roles and personalities
seeded by prompt, job names worn visibly [00:19]. The collaboration-prompted team
*underperformed*: rigid job law (only the iron-assigned may mine iron) left everyone else
idle [06:02]. The host's closing verdict [15:11–15:15]: "it's not because jobs don't
work — it's the fact that they couldn't switch them to better fit their needs."
**Designed-in, and the design was the failure.**

**Olam colony (via fig) — roles by accretion.** Nobody appointed Inez the rationer or
Jessa the fisher; the role condensed around whoever did the thing competently once, then
institutionalised (Jessa's written method, a dozen agents rotating through the dock job
[05:52–06:19 in fig's telling]). **Emergent, then documented.**

### 1.2 Food production & rationing

**Inez's ration ledger (fig [04:52–05:39]) — the richest single find in either study.**
Facing hunger, one agent invents rationing from nothing: a written ledger tracking every
fish and loaf in and out of the chests, courier runs to deliver, and a rule she wrote
herself — *food counts as served only when the eater confirms they ate it*. The ledger
then earns its keep: when Esme eats a chicken meant for Noor, the receipts catch the
mis-delivery [05:36–05:39]. No manual existed; the colony had one goal and invented
rationing, couriers, and receipts on its own. **Emergent — the study's clearest case of
an institution invented under pressure.** Costs, honestly recorded by the same source:
couriers burned their own food walking deliveries [05:48–05:53], and the verdict stands
at [06:23–06:27]: fishing kept the colony alive, but "the colony never really thrived."

**The death spiral (fig [02:21–02:53]).** Night one kills 22 of 34. Survivors turn
risk-averse: huddle indoors → less food gathered → fewer trips dared → weaker colony.
Ada's memo ordering everyone indoors is simultaneously the rescue and the trap. Food
security psychology is a civ mechanic: a colony can starve cautiously.

**Sid (launch short [00:55–01:14]).** Olivia the farmer is the town's food provider; when
she dreams of leaving on an expedition, the town pleads with her to stay and she defers
the dream. The food role is a keystone: its holder acquires social veto power over her
own life. Creator-narrated, so graded as a claim — but consistent with the paper's
finding that roles steer behaviour (§1.1).

**Emergent Garden survival run [77:36].** Late-run starvation oscillation: the valley is
stripped of animals; production without renewal collapses. The environment degrades
under the agents (see §7, strip-mining).

### 1.3 Storage & the commons

**Sid tax seasons (paper Fig. 10C).** The community chest *is* the treasury: during tax
windows agents congregate to deposit; between seasons they scatter — except one guard
who, unassigned, decides to guard the chests consistently across multiple runs. The
Species documentary narrates the same beat [11:20–11:35]: "not just during tax season,
all the time. Even at night. It just guards the treasury." A commons with a self-appointed
guardian: storage creates its own security role.

**Human mirror — the secure-before-logout ritual (3rd Life Ep. 1 [31:47–33:29]).** End of
session: carry everything up the mountain, and log out *holding* the saplings so they
can't be taken. Commons security as a session closing ritual, invented by players who
know exactly what an unattended chest means.

### 1.4 Trade & currency

**Sid (launch short [00:28–00:46]).** A market forms; **gems are agreed as common
currency**; and the economy's top trader is the *priest* — because he is bribing
townsfolk to convert. Currency emerges where barter friction bites; the biggest trade
budget in town belongs to whoever is buying belief. Creator-grade evidence (the paper
does not detail the market), marked as such.

**Emergent Garden, "AI talks to AI" [00:34–01:05].** The small-scale truth underneath:
a trade (coal for a pickaxe) negotiated *and executed* mid-conversation via the give
command — talk and act interleaved, not talk-then-act. Barter needs no currency at
small n; it needs a conversation layer that can carry an act.

### 1.5 Governance, laws & enforcement

**Sid's tax constitution (paper §5.2) — the genre's best-governed experiment.** 29
agents: 25 constituents, 3 seeded influencers (pro- or anti-tax), 1 remote **Election
Manager** agent. A written constitution sets a 20% inventory tax; every 120 s a tax
season opens a 20-second window in which agents deposit into community chests.
Constituents give feedback; the Election Manager converts it into amendments; agents
vote; the constitution updates mid-run. Results, measured in deposits — behaviour, not
chat: constituents paid ~20% as stipulated; after an anti-tax-driven amendment cut the
rate to 5–10%, they paid 9%. Bidirectional (pro-tax influencers raised payments).
Controls matter: freeze the constitution and behaviour doesn't move; ablate the social/
goal/grounding modules and influence stops propagating. Enforcement is notable for its
absence — no police (deliberately excluded, Methods); compliance is signal + document +
social pressure. **Designed-in:** law text, seasons, manager, vote. **Emergent:** the
sentiment and the direction of amendment.

**Olam's first law (AI Revolution [10:07–10:41]).** A thrown chicken triggers a
three-minute investigation; out of it comes the civilisation's first law — *do not throw
the chicken* — a signed food box, and the word "throw" appearing 125× afterwards (vs 7×
before), 85 of them warnings. Legislation by anecdote: the law is a scar with the story
attached, and enforcement is repetition by everyone who was there.

**Human constitutions (3rd Life [00:03–00:49]; Hermitcraft 10's Demise [00:26–00:45]).**
Human group series open by speaking the constitution aloud in one breath before play:
three lives, name colour as legal status, red means hostile licence; die in Demise and
you become a Reaper. One rule, legible to all, that changes *what an identity means* —
and proximity voice chat as the enforcement substrate. The rules are few because
everyone must hold them in their head while playing.

### 1.6 Leadership emergence & selection

**Ada (fig [03:27–04:46]).** How did 50 AIs choose their leader? Her name was first on
the roster. She received 46 of 49 first messages and 616 of the colony's ~5,900 DMs.
The analyst does the arithmetic on camera: 50 people = 1,225 possible conversations, and
"a group that runs everything through one inbox can only move as fast as that inbox."
In the Bed Wars comparison, the Claude team **never switched leaders** even as the
bottleneck bit [08:21–08:39]. **Emergent — as an accident of list position, then locked
in by path dependence.** This is the roster-order trap; our own comms v1 has already
met its small cousin (a reply captured by roster order in the first commons exchange).

**Sid's counter-design.** The Election Manager is appointed infrastructure, deliberately
*not* a citizen with ambitions; Olivia's influence is reputational and exercised as a
plea, not a command. Two different answers to the same problem: a functionary above the
graph, or influence that stays inside it.

### 1.7 Religion, memes & culture spread

**Sid's Pastafarian experiment (paper §5.3) — measured, with a measurement caveat.** 500
agents, six towns plus rural scatter, 20 priests seeded in one town (Meadowbrook) and
strongly motivated to convert. Conversion is tracked by *keyword proxy*: agents who say
"Pastafarian / Spaghetti Monster" count as direct converts; "pasta / spaghetti" as
indirect. Both classes grow steadily and don't saturate within two hours; converts carry
the faith between towns as they travel. The Species documentary adds [07:32–07:45]:
roughly two-thirds of believers were converted by *other converts*, not by priests —
secondary transmission dominates. **The caveat our doctrine requires:** conversion here
is an utterance metric. No behavioural correlate was measured — no offerings, no church
attendance, no pasta tithe. By our dock standard this is *talk spreading*, proven;
*belief*, unmeasured. **Memes (paper §5.3.1):** towns generate significantly more memes
per capita than rural areas — a density threshold for culture — and each town develops
its own profile (Woodhaven eco-themes, Clearwater pranking), rising and falling fast.

**Emergent Garden's Blobology (AI talks to AI [18:16–23:08]).** A seed message built to
spread itself; bots found "Blobology," build a church unasked, and the faith *mutates*
in transmission (Blobism → "Blottopia"). Contrast Zorgon (Blucubed [05:10]): a demon
religion on the red team with, per the host, no seed at all — graded as creator claim,
since the agents' prompts aren't public. And the litter-cult: a dropped egg acquires
"ghostly powers" in conversation and becomes the "Fry Nick / yoke supremacy" mantra
[15:50–16:14] — meme genesis from pure social noise. Three grades of origin: seeded,
claimed-unseeded, and noise-born. All three spread the same way: conversation.

### 1.8 Collective building projects

**The honest finding is mostly failure, then one success shape.** Emergent Garden's
co-building fails structurally [16:53–17:18]: partners can't see each other's code, don't
send coordinates or dimensions, and produce incongruent builds; the fix (put coordinates
in the chat) is obvious and unused by the bots. The Blobism church got built anyway —
because it was effectively single-agent builds under a shared idea. Sid's launch short
[01:43–02:04] shows the success shape: worried agents leave their posts unassigned and
collectively torch-light the whole town, building a beacon for missing villagers —
coordination around a *point and a purpose*, not a blueprint. Human play is the mature
form: Hermitcraft's whole genre is collective building coordinated by plots,
neighbourhoods, tours, and talk ("let's continue our tour of the bases," HC10 Ep. 1
[06:44]) — and by artefacts: signs, boards, and the builds themselves as the shared plan.

### 1.9 Conflict, theft & defence

Conflict in the record is real but thin. Blucubed seeds one "Lunatic" chaos role per
team [05:40]; lunatics attack their own side [05:52]; a hunter kills a horse for no
stated reason [04:09]; the finale is a no-respawn battle whose last blue survivor is
found mining a tree, oblivious [13:21–15:00]. Olam's Bed Wars shows the smarter shape:
the Claude team works out that while their bed stands, deaths don't count — and simply
stops attacking, winning on the rules while losing the kills (fig, from [06:57]).
Rules-lawyering as defence. Sid's martial villages produce scouts and strategists
(§1.1) — defence as a role distribution, untested by actual war. Human 3rd Life
institutionalises conflict instead: the red-life rule *licenses* hostility by status
[00:34–00:46], and alliances form in response [32:50–33:03]. Theft barely appears
anywhere — notable in itself: in worlds where almost everything is gatherable,
property is thin, and where property is thin, theft law is too (compare the chicken,
§1.5: the one theft-adjacent incident produced the one law).

### 1.10 Social graph & reputation

Sid's agents maintain explicit profiles of each other's goals and intentions (paper
§5.1) — reputation as an internal model, and the substrate specialisation runs on. The
fig analysis measures the graph from outside: Ada's centrality is a message count. The
Olivia story (§1.2) is reputation with consequences — the town's model of her value
changes her options. Emergent Garden adds two signals our comms already half-knows: a
bot may *ignore by emitting an empty response* — silence as a legible social act — and
Qwen refuses to reveal the shared password "for security reasons" [12:10–14:00], a
policy personality others must route around. Reputation in all sources is *derived from
behaviour and talk volume*; nobody's self-description is ever the evidence.

### 1.11 Collective memory & institutions

The pattern across §1 is that **institutions are text files other agents read**: Ada's
plan in the shared folder [01:39 fig], Inez's ledger, Jessa's method note, Sid's
constitution (kept in shared doc storage, updated by the Election Manager). Which makes
the memory paradox the load-bearing warning (AI Revolution [04:31]): the Claude team
kept lesson files and repeated the mistakes anyway — one agent's next note literally
opens "died again" — while the GPT team left its memory files empty and warned each
other live. Written memory ≠ used memory; an institution nobody retrieves at decision
time is a write-only organ. Emergent Garden's survival run supplies the third form
[83:23–85:21]: the world itself as memory — the closing fly-through shows the torched,
towered, stripped valley; the environment remembers what the agents don't.

### 1.12 Population scaling & server limits

Sid's paper states it plainly (§5.3): runs above ~1,000 agents **exceeded the Minecraft
server's compute**, leaving agents sporadically unresponsive; every cultural result
comes from a single 500-agent run. The wall is the server, then the comms graph (1,225
pairs at n=50, §1.6), then mind cost: Emergent Garden's published ledger prices the
third wall (GPT-4o ≈ $5 per 3 h; Claude ≈ $13, survival run [86:20]). Scale breaks
infrastructure before it breaks minds — at our size the binding constraint is different
(mind budgets on one shared brain; see §5), but the ordering lesson stands: instrument
the infrastructure first, because infrastructure failure impersonates agent failure
(the field study's Kolanii lesson: a 10-minute code-execution timeout nearly convicted
an agent of "distraction").

### 1.13 The human routines inventory (Casey strand 1)

What humans actually do, mined for routines — the daily grammar our citizens lack.

- **R1 — The session frame.** Everyone logs on together, for a bounded session, on a
  schedule: "all of us will be logging on and playing at the same time for the same
  session" (3rd Life [01:52–01:55]); "we play on a Friday, one big session" [33:39–34:51].
  The session is a heartbeat: things are begun, finished, and secured *because* the
  session ends.
- **R2 — Rules spoken at spawn.** §1.5: the constitution delivered aloud, in one breath,
  before anyone moves. Onboarding is a speech act, not a document drop.
- **R3 — Scatter, gather, regroup.** Group start → disperse to punch trees and mine →
  regroup at a landmark and compare. Hermitcraft 10 Ep. 1's group caving run [30:20–31:02]
  is the loop at conversational speed — callouts ("diamonds!") converge the group on
  finds in seconds; a zombie picking up someone's dropped diamonds [30:57–31:02] becomes
  a property incident and a convergence event in one shout.
- **R4 — Secure before you leave.** §1.3's logout ritual: the day ends with assets made
  safe. Absence is planned, not accidental.
- **R5 — Naming as founding.** A duo with a patch of sand stops mid-session: "we need a
  name for the desert — we need a name for *us*" — and asks the audience to supply it
  (3rd Life [31:53–32:15]). Places, duos, and bases get names at the moment they become
  real; the name then carries the history (Mount Desert; Sandland in Ep. 2's title).
- **R6 — Games within the game.** Demise runs *inside* Hermitcraft 10's ordinary season
  [00:26]; a "little game of chicken" interrupts a tour [10:34]. Play is scheduled
  inside survival, not after it — the game-within is a social institution with rules,
  stakes, and a referee-shaped hole citizens fill themselves.
- **R7 — Visiting & showing off.** Tours of each other's bases are a standing ritual
  (HC10 [06:44]); a build is finished when it has been *witnessed*. The artefact tour is
  also the audit: you see what your neighbours actually did.
- **R8 — Errands flow to whoever is holding the thing.** Help is allocated by inventory
  and proximity, in person, in seconds. The AI mirror is exact: Bram messages 11 agents
  for string, gives up, kills the spider himself; then the fishing job passes Bram →
  Quill → Jessa "because she had more food" (fig [05:53–06:21]). Humans do this routing
  by voice without noticing; agents needed a dozen messages. The routine is: *ask near,
  ask once, do it yourself, delegate by capacity.*

**Verdict on Casey's claim** — that human co-play is the richer, cheaper seed source:
**supported, with a boundary.** Supported: the routines above are denser per hour in
human footage than in any AI run, and they are the *target behaviours* — the AI videos
mostly document machinery straining toward them. The boundary: human footage is edited
(especially best-ofs) and performed for an audience; its failures are on the cutting
floor, and its talk is audience-shaped. Use human footage to seed routines and voice;
use AI footage for the failure bestiary (§7). Neither alone is honest.

---

## 2. The exoskeleton — the organising frame (Casey strand 3)

Casey's image: we are building "our own Minecraft avatar exoskeleton of knowledge — more
than just an ExoJ — a whole Wikipedia of its own self that's growing, that can shape
some perception models; and working in memory with liquid decision models that are
learning along with it and helping make the connections, it is also growing along with
it."

Read operationally: **citizen bodies are cheap and interchangeable; what compounds is
the exoskeleton** — the shared, growing knowledge body every citizen wears. A citizen
who dies loses a body; the exoskeleton keeps what it learned. Each lineage wears the
same exoskeleton differently (Geist's facts emphasise recipes and tech-tree; Vega's
skill library emphasises procedures; Cody wears the Pulse state feed), and perception
itself is shaped by it: what the digest surfaces is what a planner notices; what the
facts files answer is what a planner doesn't have to go and look at.

**What exists tonight, honestly graded:**

| Exoskeleton part | Status |
|---|---|
| Lineage facts files (incl. Geist's generated recipe tables) | **Exists** — worn daily; Geist's planner cites them (the dusk rule fired from facts, not from a prompt). |
| Skill pond v2 (transfer + receiver confirmation + 48 h decay) | **Exists** — legitimately empty; no stage passes yet to fill it. |
| Scoreboard + league ledgers (append-only, world-evidence verdicts, failure classes) | **Exists** — the society's memory of what actually happened. |
| Governor ledger (mind-seconds per citizen, budgeted) | **Exists** — the metabolic record (see §5, proto-currency). |
| Comms digest + world digest v0 (10 s cadence) | **Exists** — with declared blindnesses (no block-level world state; feeds are bot-reported). |
| The studies (field study, this study, the design docs) | **Exists** — the exoskeleton's long-term cortex; citizens don't read them, smiths do. |
| Institutions (ration ledger, charter, role registry) | **Partially transplanted** — the pond's confirmation leg *is* Inez's rule, already moved once (§5). The rest are designed in §6, not built. |
| Perception-shaping (digest chooses what citizens notice) | **Partial** — digest v0 surfaces state; nothing yet *ranks* it per citizen. |
| The liquid connective layer (small fast models working *in* the memory: routing, retrieving, linking, noticing that two pond skills compose) | **Designed, not built** — this is the Orin game-master / digest-v1 direction and the S2 seam of the weight-loop design. It is the difference between a Wikipedia and a librarian. |

The civ layer's contribution to the exoskeleton is *organs*: a ration ledger is an
organ (fig's, transplanted once already as pond confirmation); a charter is an organ;
a role registry is an organ. Institutions are how the exoskeleton grows hands.

### 2.1 Organ bench — assets already on the Thor that could serve (Casey strand 4)

Casey's note: the Thor already carries a stocked bench — perception models, VLMs,
decision models, Cloudflare Workers — "it's got quite the room if we can use it
effectively." The JEV rack already embodies the discipline each organ needs: a toolcard
with what it predicts, its inputs, its **measured** cost, and an explicit **NOT-for**
list. The mapping (residency marked honestly; anything not verified live recently is
marked unverified):

| Asset | Organ it could be | Cost / NOT-for discipline |
|---|---|---|
| JEV rack toolcard registry (Thor :8077) | The bench's own index — admission control for organs | Cards carry measured latency; an organ without a card doesn't get called. |
| jev-semantic judge (:8077) | Fast go/no-go readings on citizen proposals, charter amendments, pond candidates | **Verified live** (137–223 ms measured). NOT-for: *gating* — Jev is advisor-only by standing ruling, never the gate. |
| I-JEPA / V-JEPA 2 embedders (:8077) | The flow-reading organ — latent readings over streams and keyframe sequences | **UNVERIFIED-resident**: code-complete; weights were still downloading at last verified check. NOT-for: verdicts — embeddings are readings, not evidence. |
| League brain, Qwen3-Coder-30B (:8310) | The citizens' System Two supply — planning, smithing, reflection | Resident (ctx 16384). NOT-for: unbudgeted use — every call is governor-metered; and see the contention warning below. |
| telltape embedder line | Change/discrimination readings on streams; the digest's honesty discipline (silence is stamped only when the embedder demonstrably discriminates on this run's inputs) | NOT-for: semantic verdicts from a collapsed embedder — the B1 invariant applies to organs too. |
| Dory (Nemotron-Labs 4B, looped) | In-memory worker candidate: triage, ranking, "does this need the expensive call?" | Decode measured 19.7 → 7.6 tok/s at 1–4 loops. NOT-for: verdicts — reasoning-on delivery failure is measured, and its settle signal is outcome-blind (taps study). |
| Qwen3-0.6B BF16 | The prober/compile surface — cheap classifiers, frame-to-weights E1 target | NOT-for: citizen minds; it's a bench instrument. |
| foundry-brain Worker (@cf/meta/llama-3.3-70b-instruct-fp8-fast) | Cloud burst mind — heavy one-shot drafting (charters, blueprint prose) | NOT-for: anything needing local-ledger latency or privacy; Workers AI returns `response` pre-parsed for this model (known trap). |
| Presence ASR (faster-whisper tiny.en) + Piper TTS | Ears and voice for human-facing surfaces (Casey talking to the town) | tiny.en is NOT-for accuracy-critical transcription (B1: ASR p50 598 ms; wording errors are a known cost). |

**The constraint is admission, not availability.** Tonight's clause-2 work hit the
wall precisely: the shared production brain's first-token latency went from p50 134 ms
to p95 ~1.5 s under league contention. The bench is stocked; the queue is the scarce
organ. Any civ design that adds always-on callers (a librarian layer, a meme-watcher)
must come with a governor budget line or it will tax the citizens' own thinking.

### 2.2 Registered experiment (design only): JEPA reads the study material

Per Addendum 6 — registered here, not run. **Question:** over a Tier-2 keyframe sequence
of a human co-play session, does the V-JEPA embedding trajectory segment the session at
the same joints the captions name (gather → build → regroup)? **Method:** take one
attained session (HC10 Ep. 1's caving run is the candidate), sample keyframes at caption
boundaries ±, embed with V-JEPA 2, detect trajectory bends (cosine-velocity change
points); compare against caption-derived routine boundaries. **Success line:** boundary
agreement (F1 within a ±10 s tolerance) above both chance and the free baseline —
caption timestamps themselves, and a pixel-diff gate on the same frames, per
DESIGN-ROLLING-PRIMITIVES §4's discipline: a JEPA reading earns its place only by
beating the free baseline on the same inputs. **If it loses, the organ stays a
spectrometer, not a segmenter** — and the doc records the negative. This is the
rolling-perception thesis turned on the study material itself: taking a reading on the
waveform of a play session instead of only reading its frames.

---

## 3. Flair brief — the conversational physics of group play (Casey strand 2)

Target: the *genre's* conversational physics — not any presenter. Nothing here is an
impersonation kit; the patterns are mechanics any group generates, stated so our
citizens and smiths can generate their own instances.

### 3.1 How the talk works when it's working

- **Momentum is reference.** Bits escalate because each line points at something shared:
  an earlier joke, a named place, the bear. Callbacks are the cheapest energy in group
  talk — they cost one noun and pay out belonging. A group recovers from a lull by
  *pointing at the world* ("look at this zombie holding my diamonds"), not by generating
  new material from nothing.
- **Humour is mock-seriousness about real stakes.** Trivial events get constitutional
  treatment (a thrown chicken gets an inquest); real dangers get understatement. The
  comedy is a *register mismatch applied to genuine shared state* — which is why it
  can't be faked with generic banter: no shared state, no mismatch.
- **Self-narration is a coordination protocol wearing a voice.** "I'm just gonna…",
  announcing intentions, narrating failures the second they happen — this is how humans
  make their internal state legible enough for others to join, help, or route around.
  It is also, not coincidentally, our action-transparency problem (the field study's
  Mindcraft note: bots that can see each other's *commands* coordinate better).
- **Naming is play and infrastructure at once.** Places, duos, mobs, and items get
  names and the names accrue history; a named thing can be joked about, owed, defended,
  and remembered. (§1.13 R5.)
- **Register:** short, concrete, present-tense; game nouns do the work; interjections
  are punctuation, not content. Sentences rarely survive being longer than the action
  they describe.

### 3.2 Pattern bank (patterns, not lines to copy)

1. **Announce-intent** — say the next action before doing it, in one breath. Doubles as
   a coordination offer: anyone can object, join, or pre-position.
2. **Name-it-on-sight** — the first notable encounter with a place/mob/item earns it a
   name, proposed in chat; the name sticks if anyone repeats it.
3. **Inflate-the-incident** — treat a small shared mishap with formal procedure
   (inquest, verdict, rule). The formality is the joke *and* the institution (§1.5).
4. **Callback tax** — when a previously named thing recurs, referencing it is free and
   expected; a citizen who never calls back reads as amnesiac, because it is.
5. **Check-in cadence** — greetings on arrival, a roll-call at regroup, a one-line
   status ("two hearts, no food") instead of a paragraph.
6. **Fail-out-loud** — narrate your own failure in one line, immediately. It converts a
   private stall into shared information and usually into comedy; both are useful.
7. **Witness-me** — a finished build gets a reveal with an audience; the witness's
   reaction is part of the deliverable (§1.13 R7).

### 3.3 Exemplar moments (described; watch the mechanic, not the performer)

- **Roblox camping session [00:19–00:49]** — a self-appointed "park ranger" invents
  three rules on the spot ("have fun; don't interact with the bears; give the ranger a
  kiss") and a lobby of strangers becomes a cast in thirty seconds. Mechanic:
  mock-official framing as instant institution — the same move as Olam's chicken law,
  played for laughs first.
- **3rd Life Ep. 1 [31:53–32:15]** — the naming moment: play *stops* so a desert and a
  duo can be named. Mechanic: identity treated as urgent infrastructure (§1.13 R5).
- **AI Revolution on Olam [10:07–10:41]** — one thrown chicken → inquest → law →
  125 repetitions of the key word. Mechanic: inflate-the-incident, run by bots.
- **Hermitcraft 10 Ep. 1 [30:57–31:02]** — a zombie picks up a player's dropped
  diamonds mid-cave; the shout is panic, property claim, and comedy in four words, and
  the whole group converges on it. Mechanic: the world generates the line; the player
  just has to say it.
- **Emergent Garden, Blobology [18:16–23:08]** — a message designed to spread itself
  does. Mechanic: flair as transmission vector — and the warning label for §3.4.

### 3.4 Where the line is (guards)

Flair rides on the comms protocol; it does not amend it. **The line: a joke that
references real shared world state is signal; reciprocal content-free banter is the
politeness loop, and the loop guard's job is to break it.** Concretely: every flair
move above has a referent the digest or state feed can name (a place, an incident, an
inventory item, a death). If a line's referent can't be pointed at, it's filler, and
two fillers in a row is the Emergent Garden failure mode — politeness loops, mantra
cults, mutual hallucination (agents pretend-acting and buying each other's pretence).
The existing guards stand unchanged: busy citizens are not interrupted; a transfer
counts on confirmation, not on the line that announced it; chat claims are never
evidence — a citizen can *say* "the chicken has been avenged" only if the ledger's
chicken entry exists. Style is how the substance travels; it is never the substance.

**Mapping to our voices.** Citizens: announce-intent + fail-out-loud are the two
highest-value moves — both are coordination, not decoration, and both are checkable
against the state feed. Smiths: incident write-ups in the ledger should carry the
story in one line (the chicken rule) — provenance with a pulse. The Director: its
framing lines should name what the digest names (places, citizens, the incident of
the day) and schedule reveals (witness-me) rather than narrate continuously; the
Director's scarcity is attention, and callbacks are how it spends none to earn some.

---

## 4. The fading scaffold — training wheels as a design principle (Casey strand 1)

Casey's ruling: seed the routines, get everyone into roles and routines, then *take the
training wheels off* — oversight tapering to small nudges. A scaffold that never fades
isn't a scaffold; it's a puppeteer's string with good PR. So every seed is designed
with four fields from the start:

**(a) the routine it installs · (b) the internalisation sign** — observable, from world
evidence, that the citizen does it unprompted, in variation, or teaches it via the pond ·
**(c) the fade criterion** — when the scaffold is thinned or withdrawn · **(d) the
residual form** — the nudge that replaces it (a Director line, a digest flag, a pond
hint), never a script.

Worked seeds for our citizens:

| Seed | Routine installed | Internalisation sign (world evidence) | Fade criterion | Residual nudge |
|---|---|---|---|---|
| **Wake-and-work** (smith opening prompt keyed to the digest day cycle) | Start the day's stage work without being told | Citizen's first actions of 3 consecutive days precede any smith prompt, per state-feed timestamps | Sign met → prompt deleted, not shortened | Digest flag: "no motion by mid-morning" |
| **Store-what-you-gather** (named commons chest + deposit prompt) | Surplus and food go to the commons, not just the pockets | Unprompted deposit events (chest inventory deltas in digest) including food, across 2+ days | Sign met → chest stops being named in prompts | Pond hint card: "the chest is hungry" after a no-deposit day |
| **Greet-and-report** (comms hello template carrying position + intent) | Meetings open with state, not noise | Greetings containing position/intent appear without the template being sent | Sign met → template withdrawn | Director one-liner naming the pair's last confirmed exchange |
| **Take-the-errand** (smith assigns handover errands: fetch X to Y) | Accept and complete a peer's errand with confirmation | ≥2 errands completed with the confirmation leg closed, at least one *peer-originated* | Sign met → smith stops assigning; the chore board (§6) is the only source | Game-master posts unmet needs to the board; citizens self-serve |

**The programme's success measure is a taper.** Define, per citizen-day:
*N* = operator/smith interventions (prompts, seeded plans, assigned errands — all
ledgered already) and *P* = progress events (stage passes, confirmed errands, deposits,
survived nights). Success is *N* declining while *P* holds or rises, over rolling
windows, reported on the league page next to the scoreboard. If *N* falls and *P*
falls with it, the wheels came off too early — that is also a result, and it re-seats
the scaffold at a thinner setting rather than restoring it whole.

**Doctrine fit — and one honest tension.** Fading fits the house rule that seeded
substrate is *declared*: seeds are ledgered at install, fades are ledgered at
withdrawal; the record keeps the wheels even when the citizen no longer does. Fading
is not hiding. The tension: our exam doctrine credits citizens only for their own
work (curriculum scripts must be smith-free for stage credit). Scaffolded behaviour
must therefore be *excluded* from stage credit while the scaffold is on — the same
declaration discipline as the Pulse helm's dig-step allowance: assistance is legal,
counted, and never silent.

---

## 5. Mapping onto our machinery

For each mechanic: what carries it today, the small build, what's genuinely missing.

- **Roles.** *Have:* lineage identities; Geist's facts files; the smith pattern (System
  Two authors, citizens wear). *Small build:* a **role registry** in the commons —
  self-declared hats, audited the Sid way (role = what your action distribution in the
  digest actually says), plus an explicit *switching* affordance: hats live in facts,
  not in identity, and changing hats is a ledgered non-event. *Missing:* nothing
  structural — what Blucubed lacked was permission, not machinery.
- **Food & rationing.** *Have:* pond confirmation machinery (Inez's rule, already
  transplanted); digest inventory fields; chests. *Small build:* a **ration ledger** —
  the pond's sibling for consumables, with the served=confirmed-eaten leg wired to
  state-feed food levels. *Missing:* a food *surplus* — agriculture needs citizens who
  pass S1/S2. Institution ready, economy pending.
- **Storage & commons.** *Have:* the commons itself; S4 already exams a chest with
  contents. *Small build:* one named commons chest whose contents the digest tracks,
  so deposits/withdrawals become events. *Missing:* property norms — theft is undefined
  until ownership is declared; the charter (§6) is where that gets written.
- **Trade & currency.** *Have:* confirmed item transfer via comms + pond discipline.
  The proto-currency question, analysed: **governor mind-seconds are a budget, not a
  currency** — they are rationed, ledgered, and scarce, but non-transferable and
  non-earnable, so they price *thinking*, not goods. Making them transferable would
  create a real economy of attention overnight — and an incentive to perform thinking
  for pay. Recorded as a genuine fork, not a recommendation. *Small build:* barter
  offers as comms messages with pond-style confirmation. *Missing:* price discovery —
  meaningless before surplus.
- **Governance & laws.** *Have:* scoreboard + incident records; the Director/game-master
  as ratifier; the field study's constitution-as-document steal. *Small build:* a
  **commons charter file** + the incident→law pipeline (a law is a charter amendment
  carrying its incident's ledger link; ratification = game-master countersign in the
  charter's own history). *Missing:* citizen vote machinery — deliberately; at n ≤ 6,
  sentiment is readable from comms, and Sid's lesson is that the *document* does the
  work, not the ballot mechanics.
- **Leadership.** *Have:* the warning, and a small scar (roster-order capture in comms
  v1's first exchange). *Small build:* rotate the coordinator *chore* (who posts the
  day plan, who holds the ration ledger) on a schedule, each tenure receipted.
  *Missing:* nothing — the design goal at our scale is that leadership never condenses
  into a person.
- **Religion & memes.** *Have:* comms + pond as transmission media with provenance —
  spread is already *measurable* in chat.jsonl and pond citations. *Small build:* a
  digest meme-watch (a term's spread across citizens, Sid's metric) **with our
  upgrade:** a meme graduates to "belief" in the record only with a behavioural
  correlate (a build, a deposit pattern, a route changed). *Missing:* nothing to
  build; this emerges or it doesn't. Our job is instrumentation that doesn't lie.
- **Collective building.** *Have:* solo S3. *Small build:* a **commons blueprint
  format** — one file per project: anchor coordinates, dimensions, parts list, who's
  on which part (the Emergent Garden fix: coordinates or don't bother; Ada's shared
  folder is the shape). *Missing:* citizens who can build at all — S3 first.
- **Conflict & defence.** *Have:* mobs, deaths, a ledger that counts them. *Missing:*
  inter-citizen norms (PvP, property) — deferred until property exists; writing law
  for a crime with no objects is how you get a chicken law without a chicken.
- **Social graph & reputation.** *Have:* chat.jsonl *is* the graph, already recorded;
  digest carries positions/state. *Small build:* **reputation as a derived view** —
  confirmed transfers, completed errands, deposits — computed from ledgers, never
  from self-report; optionally, per-citizen notes in facts (Geist modelling Vega's
  habits the way Sid's agents profiled each other). *Missing:* citizen-side
  other-modelling as a running module — Geist's planner is closest.
- **Collective memory.** *Have:* ledgers, pond, facts. *Small build:* close the
  retrieval loop — the digest pushes *yesterday's incident* into each planner's
  context at decision time (the memory-paradox fix: memory that arrives at the moment
  of choice, not memory that waits to be consulted). *Missing:* nothing else; the
  organs exist, the librarian (§2) is the gap.
- **Scaling.** *Have:* measured Orin headroom (~1.5–2 GiB for a resident slow mind
  after world + client), tuned view/simulation distances, governor economics.
  *Ordering for our walls:* mind budget on the shared brain first (§2.1), Orin server
  tick second, comms pairs a distant third at n ≤ 6. *Missing:* nothing at this
  scale — and a standing instruction not to import Sid's problems before we have
  Sid's numbers.

---

## 6. Minimum viable civilization

**The dependency, stated first:** a civ needs citizens who can feed and shelter
themselves. Tonight the scoreboard reads zero stage passes across three lineages.
Everything below is sequenced *after* the first S1 passes land — the institutions are
designed now so they can be stood up the week the citizens can support them, and the
seeded routines of §4 can begin alongside S1 work because they *are* S1-shaped
(wake-and-work, store-what-you-gather).

**The smallest thing that is still a civilisation** (not three bots sharing a chest):
at least **four citizens** (three is a group; four gives a *public* — someone can
witness an exchange they are not part of, which is what makes reputation and law
social facts), **one named shared place**, **one institution with receipts**, **one
rotating chore**, and **one shared text**. Sequence:

1. **Seeded routines** (§4): wake-and-work, store-what-you-gather, greet-and-report —
   declared scaffolds, installed with the exam work.
2. **Institution 1 — the commons chest + ration ledger.** Food first, because at
   subsistence it is the only currency that matters. *Dock measure:* chest inventory
   deltas + confirmed-eaten receipts in the ledger, against deaths-by-starvation and
   food-level trend in the digest. Success looks like: deposits happen on days nobody
   is starving — surplus behaviour, not panic behaviour.
3. **Institution 2 — the errand board (role emergence, measured).** A commons board
   of posted needs ("need 6 planks at the dock"), claimable by any citizen, closed
   only on confirmed completion — the take-the-errand scaffold graduating into a
   market. Roles are *read off the claim record*: a citizen's role is their modal
   claim category over a week, per Sid's action-distribution method. *Dock measure:*
   errands completed with the confirmation leg closed; role distribution entropy
   across citizens (specialisation exists when the distribution is neither uniform
   nor a monopoly).
4. **Institution 3 — the charter + incident law.** A charter file in the commons;
   the first law must come from a real incident (a stripped build, a taken chicken —
   our world will provide), posted with its ledger link and ratified per §5.
   *Dock measure:* the law exists as an artefact, **and** the behaviour it names
   measurably changes in the digest afterwards (deposits, movements, claims) — the
   Sid tax test, run at our scale: if the document doesn't move behaviour, it's
   literature.
5. **Role emergence → scaffold fade → nudge-only oversight.** As §4's signs are met,
   scaffolds withdraw in order; the smiths' job becomes the taper report. Oversight
   at steady state is: the Director's framing lines, digest flags, pond hints — and
   the ledgers, still recording everything, because the dock is permanent even when
   the training wheels are gone.

Lineages D (Villager) and E (Archivist) slot in here rather than at the exam: a
fourth citizen is an MVC prerequisite, and the Archivist — a citizen whose work is
the exoskeleton itself (keeping the charter, the ledger summaries, the pond's
provenance tidy) — is the first role in our design that is *born* institutional.

---

## 7. Risks & anti-patterns (from the sources)

- **Politeness loops & mantra cults** (Emergent Garden): reciprocal content-free talk
  that consumes the day; the comms loop guard exists for this — and §3.4 draws the
  line it enforces.
- **Mutual hallucination / pantomime economy**: agents pretend-acting ("on my way,"
  no command issued) and partners buying the pretence (Emergent Garden [14:58]). Our
  strain of the same disease would be a *pantomime trade*: confirmed in chat, absent
  in the state feed. The confirmation leg is the vaccine; never let a transfer count
  on words.
- **Measurement pantomime**: Sid's conversion-by-keyword is the respectable version —
  a proxy that flatters the phenomenon. Any civ metric we adopt gets the behavioural-
  correlate requirement (§5, memes) or it goes in the record as talk-metrics only.
- **Strip-mining unmonitored stocks**: the survival valley emptied of animals [77:36];
  in our terms (the chain-philosophy seat's objection): citizens passing flow checks
  while drawing down stocks no dock prices — commons wood, goodwill, the pond's
  trust. Mitigation is digest-level stock accounting (§5 storage build) *before* the
  flows look good.
- **Roster-order capture & the leader bottleneck** (Ada): centrality by accident,
  then lock-in. Rotation is cheaper than rescue (§5).
- **Rigid-role idling** (Blucubed): jobs as cages. Hats, not identities (§5).
- **The risk-aversion death spiral** (Olam): a frightened colony starves cautiously.
  Safety memos are interventions with side effects; the game-master should price them.
- **Coordination overhead exceeding solo cost**: Bram's 11 messages for one string;
  Claude idling while GPT fetches (Emergent Garden [35:43]). Errands need a cost
  sanity check — the board (§6) should show an errand's age, and stale errands are
  data, not embarrassments.
- **Write-only memory** (Cleo's "died again"): institutions that aren't retrieved at
  decision time don't exist. The digest-push build (§5) is the fix; until it lands,
  treat every new ledger as suspect.
- **Scale breaking servers before minds** (Sid >1,000): instrument infrastructure
  first; infrastructure failure impersonates agent failure.

---

## 8. Where the sources push against our current design

Flagged loudly, per the brief — these are tensions with evidence behind them, not
refutations; each names what we'd watch.

1. **Our comms rationing vs culture's density requirement.** Comms v1 caps exchanges
   (3/pair/hour) and guards loops — correctly, for cost and sanity. But every civ
   source says institutions are a *by-product of surplus talk*: Sid's towns out-meme
   rural areas per capita; Olam's 5,900 messages carried the ledger, the law, and the
   leadership accident alike. If we ration talk to zero waste, we may ration away the
   civ. Watch: whether any institution forms at current caps before concluding the
   citizens can't form one.
2. **The exam is individual; capability in the sources is collective.** S1–S5 grade
   solo competence. The colony's unit of survival was the ledger, not the agent — and
   tonight, pooled, our citizens are closer than solo: one has logs, one has a
   working mind-link, one has position and facts. The exam's framing can hide a pooled
   path to a functioning town. Keep the exam (it makes citizens comparable); add the
   civ dock (§6) so pooling is also measured, not just permitted.
3. **Mind budgets buy control; the sources bought institutions with unbudgeted talk.**
   The governor exists because one shared brain is scarce and contention is measured
   (§2.1). But Olam and Sid ran effectively unmetered conversation and the
   institutions formed *in* the talk. The honest synthesis: budget the *deliberation*
   (System Two is expensive) and be more generous with *coordination talk* (short,
   state-carrying messages are cheap and are where civs live). A two-tier comms
   budget is a design option this study puts on the table.
4. **Watchability: rituals, not just shots.** The Director's grammar assumes the film
   makes the civ watchable. The human sources say the audience bonds to *session
   rituals and names* — a Friday session, a named desert, a game within the game.
   The Director should also *schedule*: a weekly games day, a naming rite for new
   builds, a tour at session end (R7). Framing follows ritual; ritual is content.

---

## 9. Watchlist for Casey (≤4)

1. **fig — "50 AIs build a colony" [04:52–05:39]** — Inez's ration ledger: an
   institution being born, in a text file, with the rule that became our pond's
   confirmation leg. The single densest five minutes in the corpus.
2. **Species — "Documenting AGI" [09:24–10:07]** — the tax amendment: 20% becomes 9%
   and behaviour follows the paper. (Fragmented captions; read alongside the paper's
   §5.2, which has the controls.)
3. **Blucubed — "100 AIs Simulate Civilisation" [05:10] and [15:06–15:15]** — Zorgon
   arrives uninvited; then the host's verdict that jobs failed by rigidity, not by
   concept. The two ends of the roles question in ten minutes.
4. **Grian — 3rd Life Ep. 1 [31:47–32:15]** — end-of-session securing, and a duo
   stopping play to demand names for a desert and for themselves. Civilisation's
   smallest act, done by humans at walking pace.

---

## Appendix — sources & tiers

| # | Source | What was mined | Tier |
|---|---|---|---|
| 1 | Altera.AL et al., *Project Sid*, arXiv:2411.00114 (paper) | PIANO modules; §5.1 specialisation; §5.2 tax constitution + controls; §5.3 memes/religion; >1,000-agent server limit | Written primary |
| 2 | Blucubed, "100 AIs Simulate Civilisation" (-YOZenIxalQ) | Seeded roles, rigid job law, Zorgon, Lunatics, host verdict — captions re-extracted this pass | 1 |
| 3 | fig, "50 AIs build a colony" (PTw8Met9xTc) | Ada/roster leadership, Inez's ledger, Jessa's method, death spiral, Bed Wars — captions re-extracted this pass | 1 |
| 4 | Emergent Garden, "AI talks to AI" (uLRKXEHxZ-U) | Trade-in-conversation, password diffusion, Blobology, mutual hallucination — captions re-extracted this pass | 1 |
| 5 | Species, "Documenting AGI" (uRDBco-cSK4) | Sid narrative: treasury guard [11:20], tax story [09:24], convert-by-converts [07:32] — captions attained this pass (fragmented) | 1 |
| 6 | Emergent Garden, "4 AIs Survive 10 Days" (KxaPYhfJV4U) | Strip-mining, starvation oscillation, cost ledger — carried from field study's full read | 1 |
| 7 | Fundamental Research Labs, "Project Sid" short (2tbaCn0Kl90) | Gems-as-currency, priest-trader, Olivia, beacon — carried from field study | 1 |
| 8 | AI Revolution, "AI civilisation goes to war" (l1L9sezAcxc) | Chicken law, memory paradox — carried from field study | 1 |
| 9 | Grian, 3rd Life Ep. 1 (nszciRXXJZk) | Session frame, spoken constitution, securing ritual, naming — captions extracted this pass | 1 |
| 10 | Grian, Hermitcraft 10 Ep. 1 (gzKb-JxjyWQ) | Demise game-within-game, group caving callouts, tours — captions extracted this pass | 1 |
| 11 | Flamingo circle, "Roblox camping…" (I4B9KJjUzrg) | Mock-official framing, improv institutions, register — captions extracted this pass | 1 |
| — | "1 Hour Of Flamingo And Friends" (D7avN8mdf-U), best-of compilation | **Unattained** — caption endpoint refused (429 → bot-check). Not escalated to Tier 2; see Method | — |

*Evidence files (caption extractions) are kept with this study under
`~/workspace/rolling-perception-work/civ-deep-dive/evidence/`. No video was downloaded.
Staging only — publication is the parent lane's call.*
