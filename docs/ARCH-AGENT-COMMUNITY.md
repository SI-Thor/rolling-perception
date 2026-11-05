# Architecture: The Agent Community — Rolling Perception over a Society of Agents

*Top-level design document for the agent-community programme. Written 2026-11-05,
the day the first agent crossed from the Thor into a world hosted on the Orin.
This document records the big pieces at the level they were decided, before
the dives. Component documents (CRAFTMIND-MAP, the stream-platform spec, the
trust-loop papers, the Dory studies) go deeper on their own subjects; this one
is the map of how they compose. Where a claim is measured, it says so and
points at the record. Where a piece is designed but not built, it says that
too. The point of writing it now, at the top, is Casey's: during a dive you
can be on the wrong trajectory while the pieces up here were right — so the
pieces up here get written down while they're clear.*

## 0. The thesis in one paragraph

A community of agents lives in a shared world. The expensive mistake is
giving every agent its own senses: twenty agents each perceiving the world
twenty different ways is twenty times the cost and no shared truth. Instead,
**one machine keeps one rolling perception of the world — a single,
continuously updated percept of the moment — and every citizen drinks from it
at the temporal resolution their role has earned.** Heroes tap it many times
a minute and act on fresh state. Workers and peons are heavily scripted, run
competent loops, and are still *in the rotation*: their perception slot comes
around at a longer period, the system takes in their local state, checks the
shared percept for novelty near them, and only then spends real perception on
them. Above the players sit System-Two minds whose job is not to play but to
judge the rotation itself — whether the current repertoire of scripts is
good — and to upgrade it: fixing scripts, writing new ones, issuing new ideas
to their troops, under governance, with receipts, reversibly. The whole
society runs on metered budgets whose unit generalises as the stack rises:
embed-seconds for raw perception, mind-seconds for thought, and
perception-seconds for how much of the shared moment each citizen may drink.

## 1. Topology — where things physically live

Decided 2026-11-05 from Casey's own February history and the fleet's shape:

- **The world lives on the Orin** (Jetson Orin Nano Super, the front-room
  box, LAN 192.168.0.50). A Minecraft Java server — Paper — is the first
  world. The Orin serves the world and nothing else heavy; the world is the
  stage, not the mind.
- **Humans join as players from laptops** (Java edition clients on Casey's
  two laptops). Humans are citizens with the highest temporal resolution of
  all: continuous perception, no budget.
- **The agent community lives on the Thor** (Jetson AGX Thor, the back-room
  box, LAN 192.168.0.78). The cascade, the local models, the governor, the
  ledgers, the smiths — everything that thinks — runs on the Thor and joins
  the Orin's world as ordinary clients over the LAN.
- **History that motivates this:** the family's Minecraft games with Magnus's
  Craftmind projects ran on the Orin in February 2026; that install was wiped
  by the Orin's October 2026 rebuild, and the Thor only arrived in October
  2026. The topology above is a fresh build, not a restoration.

Measured state on day one (2026-11-05, all verified from both ends): Paper
26.1.2 (protocol 775 — pinned, see §7) running as a boot-persistent service
on the Orin; a Craftmind bot ("Cody") joined from the Thor, stood in the
world, spoke in chat, and left cleanly, confirmed independently in the Orin
server log; the mind governor live on the Thor with its first receipts
written.

## 2. Bodies — what an agent physically is in the world

Two body families exist today, and the architecture treats them as
interchangeable citizens behind the same perception and budget contracts:

