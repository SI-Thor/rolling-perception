# CRAFTMIND-MAP — Magnus's Craftmind worlds, Steve, and where our cascade attaches

Read-only mapping, 2026-11-05. Sources read in full or in load-bearing
part from local copies under `~/workspace/craftmind-read/` (fetched
from the public repos; nothing pushed, modified, or filed upstream).
Repos: `Lucineer/craftmind`, `craftmind-discgolf`,
`craftmind-researcher`, `craftmind-ranch`, `craftmind-studio`,
`craftmind-courses`, and `YuvDwi/Steve`. Every claim below names its
file. Statements marked **[speculation]** are ours, not the code's.

A note on provenance before anything else, because it changes how
the code should be read: the Craftmind repos are large, fluent, and
uneven. The core loops quoted here were read line by line; the
peripheral systems (economy, quests, federation, tournaments in
`craftmind/src/…`) were inventoried from the tree, not audited.
Several headline claims in the READMEs ("no hardcoded scripts, every
action decided live by an LLM") are **not** what the code does — the
code is more interesting than the README: it is mostly scripted,
with the LLM in a much narrower seat. That narrower seat is exactly
why the cascade map in §5 works.

---

## 1. craftmind — the framework's real architecture

`Lucineer/craftmind` (JavaScript, `package.json`): a Mineflayer bot
framework. Dependencies are the tell: `mineflayer ^4.35.0`,
`mineflayer-pathfinder ^2.4.5`, `rcon-client`, `dotenv`. A bot is an
**external protocol client** — a real (fake) player that joins a
server over the wire, exactly like a human client. It is not a mod
and needs nothing installed on the server.

### 1.1 Body: bot.js + state machine + pathfinder

- `src/bot.js` (~880 lines) is the body factory. It creates the
  Mineflayer bot, loads `mineflayer-pathfinder`, builds Movements,
  and exposes scripted verbs as bot methods: `followPlayer`,
  `goTo` (`goals.GoalBlock`), `mineBlock`, `placeBlock`, look-at,
  chat. Movement decisions are the pathfinder's, not a model's.
- `src/state-machine.js`: a validating finite state machine.
  Built-in states `IDLE, FOLLOWING, NAVIGATING, MINING, BUILDING,
  FISHING` (+ `DEAD`); transitions are table-checked (an invalid
  transition is refused with a warning, except to `IDLE`/`DEAD`),
  counted, emitted as events, and timeout-guarded (a state that
  overruns is forced back to `IDLE`). Plugins register their own
  states and transitions (`registerState(s)`), e.g. the fishing
  plugin's `CASTING, REELING, FIGHTING, LANDING`.
- Plugins: `src/plugins/index.js` (`PluginManager`) plus auto-loading
  of every file in `src/plugins/` by `src/bot.js`. A plugin is
  `{name, load(ctx)|init(ctx), unload|destroy}`; `ctx` gives it
  commands, events, the action registry, knowledge, messenger,
  inventory hooks, crew roles — and **prompt fragments**
  (`registerPromptFragment(key, text, priority)`), which are the
  plugin system's one channel into the LLM's system prompt.
  Built-ins include `auto-eat`, `auto-equip`, `auto-respawn`,
  `combat`, `flee-on-danger`, `wanderer`, `player-tracker`,
  `death-tracker`, `fishing-bridge`, `game-hub`, and notably
  `src/plugins/rate-limiter.js` — a chat anti-spam limiter
  (sliding window, default 7 messages / 30 s, burst 3 / 3 s), i.e.
  a rate control, but for *server-kick avoidance*, not for cost.
- `src/orchestrator.js`: a multi-bot registry/conductor — registers
  named agents, fuzzy-matches names, connects bots with a 2-second
  stagger. Coordination above the single-bot level is thin here;
  the richer coordination lives in `src/npc/coordination.js` and
  the satellite repos' own runtimes (not audited line by line).

### 1.2 The second, domain-general agent layer

`src/agent-framework/` is a separate, mostly LLM-free agent runtime
that the satellites reuse (fishing NPCs, film actors, students,
research assistants — its own header says so):

- `agent.js` (`Agent`): personality traits, a mood vector
  (`energy, satisfaction, frustration, social`) updated by typed
  events, episodic memory (capped at 100), a **relationships store**
  (`trust` starting 0.3, +0.02 per positive interaction, −0.03 per
  negative, with interaction counts and last-seen), a time-block
  schedule, and a `tick(context)` that returns schedule actions or,
  stochastically (`talkativeness × 0.15`, 15 s per-target cooldown),
  social actions (`greeting` < `chat` < `share` by trust band).
- `decision-engine.js` (`DecisionEngine`): **pure scoring, no LLM.**
  It ranks previously recorded behavior *scripts* for current
  conditions from `SessionRecorder` history + `ComparativeEvaluator`
  insights: base 0.3, +success-rate×0.3, +evaluator-mean×0.2,
  +similar-session-rate×0.2, +target-rate×0.15, recency bonus,
  then personality modifiers (stubbornness rewards well-worn
  scripts, frustration penalises recently failed ones, curiosity
  rewards rarely tried ones). Below 0.3 confidence it explores or
  waits; low mood-energy forces `rest`. This is a learned-by-counting
  policy over scripts — the closest thing in the fleet to a
  home-grown decision tier, and it costs zero model calls.
- `action-planner.js` / `action-executor.js` / `action-schema.js`:
  plan/execute plumbing around those script choices.
- `behavior-script.js` (in `src/`, shared): the **reflex language**.
  A behavior script is a prioritised rule array —
  `{id, condition, action, priority}` — whose conditions are a small
  DSL (comparisons, `AND/OR/NOT`, `@time`, `@near`, `@within`),
  parsed by a hand-written tokenizer/recursive-descent parser and
  evaluated by *pure string/state matching, no LLM calls* (the
  file's own words), firing the highest-priority matching action
  each tick. This file is the single most important one in the repo
  for §5: it is a finished, working reflex tier.

### 1.3 THE BRAIN — how the "LLM brain" is actually invoked

`src/brain.js` exports `LLMClient`, `PERSONALITIES`, `BrainHandler`,
`HealthMonitor`. Read carefully, the LLM has **three** seats, and
only three:

1. **Chat (`BrainHandler.handleChat`)** — the main seat. Wired in
   `src/bot.js` to Mineflayer's chat event for any non-command
   message not from the bot itself. The reply is *chat text*, not
   an action: it is trimmed, truncated to 100 characters, and sent
   with `bot.chat()`. Context per call (`_buildContext`): one
   compact line — position, block underfoot, health, food,
   day/night, up to 5 entity names within 20 blocks, and who it's
   talking to — substituted into the personality's `{context}`
   placeholder, plus the client's rolling history.
2. **Autonomous thought (`BrainHandler.autonomousThought`)** — a
   ≤5-word "what should I do next?" idea, logged to console.
   It fires on only ~10 % of calls (`Math.random() > 0.1` returns),
   and — critically — its return value is **not connected to the
   action machinery** in the code as read: it produces a string for
   the log. The bot's actions continue to come from commands,
   scripts, plugins, and the state machine.
3. **Script authorship (`src/script-writer.js`, `ScriptWriter`)** —
   the consequential seat. Given a current behavior script, a
   problem context, novelty events, and performance data, it calls
   the LLM once (`fetch`, `temperature 0.3`, `max_tokens 1000`) for
   JSON `{reasoning, added, removed, modified}` rule edits; edits
   are validated by `behavior-script.js`'s `validateScript`,
   quality-scored by a local heuristic (0–100), and can be A/B
   tested (`startABTest`, default 5 min, mean-score winner). The
   LLM here is not a pilot; it is an occasional *editor of the
   reflex tier's code*.

What the LLM **decides**: conversational replies; (log-only)
intentions; proposed edits to behavior scripts.
What **scripts decide**: everything the body does moment to moment —
pathfinding goals, state transitions, plugin reflexes (eat, flee,
equip, respawn), behavior-script rule firing, and, in the
agent-framework layer, which script to run (`DecisionEngine`).

**Provider & context shape.** `LLMClient` defaults: Z.AI coding
endpoint (`https://api.z.ai/api/coding/paas/v4/chat/completions`),
model `glm-4.7-flash` (`src/bot.js` CLI default `glm-4-flash`),
`max_tokens: 200` for chat calls, full-endpoint URL and key from
config/env (`ZAI_API_KEY`). History is a plain rolling window,
sliced to `maxHistory`. Prompt assembly = personality system prompt
+ priority-sorted plugin fragments. A `HealthMonitor` probes the
API (30 s default), and on failure the brain **degrades to canned
pattern replies** (`_fallbackChat`: greetings, "Idk, my brain is a
bit foggy right now", silence otherwise) — graceful, and honest
about being degraded in its status object.

**Cost/rate controls that exist** (this is the part the cascade
map builds on):

- `BrainHandler.minThinkInterval` — default **2,000 ms** minimum
  between LLM calls; a second guard drops calls while one is in
  flight (`thinking` flag; the bot literally chats `...`).
- `LLMClient` retry with backoff; health-probe traffic excluded
  from history.
- `src/attention-budget.js` (`AttentionBudget`) — a real,
  general **LLM-call budgeter**: registered attention entries with
  priorities (`critical > important > normal > low`), per-entry
  minimum intervals, a heartbeat (default 30 s), a global
  `maxCallsPerMinute` (default **4**), focus mode (focused entry's
  interval floors at 5 s; others' intervals ×3), suppression, and a
  500-entry call history with trigger labels. `interrupt()` lets
  critical/important events pre-empt — and it is wired to
  `src/novelty-detector.js` (`NoveltyDetector`: running mean/σ per
  key, severity at 2σ/3σ/4σ, needs ≥5 samples). In other words:
  **a diff-gated attention scheduler for model calls already
  exists in this repo**, as a library. What it does not have is a
  *cost* unit (it counts calls, not tokens/seconds/money), a
  per-agent or per-stream split, persistence, or any connection
  to the chat brain's 2 s interval (the two limiters coexist
  un-unified — as read, `AttentionBudget` serves the
  attention/novelty subsystems, `BrainHandler` self-limits).

**Cost controls that do not exist:** no token accounting anywhere;
no per-bot budget; no model tiering (one model for chat, thoughts,
and script edits — the same `glm-4.7-flash` class throughout);
no spend ledger; `ScriptWriter` counts its own requests
(`_requestCount`) but nothing reads the counter as a budget.

---

## 2. craftmind-discgolf — in depth

`Lucineer/craftmind-discgolf` (branch `master`; tiny — 24 files).
Two parallel implementations live side by side, and keeping them
apart is essential:

- **The Worker/simulator line**: `src/engine/disc-physics.js`,
  `src/engine/disc-database.js`, `src/scripts/…` — a standalone,
  deterministic-ish flight simulator (the deployed Cloudflare
  Worker per the README).
- **The in-Minecraft line**: `src/disc-physics.js` (snowball-entity
  flight inside a live world via a Mineflayer bot), `src/course-builder.js`
  (builds courses as blocks), `src/scorecard.js`.

### 2.1 The catalogue

`src/engine/disc-database.js`: **73 disc entries** (counted), each a
flat record `{id, name, manufacturer, type, speed, glide, turn,
fade}` — real models from Innova/Discraft/Dynamic Discs/Prodigy/
Discmania with their published flight numbers (Speed 1–14, Glide
1–7, Turn −5…+1, Fade 0–5), typed as putter / midrange /
fairway_driver / distance_driver, plus a derived
`stability(disc) = fade + turn`. No per-disc mass/diameter/plastic
variation; the four flight numbers are the entire physical identity
of a disc. (Data quality caveat, visible in the file: a few
duplicated/mislabelled rows — e.g. `ddx`/`ddl` both named "DDx",
a Zone filed as a distance driver.)

### 2.2 The physics — two engines, honestly graded

**Engine A (`src/engine/disc-physics.js`, `simulateThrow`)** is the
real one. Fixed-step integration, `dt = 0.02 s`, up to 8 s:

- Launch: arm speed from disc speed (`22 + speed/14 × 8`, × power),
  direction from aim yaw/pitch and hyzer.
- Forces per step: quadratic drag (`0.5·ρ·v²·Cd/m`, ρ = 1.225,
  m = 0.175 kg, `Cd = 0.08 + (14 − speed)·0.003`); lift
  (`Cl = 0.02 + glide/7 × 0.06`, applied at 0.3 weight vertically);
  gravity 9.81.
- The disc-golf part: a **spin-decay factor**
  `spinFactor = max(0, 1 − t / (2 + fade·0.5))` blends an early
  lateral **turn force** (`turn × 0.15 × spinFactor + hyzer × 0.03`)
  into a late **fade force** (`fade × 0.08 × (1 − spinFactor)`),
  applied perpendicular to the throw line. That is the correct
  qualitative shape of a real flight: high-speed turn early,
  low-speed fade late, hyzer adding to the lateral bias.
- Wind: constant vector, small coupling (`×0.01` per step on the
  velocity update, plus a 0.5-scaled wind velocity term in the
  force sum — the two wind paths are not consistent with each
  other; see the verdict below).
- Collisions: ground at y ≤ 0 ends flight (no skip/roll in this
  engine); obstacles are vertical cylinders — inside radius and
  below 6 blocks: velocity ×0.3/×0.5 and a positional push-out.
- Output: full trajectory, distance, peak height, and a landing
  classification (`parked / in_basket / short / long / left /
  right / obstacle`) from distance + lateral offset heuristics.

**Engine B (`src/disc-physics.js`, `DiscPhysics`)** is the
Minecraft-embodied variant: per-tick updates using Minecraft
snowball constants (gravity 0.05/tick, drag ×0.99), turn/fade as
small constant lateral accelerations on vx only
(`turn·0.001·speed`, `fade·0.002·(1−speed/10)`), glide as a
speed² lift term, ground contact via `bot.blockAt` column scans,
one skip bounce, a roll-out decay, basket capture within a
1.5-block sphere, and a 0–100 landing score. It is cruder and
asymmetric (lateral force ignores throw direction), but it runs
against real terrain and a real basket position.

**Is it real enough to show measurable skill growth?** Qualified
yes for Engine A, with the qualification doing real work:

- The *decision surface is real*: because turn/fade/glide trade off
  against distance, wind, and hyzer in the integrator, disc choice
  measurably changes outcomes — the heuristic selector
  (`src/scripts/disc-selector.js`, below) parks some discs and
  buries others, and a better selector demonstrably out-scores a
  worse one on the same holes. Skill, defined as selection +
  power/hyzer choice, has somewhere to live.
- But **the thrower is noiseless in Engine A as read**: given disc,
  power, hyzer, aim, and wind, `simulateThrow` is deterministic —
  there is no release noise, no wobble, no execution error term.
  (The README claims wobble is modelled; in the code read, it is
  not.) Growth can therefore only appear in *decision quality*,
  not in execution, and a perfect selector converges to a ceiling
  quickly. Engine B inherits Minecraft's tick/entity noise
  implicitly but adds none of its own.
- Wind is the weakest force in both engines (ad-hoc small
  couplings; in A, partly double-counted), elevation is absent in A
  (flat ground plane) and present only via terrain in B, and
  neither models skip/roll on landing in A or putting at all.
  **[Our read]** the physics is a good *league* physics — honest
  trade-offs, legible causes — and not yet a *training* physics:
  add a per-player execution-noise model (release angle/power
  jitter that shrinks with practice) and it becomes one. That is a
  small, well-defined addition, not a rewrite.

### 2.3 Courses

`src/course-builder.js`: three courses are claimed by the README;
the file as read defines the 9-hole **Acadia Pines** in full
(holes 155–380 blocks, par 3–4, tee/basket coordinates with yaw,
cylindrical tree obstacles with radius/height, descriptions —
"The Opener", "Pine Needle Alley", a 320-block par-4 "Elevation
Drop" (tee y=72 → basket y=58), "The Tunnel", "Risk/Reward",
"Ace Run", "The Grove", "Water Hazard", "Clubhouse Finish") and a
`CourseBuilder` that registers courses, and can *build* them into
a Minecraft world (tee/basket placement) as well as describe them
for the simulator. Holes are data, not code — a course is a JSON-
shaped object, which matters for §5's flywheel.

### 2.4 The stochastic personality system

`src/scripts/script-engine.js` (`GolfScriptRunner`, `MoodSystem`,
`Step`, `weightedRandom`) — adapted, per its header, from the
fishing engine. Personalities are **behavior scripts** (again the
fleet's pattern): sequences of steps — `walkToTee`, `throwDisc`,
`chat` (weighted-random line pools), `branch`, `goto`, `set`,
`celebrate/complain/readCard` — executed against a shared context
(hole, par, disc in hand, distance, wind, strokes, last result).
Stochasticity enters through: weighted/random chat selection,
mood-gated chattiness, randomised delays scaled by a mood
`speedMultiplier`, and script-level branching on the last landing.

`MoodSystem`: three drifting scalars — mood (0–1, pulled toward
0.5, shifted +0.10 for parked/in-basket, −0.08 obstacle/short,
−0.04 left/right), focus (drifts to 0.7), energy (decays) — ticked
every auto-run cycle (default 3 s). It colours *expression and
pacing*, not shot quality.

The four shipped golfers (`src/scripts/v1-*.js`):

- **v1-caddy** — not a player but an advisor: calls the pure
  heuristic `recommendDisc()` (distance bands → type; wind →
  stability filters; obstacle count → speed caps; a small scoring
  pass with a "classics" bonus for Buzzz/Teebird/Destroyer/Aviar/
  Roc3/Wraith) and chats the recommendation + reason, then throws
  with the suggested power/hyzer. Its hypothesis is written in its
  header: best for human experience, moderate own scores.
- **v1-veteran, v1-showboat, v1-stoic** — the same engine with
  different line pools, branch tendencies, and throw parameters:
  personality as *style and risk posture over an identical physics
  and selection substrate*, not as different skill.

### 2.5 How a round is simulated / scored

Two scorecards exist. `src/scorecard.js` (`Scorecard` class in the
Minecraft line) tracks rounds by id: per-hole strokes/par/
scoreToPar/label (Ace…Triple Bogey), totals, performance labels,
a simple handicap (`scoreToPar × 0.9 / holes`), and per-player
best-round records. The engine-line `Scorecard` inside
`script-engine.js` is a lighter in-round version (per-hole strokes
vs par, running totals). A round in the sim line is: for each hole,
scripts walk to the tee, select (heuristically or by personality),
`simulateThrow`, advance the lie by the result, repeat to the
basket, record strokes; the runner's mood updates from landings.
There is **no persistent cross-round league table, no per-player
throw history, and no learning from recorded rounds** in this
repo — outcomes are scored and (in the Worker) displayed, then
gone. Remember that gap; §5 needs it.

---

## 3. The satellite worlds — agent-organisation patterns

One paragraph each; all reuse the §1.2 agent framework
(personality/mood/relationships/schedule + behavior scripts) with a
domain runtime on top.

**craftmind-researcher — the self-improvement loop.**
(`src/index.js`, `src/discovery.js`, `src/ai/…`) A single research
agent runs an explicit 11-step scientific cycle: knowledge-gap
spotting over its own knowledge graph → `DiscoveryAgent` hypothesis
→ literature/novelty check → controlled experiment design (one
variable at a time, `experiment-validator.js` incl. sample-size
estimation) → execution against a bot body → statistical validation
→ falsification check → knowledge-base admission *with citations to
the experiment* → peer review (`ai/peer-review-system.js`), critic
and teacher agents (`critic-agent.js`, `teacher-agent.js`), and
finally **script distillation** (`distiller-agent.js`): proven
findings are compiled back into behavior scripts, with a
`meta-learner.js` tracking which kinds of hypotheses pay off. It is
the fleet's clearest statement of the pattern *learn in the
expensive tier, distil into the cheap tier* — CUA-Master's flywheel,
in miniature, already running. A hypothesis cycle takes 4–6 minutes
of real time (README, honest limitation).

**craftmind-ranch — breeding and specialisation.**
(`src/evolution-engine.js`, `src/dna.js`, `src/fitness.js`,
`src/population.js`, `src/ai/genetics-evaluator.js`) A *population*,
not an agent: 8 base species with DNA blueprints (traits, job
preferences, learning rate as heritable data files in
`data/default-dna/*.md`), fitness awarded **only for verified
completed in-game work** (no proxy rewards — the README is explicit
and the fitness code agrees), tournament selection, single-point
crossover, mutation (default rate 0.1, strength 0.2), generational
snapshots of fitness history, soft population caps, and a
task-confidence mechanic (permanent speed-up at repeatedly
succeeded jobs — specialisation as an earned, per-individual
trait). Organisation = *selection pressure over a population*;
nobody is in charge, and improvement is a property of the lineage,
not the individual.

**craftmind-studio — director and cast.**
(`src/ai-director.js`, `src/director.js`, `src/ai/studio-agent-configs.js`,
`src/ai/directing-evaluator.js`, `src/scripts/…`) A hierarchy: one
**director** (script → shot list: scene-type detection from event
density/chat, shot-type and camera-move selection with stated
reasoning, transition optimisation) over **actor bots** with
schedules, marks, mood/focus state, and per-personality script
engines (v1-auteur / v1-hack / v1-mentor / v1-temperamental — the
disc-golf script engine's sibling). Takes, highlights, post-
production and an audience/finance layer sit downstream; a
directing evaluator scores the director's own choices. Organisation
= *one expensive-ish planner, many cheap executors, and an
evaluator watching the planner* — structurally the closest of the
four to our cascade's shape.

**craftmind-courses — teachers and classmates.**
(`src/index.js`, `src/classroom.js`, `src/ai/teaching-agents.js`,
`src/ai/socratic-engine.js`, `src/ai/adaptive-difficulty.js`,
`src/npc-teacher.js`, `src/npc-classmate.js`, `src/peer-learning.js`)
One teacher bot (named, styled — patient / challenger / Socratic /
hands-on; the Socratic engine drives question-first dialogue) plus
NPC classmates of fixed types (curious Alex, competitive Sam,
struggling Jordan) who are simultaneously students and *teachable
peers* (the human learns by teaching them back — `peer-learning.js`).
An adaptive engine tracks per-student confidence and slows pacing
before frustration; courses are JSON curricula (`courses/*.json`:
survival, building, redstone) with skill trees, spaced repetition,
quizzes, and discovery zones that hint only when stuck-detection
fires. Organisation = *a persistent authority role + a peer group
whose composition is itself the pedagogy*.

---

## 4. The second body: YuvDwi/Steve — agents as entities

`YuvDwi/Steve` ("Cursor for Minecraft"): a **Forge mod** for
**Minecraft 1.20.1 / Java 17** (`build.gradle`:
`net.minecraftforge:forge:1.20.1-47.2.0`, `java.toolchain 17`;
`mods.toml`: loader `[47,)`, Minecraft `[1.20.1,1.21)`, side
`BOTH`). Where Craftmind bots *visit* a world as clients, a Steve
*lives* in it: a custom `PathfinderMob` entity
(`entity/SteveEntity.java`), spawned with `/steve spawn <name>`
(`command/SteveCommands.java`), with vanilla goals (float, look-at-
player, wander) plus its own executor tick.

### 4.1 How Steve's brain works

- **Invocation**: only on a natural-language command (GUI opened
  with K, or commands) — there is no ambient/autonomous thinking
  loop. `ActionExecutor.executeCommand` cancels the current action
  and starts planning; the recommended path is async
  (`planTasksAsync`: the LLM call runs on a thread pool, the game
  thread polls the future in `tick()`; a synchronous path exists
  and its own javadoc warns it blocks the game thread 30–60 s).
- **Planning**: `llm/TaskPlanner.java` builds one prompt
  (`llm/PromptBuilder.java`: capabilities/action catalogue,
  formatting instructions, conversation context) and calls a cloud
  provider **once per command**, returning a whole structured
  action sequence (direct execution, explicitly *not* iterative
  ReAct — the README gives the reason: fewer API calls, less
  latency). `ResponseParser` extracts the actions; per-action
  classes (`MineBlockAction`, `BuildStructureAction`,
  `PlaceBlockAction`, combat, follow, gather…) execute them
  tick-by-tick through `ActionExecutor.tick()` gated by
  `actionTickDelay` (default 20 ticks = 1 s between action checks).
- **Providers**: OpenAI / Groq / Gemini, each with sync + async
  clients. One shared API key field; provider chosen in config
  (`SteveConfig`: provider default `groq`, model default
  `gpt-4-turbo-preview` for the OpenAI field, `maxTokens` default
  8000 in code — the example toml says 1000 — temperature 0.7).
  The OpenAI endpoint is a hard-coded constant
  (`https://api.openai.com/v1/chat/completions` in
  `llm/OpenAIClient.java`) — there is **no base-URL configuration**,
  so a local/OpenAI-compatible endpoint cannot be pointed at
  without a code change (a small one).
- **Cost controls**: better than nothing, still not a budget.
  A Caffeine-backed `LLMCache` (SHA-256 prompt keys; its javadoc
  claims 40–60 % hit rates), and a Resilience4j wrapper
  (`ResilientLLMClient`: circuit breaker, retry, **rate limiter**,
  bulkhead) plus an `LLMFallbackHandler` across providers. But
  there is no token/spend accounting, no per-agent budget, no
  local-model tier, and `maxActiveSteves` (default 10, up to 50)
  is a count cap, not a cost cap. Per command = one unbounded
  frontier call (plus retries/fallbacks that can multiply it).
- **Memory**: `memory/SteveMemory.java` — current goal + last 20
  action descriptions, **persisted to the entity's NBT**
  (`SteveEntity.addAdditionalSaveData`/`readAdditionalSaveData`),
  so a Steve's goal and recent history survive world save/load and
  server restarts. `memory/WorldKnowledge.java` — a *snapshot*
  scan (biome + block census + entities within radius 16, sampled
  every 2 blocks) taken at construction; summaries (top-5 blocks/
  entities, nearby player names) feed prompts. Perception is
  therefore: full server-side truth, but only as a coarse,
  on-demand census — no continuous perception stream, and the scan
  itself is ~17³/8 ≈ 4,600 block-state reads each time it's built.
  `StructureRegistry` catalogues built structures.
- **Multi-agent**: `action/CollaborativeBuildManager.java` —
  server-side, `ConcurrentHashMap`-guarded; a build's block list is
  deterministically partitioned into spatial quadrants
  (NW/NE/SW/SE sections), each Steve atomically claims a section,
  placement conflicts are prevented by the partition, progress is
  tracked per section with reassignment on completion. Simple,
  deterministic, and genuinely conflict-free *for builds*; it does
  not generalise to non-spatial tasks.
- **Code execution**: `execution/CodeExecutionEngine.java` — a
  GraalVM JS context with a properly paranoid configuration
  (`allowAllAccess(false)`, no IO, no native, no threads/processes,
  no host-class lookup) exposing only a `SteveAPI` bridge, for
  LLM-written scripts. Together with the plugin system
  (`plugin/PluginManager`, action plugins registered into the
  executor), Steve has *two* extension tiers Craftmind also has:
  actions-as-plugins and scripts-as-programs.

### 4.2 Craftmind body vs Steve body

| | Craftmind | Steve |
|---|---|---|
| Body | External Mineflayer **client**; a fake player over the protocol | **Entity inside the server**, a custom mob |
| Brain lives | In the bot process (Node, anywhere on the network) | In the **server JVM** (mod code), calling out to cloud APIs |
| Server needs | Any server a client can join; nothing installed | **Forge 1.20.1** with the mod, on server *and* (for its entity/GUI) clients |
| Persistence | Bot-side files (memory/relationship JSON in `data/`, `memory/`); world doesn't know the bot between logins | **NBT on the entity** — memory rides the world save; the agent is *in* the world's own persistence |
| Perception | Protocol-limited: what a client may see (chunks, entities, chat) — honest, partial, like a player's | Server truth, one block away — but used only as coarse snapshots (`WorldKnowledge`) |
| Tick budget | Bot's own process; a slow bot lags only itself | **The server's 20 TPS thread** — every Steve's executor ticks there; planning is async precisely to protect it |
| Failure blast radius | A crashed bot = a player disconnecting | A misbehaving mod = server lag/crash for *everyone*, humans included |
| Model calls | Per chat message (2 s floor), ~10 % thoughts, occasional script edits | One per command, whole-plan, cloud frontier |
| Identity | A player account (needs a joinable account / offline-mode) | A spawned entity with a name; no account needed |

What the entity model makes **easier**: true persistence and
presence (the agent is there when you log in, standing where it
was, remembering its goal); zero account/auth friction; direct
access to world state for planning and verification; deterministic
multi-agent partitioning inside one process. What it makes
**harder**: everything shares the server's tick and failure
domain; scaling agents = scaling load on the one machine that also
serves the humans; perception *richness* is available but any
continuous use of it competes with the game loop; and the mod pins
the whole world to one Minecraft/Forge version.

---

## 5. THE MAP — where the rolling-perception cascade attaches

Our cascade, in one line: cheap always-on reflex tier →
diff-gated perception (only what changed gets expensive attention)
→ budgeted reflective calls in a metered unit (embed-seconds today,
"mind-seconds" for model calls) → a corrections/trust ledger that
scores who mattered and demotes who didn't → per-stream budgets and
a tenancy ladder that yields shared resources rung by rung.
Component by component:

### 5.1 Reflex tier — it already exists, twice

- **Craftmind**: `behavior-script.js` *is* the reflex tier —
  prioritised rules, pure evaluation, no model calls, fired per
  tick — backed by the state machine (hard reflexes with validity
  and timeouts) and plugin reflexes (eat/flee/equip/respawn).
  The disc-golf `script-engine.js` and studio/course script
  engines are the same invention per-domain. **Attach point:**
  none needed; name it, and route everything else around it.
- **Steve**: vanilla goals + `BaseAction.tick()` implementations
  are the reflex tier, and `ActionExecutor`'s queue is its spine.
  The cascade's contribution is not a new tier but a *gate in
  front of the planner*: most commands Steve receives are
  routine in context (follow, gather more of the same, continue)
  and could be resolved by cached plans / script templates
  (Steve already caches identical prompts) instead of a fresh
  frontier call. **[Speculation]** a diff-gate on *world state
  since last plan* (SteveMemory + WorldKnowledge deltas) decides
  "replan vs continue" — today every command replans from zero.

### 5.2 Diff-gated perception — present as novelty, absent as gating

- Craftmind already computes the gate signal: `NoveltyDetector`
  (σ-surges per key) feeding `AttentionBudget.interrupt()`. What
  it gates today is *attention callbacks*. **[Attach]** point the
  same signal at perception itself: Mineflayer gives the bot a
  continuous event stream (block updates, entity spawns/moves,
  chat); today `_buildContext` samples a fixed 20-block snapshot
  per chat call regardless of what changed. A telltape-style
  fingerprint-and-diff over the bot's local world model would let
  the brain's context contain *what changed*, and let silence
  mean "nothing changed" provably — the freshness-by-novelty rule
  (silence is stamped meaningful only when the instrument has
  demonstrated discrimination on this run's inputs) applies to
  agent perception verbatim.
- Steve inverts the problem: perception is free and total
  (server-side), so the gate must be *self-imposed* — a
  WorldKnowledge that diffs successive scans and only wakes the
  planner on material change would convert Steve from
  command-driven to event-driven without new machinery. The cost
  being gated there is not perception but **server CPU**: the
  16-radius census is exactly the kind of always-on scan our
  cascade exists to budget.

### 5.3 Budgeted reflective calls — the insertion points

The unbounded (or only rate-limited) model calls, i.e. where a
mind-seconds meter and a per-agent budget slot in:

1. `BrainHandler.handleChat` — every qualifying chat message,
   floored at 2 s, 200 tokens, frontier-ish model. **Insert:**
   AttentionBudget as the single front door (it already has
   priorities, per-entry intervals, and a calls/minute cap);
   promote its unit from *calls* to *estimated tokens/seconds*,
   split per bot, and let chat fall to local models first with
   cloud as the top rung (the `apiUrl` is already configurable —
   a Thor-hosted OpenAI-compatible endpoint is a config change
   here, not code).
2. `BrainHandler.autonomousThought` — currently ~10 % random,
   output discarded to a log. **Insert:** make it novelty-gated
   (fire on `NoveltyDetector` severity, not dice) and *route its
   output into the DecisionEngine/script queue*; an intention that
   cannot change an action is spend without effect, and the
   ledger (§5.4) should score it as such.
3. `ScriptWriter.suggestScriptChanges` — already rare, already
   quality-scored and A/B tested; the natural **top rung** of the
   ladder (the "occasional call upward" for self-modification).
   It needs only a meter and a budget line; its A/B machinery is
   already the adoption gate our weight-patch governance uses
   (propose → verify → adopt/deny → rollback).
4. Steve's `TaskPlanner.planTasks` — one cloud call per command,
   multiplied by retries/fallback. **Insert:** a budget check in
   `ActionExecutor.executeCommand` (the single choke point every
   command passes), the LLMCache promoted to a *plan library*
   (parameterised templates for repeated command shapes), and a
   local-model first rung — which requires the one code change
   noted in §4.1 (configurable base URL) since the endpoint is a
   hard-coded constant today.
5. The satellites' LLM seats — researcher's hypothesis cycle,
   studio's director, courses' Socratic teacher — were not audited
   for call frequency (their runtimes are partly in files read for
   structure, not for invocation). **[Speculation, grounded in
   their shapes]** each has the same three-seat pattern (chat /
   periodic reflection / artefact authorship) and the same
   insertion: one metered front door per world, not per agent.

**Tenancy ladder translation.** On a shared Thor (§6), the ladder
becomes social scheduling: rung 1, ambient chat falls to the
smallest local model; rung 2, autonomous thoughts pause; rung 3,
script-writing and research cycles defer; rung 4 (never yielded):
safety reflexes and any agent mid-conversation with a human.
Craftmind's `AttentionBudget.focus()` (one entry gets 5 s
intervals, everyone else ×3) is a two-rung prototype of exactly
this, already written.

### 5.4 The league / trust ledger — where it lives

Nothing in any of these repos keeps a cross-session, cross-agent
record of *who mattered*. The pieces to build it from exist:

- `Agent.relationships` (trust ±, counts) — per-agent, in-memory,
  dyadic: the seed of a reputation ledger, missing persistence
  and outcomes.
- `DecisionEngine`'s session records + `ComparativeEvaluator`
  (success rates per script, per conditions) — a *script-level*
  trust ledger already, missing the agent level and corrections.
- `leaderboard/engine.js`, disc golf's `scorecard.js` (handicap,
  best rounds), ranch's `fitnessHistory` — outcome records,
  kept per-world, never folded back as corrections.
- Craftmind's `data/memory/memory.json` (242 KB in-repo) shows
  persistence is file-JSON by convention.

**Attach point:** a single append-only ledger service beside the
bots (in our topology: on the Thor), fed by hooks that already
emit the raw events — state-machine transitions, script session
outcomes, scorecard records, fitness awards, Steve's
`ActionCompletedEvent`/`MetricsInterceptor` (Steve *already has*
an interceptor chain publishing action metrics — the cleanest
tap in either codebase). Corrections enter the way ours do:
human taps ("that mattered" / "not a change") and judged outcomes
(round scores, task completions), producing per-agent *and*
per-script trailing judged precision — the demotion figure from
our trust-loop work — which then steers §5.3's budgets (trusted
agents get mind-seconds first) and §5.5's construction. In
disc-golf terms this is precisely the missing piece from §2.5:
a league table with memory, where an agent's disc choices are
scored against outcomes over rounds, not vibes per round.

### 5.5 The course-builder flywheel — what it needs that isn't there

Target: courses that mutate against the league's *measured*
weaknesses (CUA-Master's outer loop, with terrain as the data).
Present: holes as data (`course-builder.js` — JSON-shaped,
buildable into a world *and* simulable); a deterministic
simulator to pre-test a mutation (Engine A); a heuristic selector
whose failures are legible (it tells you its reasons); scorecards.
Missing, in dependency order:

1. **Recorded throws.** Per-agent, per-hole, per-disc throw
   outcomes persisted (lie → choice → result), without which
   "weakness" is unmeasurable. (Scorecards record strokes, not
   decisions.)
2. **An execution-noise / skill model** (§2.2): otherwise the
   league's weakness is always the selector's, never the arm's,
   and courses tuned to it teach nothing about throwing.
3. **Aggregation**: weakness = a statistic over the ledger
   (e.g. strokes-lost-by-cause per hole: water, tunnel exits,
   long par-4 second shots), with enough rounds to clear noise —
   the researcher's `experiment-validator.js` sample-size habits
   are the in-family template.
4. **A mutator with constraints**: hole edits as governed
   proposals (move a basket, add a tree cylinder, change par) —
   generated by rule or by the ScriptWriter-pattern LLM seat,
   **pre-flighted in Engine A** against the league's recorded
   distribution (a mutation that makes a hole impossible or
   trivial fails simulation review), adopted one at a time with
   rollback to the prior hole definition. All data, so all
   reversible — the patch discipline transfers exactly.
5. **A/B by rotation**: alternate mutated/original holes across
   rounds (ScriptWriter's A/B scaffold, reused) so improvement
   claims are measured, not narrated.

None of 1–5 requires new physics or new agent machinery. It is a
ledger plus a governor — which is to say, it is our platform's
home ground.

---

## 6. Deployment topology — Orin world, Thor home, two laptops

The owner's intended shape: **a Minecraft Java server on the Orin**
(the front-room box; a Jetson Orin Nano-class machine — the fleet
footer in every Craftmind README names the vessel "JetsonClaw1,
Jetson Orin Nano 8GB"), **the owner's two laptops joining as human
players**, and **the Thor connecting as the agent community's
home** — cascade, local models, budgets, and ledger on the Thor;
agents join the Orin's world from there.

### 6.1 Which pieces run where

| Piece | Home | Why / cost |
|---|---|---|
| Minecraft server (world, tick loop) | **Orin** | The world must be where the humans' session is hosted; a small-population Java server is a 2–4 GB JVM — feasible on 8 GB, not roomy |
| Human clients ×2 | Laptops | Vanilla or Forge clients (see §6.2 — the choice is forced by the server flavour) |
| Craftmind bot processes (Node/Mineflayer) | **Thor** | Each bot is a Node process + pathfinding on the *bot's* CPU; on the Thor they cost the server nothing but protocol traffic. LAN latency Thor↔Orin is ~milliseconds — irrelevant next to 2 s think floors and 1–3 s actor latencies the repos themselves quote |
| LLM calls (chat/thought/script) | **Thor** (local first) | `LLMClient`/`ScriptWriter` take a configurable `apiUrl` → a Thor-hosted OpenAI-compatible local endpoint is config, and the cloud becomes the top rung only. This is what makes "mind-seconds on a budget" physically real: the meter sits next to the models |
| Cascade: AttentionBudget front door, novelty gate, ledger, trust loop, course mutator | **Thor** | Append-only files/services beside the bots; the ledger is fed over LAN by bot/server events — trivial bandwidth (scorecards and transitions, not frames) |
| Steve mod (if used) | **Inside the Orin server JVM** | Non-negotiable: the entity lives where the world lives. Its LLM calls would originate *from the Orin* to cloud endpoints as written — under this topology that breaks the "budgets live on the Thor" rule unless Steve's planner is proxied/patched to call the Thor (the hard-coded OpenAI URL means a code change, §4.1) |

### 6.2 The Forge/Paper/vanilla conflict — stated plainly

**One world, one server flavour, and the two bodies want
different flavours:**

- **Craftmind bots** join as protocol clients. They are happiest
  with a **vanilla or Paper** server: nothing to install, bots and
  vanilla human clients alike just connect. Paper additionally
  gives server plugins and the best small-machine performance of
  the three. (Operational footnote, standard for Mineflayer:
  bots need either real accounts or an **offline-mode** server —
  on a home LAN that is the pragmatic choice, and it means anyone
  on the LAN can join under any name; acceptable at home, worth
  saying out loud.)
- **Steve requires Forge 1.20.1** — on the server *and*, because
  the mod registers a custom entity type and a client GUI
  (`mods.toml` side `BOTH`), on **every connecting client**: both
  laptops would need Forge 1.20.1 + the Steve jar to see Steves
  and open the K panel. **Paper cannot run Forge mods at all** —
  Paper+Steve on one world is not a configuration that exists.
  Craftmind bots *can* in principle join a Forge server as
  clients, but a modded server with custom entity registries is
  exactly the case vanilla-protocol bots handle worst (registry
  mismatches commonly refuse or break the connection) — treat
  Craftmind-on-Forge as **unproven until tested**, not as a plan.
- So the topology forces a fork in the road:
  **(A) Paper/vanilla on the Orin** → Craftmind community + human
  laptops, trivially, today; no Steve. **(B) Forge 1.20.1 on the
  Orin** → Steve entities + Forge'd laptops; the Craftmind
  community's admission is an experiment, and the Orin's 8 GB now
  carries Forge overhead plus every Steve's tick on the same
  thread as the humans' game. **(C) [speculation]** hybrid
  Paper/Forge cores exist in the ecosystem; none is in either
  repo, and betting the family world on one is a research task,
  not a default.
  Our recommendation, from the map: **start with (A)**. The
  community, the ledger, and the disc-golf league are all
  Craftmind-shaped; Steve is one (excellent) *body* whose
  planner-seat ideas (whole-plan calls, plan caching, interceptor
  metrics) port into the cascade without its server marriage.
  Revisit (B) as a deliberate second world — a Forge world is a
  fine *destination* for a Steve colony once the cascade exists
  to budget it.

### 6.3 Load and latency, honestly

- Orin server: the tick budget is the scarce resource. Craftmind
  bots cost it little (they're clients). Under option (B), every
  Steve's `ActionExecutor.tick()` + any `WorldKnowledge` rescans
  come out of the same 50 ms tick the humans feel; `maxActiveSteves`
  is the owner's hand on that tap.
- Thor: bot processes are light; the real load is local-model
  inference for the reflective tier — which is the cascade's home
  turf (budgets, yield ladder when the Thor's other work calls).
  Keeping inference on the Thor and the world on the Orin is the
  right split: each box's scarce resource (Orin tick, Thor GPU)
  is spent by the tier that owns it.
- Perception traffic: Craftmind bots perceive through the game
  protocol itself (chunk/entity packets the server already sends
  players) — the rolling-perception platform adds *no* camera/
  embedding load to this world at all. Its "streams" here are
  event streams, and its budgets are mind-seconds. The expensive
  senses (I-JEPA etc.) stay with the house cameras where they
  belong.

---

## 7. Licences and activity

From LICENSE files and repo metadata, checked 2026-11-05:

| Repo | Licence | Last commits |
|---|---|---|
| Lucineer/craftmind | **MIT** (LICENSE file present, © 2026 CraftMind Contributors) | 2026-04-27 (fleet-footer), substantive 2026-04-07 |
| Lucineer/craftmind-discgolf | **MIT claimed in README; no LICENSE file in the repo** (GitHub detects none) | 2026-04-27 / 2026-04-07 |
| Lucineer/craftmind-researcher | **MIT** (LICENSE present) | 2026-04-27 / 2026-04-07 |
| Lucineer/craftmind-ranch | **MIT** (LICENSE present) | 2026-04-27 / 2026-04-07 |
| Lucineer/craftmind-studio | **MIT** (LICENSE present) | 2026-04-27 / 2026-04-07 |
| Lucineer/craftmind-courses | **MIT** (LICENSE present) | 2026-04-27 / 2026-04-07 |
| YuvDwi/Steve | **MIT claimed in README and in `mods.toml`** (`license="MIT"`); no standalone LICENSE file in the tree as read | 2026-07-28 (README), substantive 2026-01-18 |

Activity read: the Craftmind family is a finished spring-2026
body of work (a documentation/fleet refresh in April, quiet
since) — stable to build on, not a moving target. Steve's last
substantive commits are January 2026 with a July README touch.
`craftmind` is by far the largest repo (~500 MB of git history —
mostly `server/` world data and memory files in-tree; the source
proper is ~70 MB across 409 files).

---

## Appendix — reading notes and limits of this map

- Read line-by-line: craftmind `brain.js`, `attention-budget.js`,
  `script-writer.js`, `behavior-script.js` (parser + head),
  `state-machine.js`, agent-framework `agent.js` +
  `decision-engine.js`, `bot.js` (structure), plugins index +
  rate-limiter, `novelty-detector.js` (head); discgolf both
  physics engines, disc database, disc selector, script engine,
  all four v1 scripts' pattern (caddy in full), course-builder
  (Acadia Pines in full), both scorecards; Steve `TaskPlanner`,
  `ActionExecutor`, `SteveEntity`, `SteveMemory`,
  `WorldKnowledge`, `CollaborativeBuildManager`,
  `CodeExecutionEngine`, `SteveConfig`, `build.gradle`,
  `mods.toml`.
- Read for structure (headers, exports, organisation), not every
  line: the four satellites' runtimes; craftmind's economy/quest/
  tournament/federation subsystems; Steve's individual action
  classes and async client internals.
- Not done: nothing was executed. No bot was run, no server
  started, no throw simulated by us — physics judgements are from
  the integrator code as written. Local copies were assembled
  under `~/workspace/craftmind-read/` from the public repos
  (full `git clone` of craftmind is heavy — ~500 MB — and timed
  out on this connection; the read copies are the complete
  load-bearing source files, verified against the repos' trees).