- **Craftmind bots** (Magnus's Lucineer framework): external protocol clients
  (Mineflayer). Moment-to-moment behaviour is a prioritised rule system and a
  validating state machine — *no LLM calls in the reflex path* (verified in
  CRAFTMIND-MAP). The framework already contains the cascade's sockets: an
  attention budget with a novelty detector (a diff-gated attention scheduler
  in embryo), a chat seat, and a script-writer whose proposed behaviour edits
  are quality-scored and A/B tested before adoption.
- **Steve** (YuvDwi/Steve, "Cursor for Minecraft"): an in-world Forge entity
  with natural-language command → whole-plan LLM call → tick-based action
  execution. The opposite body: the brain call is per-command, unbounded, and
  cloud-shaped — which makes it the cleanest demonstration of why the budget
  layer exists. Its interceptor chain already publishes action metrics (a
  ready-made ledger tap), and its memory persists inside the world save.

The architecture does not pick a winner. Bodies are replaceable; the
contracts in §3–§5 are the durable part.

## 3. Layer 1 — Rolling perception: one percept of the moment

The core invention, carried over from the Confluence stream platform with
streams replaced by a world:

- A service on the Thor maintains **the digest**: the continuously updated
  state of the world and the community — positions, movements, events,
  completions, utterances, scores — as choreography, not raw sensation.
  (The Presence stack proved this shape at household scale: the ledger stores
  where/when/who/how-strong, never pixels or embeddings.)
- The digest is a **subscription service with tiers**, not a broadcast.
  Each citizen class subscribes at a cadence and a granularity (§4). A hero
  reads the fine digest around itself many times a minute. A peon's slot in
  the rotation is a coarse, infrequent read — plus a novelty check: has
  anything in the digest changed *near this peon* since its last slot? If
  not, the slot costs almost nothing and the peon keeps scripting. This is
  the telltape diff-gate promoted from frames to citizens: perception is
  spent where the world actually changed.
- **Silence semantics are inherited from telltape and are load-bearing:** a
  quiet digest region means "nothing happened" only if the pipeline has
  demonstrated discrimination on the current inputs. Frozen feeds, dead
  bots, and broken sensors must receipt as FROZEN/UNKNOWN, never as calm.
  The society's trust in its own calm depends on this.
- Sources: server state (the world is server-truth — positions and events
  are authoritative there), bot self-reports at their slots, and the action
  ledgers. Where a body offers an action-metrics interceptor (Steve), that
  is the preferred tap.

Status: **designed, not yet built.** The digest is the next build after the
league's first governed round. Its inputs exist (server, bots, ledgers); its
subscription contract is this section.

## 4. Layer 2 — Temporal resolution: the rotation

The rotation is the schedule of who perceives, how often, and how finely.
It is where the cascade's cadence tiers and the tenancy ladder become social:

- **Classes, by role.** Heroes/main characters: high cadence, fine
  granularity, real decision-making against fresh state. Skilled workers
  (builders, throwers): medium cadence, task-shaped slices. Peons:
  heavily scripted, low cadence — but *in* the rotation, never outside it.
  A citizen outside the rotation is a citizen the system cannot notice
  failing.
- **Perception-seconds** are the budget unit at this layer: the integral of
  granularity × cadence a citizen consumes from the shared percept. The
  governor (§5) already meters mind-seconds; the rotation extends the same
  accounting to perception. A peon's cheapness is a *measured* cheapness,
  receipted like everything else.
- **Yield is social.** The tenancy ladder built for the camera cascade (a
  foreign load or an interactive session pushes reflective work down rungs)
  applies unchanged in shape: under contention — a human playing, a heavy
  build, the box busy — the rotation stretches peon periods first, then
  worker cadences, and heroes last. Who yields, in what order, is a policy
  of the society, stated in advance, not improvised under load.
- **Escalation.** A slot that finds novelty beyond the citizen's script —
  damage, an unexpected player, a task that won't complete — escalates:
  finer digest, a mind call, or a word to a smith. Escalations are events in
  the ledger; their rate per citizen is a health signal for the scripts
  themselves (§6).

## 5. Layer 3 — Minds: local first, metered, rotating

- The community's routine thought runs on **local models on the Thor**,
  rotating with load and role (the presence brain — Qwen3-Coder-30B — is the
  first seated mind; Dory, the looped model, is the designated refiner class:
  a model whose *depth* is a dial, seated over text digests with loop-count
  receipted per verdict, per DORY-SMOKE-1's findings).
- All mind access passes through **the governor**: a proxy that meters
  calls and mind-seconds per agent against a rolling-hour budget, receipts
  every call, and refuses over-budget agents with a shaped refusal the
  bodies are designed to degrade gracefully from (Craftmind falls back to
  canned behaviour by design). Built and live 2026-11-05; first receipts
  written the same day.
- **Above the local tier**, the subscription seats and APIs (Claude,
  MiniMax, ZCode, Kimi; Typesafe/Jev strictly as an advisor *sense*, never a
  gate) are the expensive minds, bought with the same budgeting discipline:
  a call upward is a decision the ledger can explain.
- Model rotation is a policy surface, not an accident: which mind serves
  which class at which hour is recorded, so the society's cognitive history
  is auditable — a verdict can always be traced to the mind that made it.

## 6. Layer 4 — System Two: the smiths and the improvement loop

The top layer does not play. It maintains the repertoire.

- **The charter:** judge whether the current rotation — the set of scripts,
  classes, cadences, and budgets — is good, and upgrade it. Concretely:
  fix failing scripts, write new scripts, propose new citizen classes and
  new tasks ("new ideas for their troops or their workers or their
  builders"), retune cadences and budgets.
- **The mechanism already exists in prototype:** Craftmind's script-writer
  proposes behaviour edits; a scorer quality-scores them; A/B trials run
  them against incumbents; adoption is a decision, not a merge. The
  architecture generalises that loop and puts it under the fleet's standing
  governance: a proposed script is an *effect* — proposed, verified in
  trial, adopted or denied on evidence, and reversible (the Jacquard
  lifecycle, proven on weight patches in the weight-space programme and
  identical in shape here).
- **The trust loop scores the smiths.** Every citizen and every smith
  accumulates judged outcomes: per-agent trailing precision over tapped
  verdicts (the trust-loop build, shipped 2026-11-05, computes exactly
  this for streams; citizens are streams of behaviour). A smith whose
  scripts keep losing trials is demoted — its proposal budget shrinks on a
  trailing window with hysteresis; a smith that keeps landing improvements
  earns a larger one. Demotion routes on evidence, era-fenced, never on a
  single bad day.
- **The flywheel, and its guardrail.** The course-builder in the disc golf
  league (§8) is the first smith workload: it reads the ledger's measured
  weaknesses and mutates the course against them, pre-flighted in the
  simulator, rollback on regression — the CUA-Master recursive-improvement
  shape at society scale. The guardrail comes from the same study: a
  flywheel steered by its own synthetic experience drifts; ours is steered
  by *real play* — human players included — and its judges are referees and
  cold playtests, never the smiths themselves.
- **Escalation terminus.** What the smiths cannot settle — a class that
  keeps failing, a budget that keeps exhausting, a trajectory that feels
  wrong — surfaces to Casey as a decision, batched, with the ledger
  evidence attached. Casey is the society's constitutional court, not its
  middle manager.

## 7. Decisions recorded (so the dives don't re-litigate them)

- **Paper XOR Forge.** One world cannot be both. Craftmind citizens require
  a protocol world (Paper); Steve requires a Forge world (server *and*
  clients). Decision: the first world is **Paper + Craftmind**; a Forge/Steve
  world is a deliberate *second* world, later, if the pattern earns it.
- **Protocol pin.** The Orin server is pinned to **Paper 26.1.2 (protocol
  775)** because the bot client data (minecraft-data) cannot yet join 26.3.
  The 26.3 jar and its generated world are kept aside, not deleted. Revisit
  when client data catches up.
- **Offline mode on the LAN.** Bot clients join without Mojang auth;
  anyone on the home network could join under any name. Accepted for a home
  LAN, stated out loud, revisited if the world is ever exposed beyond it
  (it must not be port-forwarded in this mode).
- **Magnus's repos are read-only inspiration.** The league's working copies
  live on the Thor and will become our own repositories; the Lucineer
  originals are never modified.
- **Deterministic physics cannot train a thrower.** The disc golf engine's
  flight model is honest, but its thrower has no execution noise, so skill
  could only grow in disc *selection*. The execution-noise model (noise that
  shrinks with practice) is a named, required addition — it is the
  difference between a league that learns and a league that converges.

## 8. The first society: the disc golf league

The league is the type specimen — chosen because disc flight is honest
physics with a vocabulary (speed/glide/turn/fade, hyzer/anhyzer, wind), disc
choice is a small legible decision with a measurable outcome, and a course
is a thing builders can improve. Season one's shape:

- Four to six citizen throwers with distinct personalities and disc bags;
  one builder-smith; nine holes.
- Every throw is recorded in the league ledger **as a decision** (disc,
  power, hyzer, wind, outcome) — the ledger is the society's memory and the
  smiths' evidence.
- Weekly, the builder mutates the course against the ledger's measured
  weaknesses; mutations are pre-flighted in the simulator and reversible.
- A league page makes it watchable: standings, bags evolving, the course
  changing, mind-call and perception budgets visible. Watchability is a
  requirement, not a garnish — the wow is the audit made visible.

Later worlds inherit the stack rather than reinventing it: the filmmaking
studio (craftmind-studio), the classroom (craftmind-courses), Sitka ecology,
agents playing music together. Each is a new world with the same digest,
rotation, governor, and smiths.

## 9. What exists, what is designed, what is open (2026-11-05)

**Exists and verified:** the Paper world on the Orin; the Craftmind bodies
running from the Thor; the mind governor with live budgets and receipts; the
league ledger wired into the disc golf throw path (decision lines recording);
the trust loop computing judged-precision demotions; telltape's silence
semantics as the perception honesty standard; Dory measured as a refiner
candidate (decode rates per loop count, reasoning delivery failure modes —
see DORY-SMOKE-1).

**Designed, not built:** the world digest service and its tiered
subscriptions (§3); the rotation scheduler with perception-second accounting
(§4); the execution-noise skill model (§7); the smith trial/adoption pipeline
generalised beyond Craftmind's built-in script-writer (§6); the league page.

**Open questions, deliberately left open at the top:** how fine the digest's
spatial grain should be before it becomes surveillance of citizens rather
than perception of a world; whether a peon's local perception should ever
bypass the digest (a reflex arc) and what that does to the shared-truth
claim; the right trial length for a script A/B (too short is noise, too long
is a season); how smiths earn budget across *kinds* of proposals, not just
volume; whether music — the society playing together in time — is a
perception problem (shared beat as a digest field) or its own layer.

## 10. Lineage

Rolling perception began as a stream platform for cameras (Confluence) with
citizens' evidence rules (telltape), a presence that answers questions about
a house, and a trust loop that demotes streams that cry wolf. The community
architecture is the same cascade with the streams replaced by citizens — and
Casey's framing is the one this document is written under: the Thor dreams
the world once, continuously, and everyone — hero, peon, smith — drinks from
that single dream at the rate their role has earned.
