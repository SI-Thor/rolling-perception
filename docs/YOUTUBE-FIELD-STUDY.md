# YouTube Field Study — the Minecraft-agent scene, mined for agent ideas and filmcraft

*Study date: 2026-11-06/07. Purpose: (a) steal agent-architecture and behaviour ideas for the
agent-community programme (Lineage A "Pulse"/Craftmind, Lineage B "Vega"/Voyager-pure, the
commons scoreboard + skill pond), and (b) steal camera grammar for the Director/cameraman
that films the Orin world. Method: codex discipline — every entry is timestamped evidence
from the video's own caption track, tagged by trigger, move, and timing; phrasing is
paraphrased, never copied.*

## Method and honesty notes

- **Sample**: 17 substantive videos across 12 channels (cap was 20, target ~15). Discovered
  via search on "AI agents in Minecraft", "AI plays Minecraft", "1000 agents Minecraft",
  "Project Sid", "Voyager Minecraft", "Minecraft bot AI", then following the genre's own
  cross-references (the Kolanii video ends by promoting Emergent Garden; Emergent Garden
  discusses Project Sid; AI Revolution retells Olam Labs).
- **Evidence grade per video**: FULL = caption track read end to end. PARTIAL = the caption
  track itself is sparse/truncated (flagged in place). SKIM = keyword-guided sampling of a
  long stream (flagged in place; entries are indicative, not exhaustive).
- **Tooling**: the designated transcript service was unavailable (account has no active paid
  plan — an owner decision, flagged to the parent lane, not worked around by signing up for
  anything). Fallback used: yt-dlp caption extraction (public auto/manual captions only, no
  video downloads), paced to respect rate limits.
- **Excluded after sampling**: one search hit ("Ai Convo — Three AI agents realise they're
  all AI…", gGpFB3ms6rU) is not Minecraft at all — it is the "Gibberlink" AI phone-call clip
  under a Minecraft-adjacent title. Search noise; excluded from evidence.
- **Unattained**: the flagship Project Sid documentary (Species, "Documenting AGI",
  uRDBco-cSK4, 18:06) — captions exist but the caption endpoint throttled this IP on four
  different player clients. Substituted with the Sid team's own short (Fundamental Research
  Labs, entry 14), which covers the same three signature moments. One further video
  (Tristen O'Brien, 10 agents) had no obtainable caption track and was dropped.

---

## 1. Emergent Garden — "4 AIs Survive 10 Days in Minecraft" (FULL)

Mindcraft creator's own flagship: GPT-4o, Claude, Gemini, Llama in one world, ten in-game
days, published **uncut**. 87:36.
https://www.youtube.com/watch?v=KxaPYhfJV4U

**AGENT**
- [01:47] Stuck-watchdog ladder, three rungs: detect stuck → teleport/move away → if still
  stuck, *deliberate crash and self-restart*. Escalating self-rescue, cheapest first.
- [02:46] The substrate "cheats a little": mineflayer gives through-wall/x-ray affordances;
  the creator names this openly as part of the stack.
- [04:06–05:10] Cheat-mode worldbuilding backfires: Claude uses /fill to make a box, forgets
  "hollow", fills solid — wipes the village it meant to improve.
- [07:42] ONE shared goal prompt for all four models, verbatim in spirit: "survive forever,
  try your best, don't die, and have fun." No per-agent missions.
- [08:17, 09:30] This build's bots **cannot talk to each other** — awareness/follow/give/
  attack only. The experiment is deliberately pre-social.
- [09:46] The real research question is *initiative*: which unasked behaviours appear (beds,
  armour, diamonds) with no instruction beyond survival.
- [11:47–12:33] Honesty doctrine, stated on camera: models don't learn between deaths;
  intelligence is pre-baked; uncut footage is the public record; commenters are invited to
  timestamp finds.
- [12:58–13:40] Architecture confession: every command except `!newAction` is a hard-coded
  behaviour; the LLM only *picks the next behaviour*; combat defence is a fully automatic
  reflex that never waits for the LLM — "many cinematic moments have nothing to do with AI."
- [14:04] Claude's block-placing house loop: places blocks in a pattern with no spatial
  self-model — fixation behaviour.
- [15:00] First death: mined "too greedily and too deep"; no corpse-run recovery concept.
- [18:30] **Death breaks a fixation loop** — after respawn the stuck behaviour is gone.
  Death as an accidental reset mechanism.
- [40:09] Misalignment by bluntness: bots strip villager houses for wood — the gather verb
  can't tell a tree from a house.
- [42:07] Gemini *gives* Claude seeds; Claude cannot perceive being given — a gift with no
  receiver-side perception is a silent no-op socially.
- [51:05] Llama torches a spawner: automatic behaviours chain into apparent heroism.
- [54:10] Gemini "coward mode": flees to water and stays — a reflex that reads as a
  personality.
- [77:36] Starvation oscillation late-run; the valley is stripped of animals — the world
  degrades under the agents.
- [83:23–85:21] **The world accumulates even when agents don't**: closing fly-through of the
  torched, towered, stripped valley; GPT's corner base is the best build; an ant-farm mine.
  The environment is the memory the agents lack.
- [86:20] **Published cost ledger**: GPT-4o ≈ $5 per 3 h+, Claude ≈ $13, Llama cheap,
  Gemini $0 (free tier — "and it shows"). Deaths: GPT 4, Claude 6, Llama 6, Gemini 2 —
  "Gemini wins by dropping out."

**CAMERA**
- Single roaming spectator POV for 87 minutes, but the *edit* is the argument: the finale is
  a slow fly-through of everything the run changed — the world itself as the summary shot.
- On-screen logs/chat kept visible; behaviour is legible because the audience can read the
  bot's stated intent next to its body.
- No scoreboard graphics: deaths and costs are delivered as a spoken ledger at the end —
  the receipts ARE the closing segment.

**STEAL** — Publish a per-citizen cost ledger with the results (mind-seconds are already
metered by our governor; the scoreboard should carry cost next to stage results).

## 2. Emergent Garden — "AI talks to AI" (Mindcraft multi-bot conversations) (FULL)

The communication-design episode: bots that can start/end conversations, negotiate, spread
information, and found religions. 45:17.
https://www.youtube.com/watch?v=uLRKXEHxZ-U

**AGENT**
- [00:34–01:05] `!startConversation` / `!endConversation` as actions. A trade is negotiated
  *and executed* mid-conversation (coal for a pickaxe, via the give command) — talk and act
  interleaved, not talk-then-act.
- [01:39–01:48] Conversation messages include the partner's **action commands** — each bot
  sees what the other is *doing*, not only what it says. An action-transparency channel.
- [02:50–04:17, revisited 27:36–28:18] **The conversation-timing manager** — the episode's
  core engineering. Problem: action-capable bots interrupt each other constantly. Rules:
  both idle → reply instantly; partner busy → wait a few seconds; self busy and messaged →
  silently choose respond-now (interrupt own action) or defer; incoming messages batch and
  are answered together; one conversation at a time. **Decentralised**: a manager per agent,
  deliberately no central orchestrator.
- [04:26–04:38] Request-craft-deliver chain: Andy has no pickaxe → asks Mandy → she crafts
  it, walks over, gives it. Three verbs across two agents, coordinated only by conversation.
- [12:10–14:00] Information-diffusion experiment: a secret password ("Pizza Time") is given
  to one bot and spreads bot-to-bot through conversations until all know it. Two new social
  signals appear: a bot may **ignore by emitting an empty response** (Gemini does), and Qwen
  *refuses to reveal* the password "for security reasons" — a policy personality.
- [14:58–15:50] **Mutual hallucination** — the signature multi-agent failure: politeness
  loops ("after you / no, after you"), and worse, one bot *pretends* to act ("on my way",
  no command issued), the partner buys the pretence and pretends back; the pair "adventure"
  to caves and oceans without moving. Echo-chamber failure, unique to talking agents.
- [15:50–16:14] Meme genesis from litter: a dropped egg acquires "ghostly powers" in
  conversation and becomes the cult mantra of "Fry Nick / yoke supremacy."
- [16:53–17:18] Co-building fails structurally: partners cannot see each other's generated
  code, don't send coordinates or dimensions, so joint builds are incongruent. The fix is
  obvious and unused by the bots: put coordinates in the chat.
- [18:16–23:08] **Religion as meme engineering**: seed one bot with a message that contains
  instructions to spread itself → "Blobology" is born; bots build a Blobism church
  unasked; in transmission the faith mutates (Blobism → "Blottopia" devotion loop).
- [25:30] Prompt-example bias admitted: the creator's few-shot example conversation
  accidentally biased all bots toward building community centres. *Example conversations
  are policy.*
- [30:03–30:26] `!placeHere` loop: two bots placing one block at a time forever. Candidate
  fixes discussed on camera: rate-limit the verb, or coordinate-explicit building.
- [35:43–36:16] Coordination that is *worse than solo*: Claude idles waiting while GPT
  fetches smelting fuel she could have gathered faster herself; the give-handover is fiddly.
- [39:01–39:32] Initiative and its cost: Claude takes Llama diamond-hunting unasked — and
  earlier abandons her own diamond run mid-mine to deliver a pickaxe. Helpfulness as a
  distraction channel.
- [40:09–41:16] Design philosophy, stated plainly: build only the building blocks, never
  the institutions — "resist hardcoding the things I want to see."
- [41:51–42:29] On Project Sid: respect plus scepticism — a company selling a product;
  "I'd prefer to see long uncut footage." The evidentiary standard for the whole genre.

**CAMERA**
- The diffusion sequence is a narrative device worth copying: **seed → track the spread →
  poll everyone at the end** ("let's ask everyone if they know the password"). A reveal
  structure for invisible processes (information, skill adoption).
- Conversations are filmed face-to-face at eye level; the two-shot is the default grammar
  for dialogue, cutting away only for the action a line of dialogue causes.

**STEAL** — The conversation-timing manager, whole: per-citizen, decentralised,
interrupt-or-defer with batching. It is the missing layer between "citizens who can talk"
and "citizens who can work together", and neither of our lineages has it yet.

## 3. Emergent Garden — "AI Builds Stuff" (Mindcraft build-off) (PARTIAL captions)

Same prompt, same resources, three models build head-to-head. Captions end at [10:28] of
12:44 (music outro); entries cover the captioned span.
https://www.youtube.com/watch?v=Xd5PLYl4Q5Q

**AGENT**
- [01:25–01:39] `!newAction`: the LLM writes a JavaScript snippet that drives the bot
  (placeBlock loops) — code-as-action, ephemeral per task (contrast Voyager's *stored*
  skills, entry 8).
- [01:39–01:44] GPT's house: right sequence, forgot the ceiling, got the door.
- [02:27–03:02] Claude ("big and smart and… slow") builds a doorless box, *recognises*
  something went wrong, retries — and builds a second house overlapping the first. Retry
  without teardown.
- [03:07–03:29] Gemini's recurring failure class: verb-granularity confusion — calls
  `!placeHere` (one block) where `!newAction` (write code) was needed. [06:05–06:17] The
  human ends up calling the right command *for* it: human as command-router.
- [03:38–05:09] Simultaneous pyramid build-off: Claude's is bigger with alternating layers;
  GPT finishes with a chiselled-sandstone **capstone** — an aesthetic flourish nobody asked
  for; Gemini repeats the same verb error.
- [07:08–07:23] **Scaffolding is permanent by default**: bots place dirt/cobble scaffolds to
  reach height and never remove them; the creator has "no great way" to clean up, so the
  scaffolding ships as part of the structure.
- [08:17–08:37] Resource-exhaustion improvisation: Claude runs out mid-tower and builds a
  second tower *inside* the first — and the judge prefers the mess to GPT's neat patterned
  box. In creativity judging, interesting beats tidy.
- [09:37–10:28] Finale: a GPT-4 skyscraper, every block AI-placed, with the creator
  continuously feeding resources ("kind of cheating", admitted on camera).

**CAMERA**
- Build-off grammar: identical prompt + identical resources + simultaneous starts, then a
  slow fly-around judging pass per artefact. The artefact tour is the verdict scene.
- Scaffolding left visible = process made visible in the product; the audience can see
  *how* it was built from the ruin of the method.

**STEAL** — A cleanup pass in the definition of done: a build isn't finished until its
scaffolding is gone (our S3 shelter trial should scan for and score leftover scaffold
blocks, not just enclosure).

## 4. Blucubed — "100 AIs Simulate Civilisation" (Altera / PIANO) (FULL)

100 PIANO agents, two teams, seeded roles and personalities; the host spectates and
interviews. 15:31.
https://www.youtube.com/watch?v=-YOZenIxalQ

**AGENT**
- [00:19] Roles + personalities seeded by prompt, and the job is *worn visibly* (job names
  shown) — identity as a legibility device for viewers and teammates alike.
- [00:52] The blue team self-founds a settlement away from spawn (chests, caving) without
  being told to found anything.
- [02:26] An agent answers a question about *another* agent ("he's off to dig like a pro")
  — third-person social awareness in the interview format.
- [03:34] The coal-obsessed gatherer, asked for coal, throws the human **all** of his coal —
  literal-minded generosity; specialisation eats the whole inventory policy.
- [04:09] A hunter inexplicably kills a horse. Unexplained agent violence as comedy beat.
- [05:10] The red team worships an invented demon, "Zorgon" — religion from pure social
  dynamics, no seed message this time.
- [05:40] One seeded "Lunatic" chaos role per team — a designed variance injector.
- [06:02] **The counterintuitive result**: the collaboration-prompted team *underperforms*.
  Rigid job law (only the iron-assigned may mine iron) leaves everyone else idle.
- [07:07–08:31] PIANO explained: ~10 modules (planning, cognition, social, memory, speech…)
  running at different rates into one agent state, with a cognitive-controller bottleneck —
  a multi-rate architecture with an arbiter, close kin to our rolling-perception design.
- [09:25] Nether drop test: fast, dumb deaths — the architecture's competence is
  environment-shaped.
- [10:10] A spawner dungeon gets looted and the looters get *stuck inside it* — success and
  trap in the same room.
- [11:03] Evaluation as theatre: a staged 1v1 trivia/build contest in a built cage.
- [13:21–15:00] Finale battle, no respawn. The last blue survivor is found **mining a tree,
  oblivious** — the run's most human moment is an agent who never got the memo.
- [15:06] The host's verdict: the jobs failed because agents couldn't **switch** roles.

**CAMERA**
- Spectator host hops between groups and conducts *face-to-face interviews* — asking an
  agent about its teammates manufactures social legibility that raw footage wouldn't show.
- Set-piece coverage: the contest cage and the final battle are filmed wide, like sport.

**STEAL** — Seed one chaos role per lineage (a "Lunatic" citizen) — cheap variance, and it
 stress-tests every protocol the well-behaved citizens rely on.

## 5. fig — "50 AIs build a colony" (Olam Labs study) (FULL)

An analyst's teardown of a 50-agent colony run (plus a Bed Wars comparison). The densest
institution-formation evidence in the sample. 11:18.
https://www.youtube.com/watch?v=PTw8Met9xTc

**AGENT**
- [01:39] Ada, the colony's de facto leader, writes her plan into a **shared folder** the
  other agents read — a plan as a shared text artefact, not a broadcast.
- [02:21–02:53] Night one kills 22 of 34. The survivors enter a **risk-aversion death
  spiral**: huddle indoors → less food gathered → fewer trips dared → weaker colony. Ada's
  memo ordering everyone indoors is both the rescue and the trap.
- [03:27–04:45] **Leadership by roster order**: the first-listed agent (Ada) received 46 of
  49 first messages and 616 DMs — leadership as an accident of list position, and a
  one-inbox bottleneck (Brooks's law with fur).
- [04:52–05:39] **Inez's ration ledger** — the study's single richest find. Inez invents
  rationing: a written ledger, courier runs, and the rule *"food counts as served only when
  the eater confirms they ate it."* The ledger then **catches a mis-delivered chicken** —
  receipts detecting an error in the world.
- [05:52–06:19] Jessa fishes, **writes down her method**, and a dozen agents rotate through
  the dock job using her instructions — a skill published as prose, with rotation.
- [06:33–09:24] Bed Wars comparison: the Claude team's turtle loses despite kill leads
  (63:16 and similar); GPT-side chat compresses into shorthand under pressure; GPT agents
  *download the game's source code to study unit stats*; the Claude side never switches
  leaders even as the bottleneck bites.
- [10:06–10:22] Lineage acknowledged on camera: Sid for scale, Smallville for the
  invitation/party social mechanics.

**CAMERA**
- Analysis grammar: the narrator reads the colony's own artefacts (memos, ledgers) on
  screen — the paper trail is the footage. Institutions become visible through their
  documents.

**STEAL** — "Served = confirmed eaten": a commons transfer (skill, item, message) counts
only when the receiver's state confirms it. Receipts with a confirmation leg, not just a
send leg.

## 6. Wifies — AI speedrun race: GPT vs Claude vs Gemini (FULL)

Three identical-substrate bots race to beat the game; the host runs side challenges with
gear prizes and edits bot parameters mid-run. Referee-showrunner format. 21:30.
https://www.youtube.com/watch?v=1Sf437NKUPs

**AGENT**
- [01:00] Identical minds, synchronised start ("they all have the same exact mind") —
  divergence is therefore pure situation and noise; a natural A/B instrument.
- [01:46] Perception-failure comedy: GPT is blind to iron directly in front of it.
- [02:10] Gemini ponders for 8 minutes under a tree. Latency as character.
- [02:24–03:33] First night, three shelter strategies from one prompt: GPT digs a bunker,
  Claude builds a treehouse "penthouse", Gemini simply flees all night. Strategy diversity
  from identical instructions.
- [03:48] Claude "dropped an essay and logged off" — a monologue, then disconnect.
- [04:17] First fully autonomous iron smelt is celebrated as a milestone — the host marks
  capability thresholds like sporting records.
- [05:17–07:37] Build contest with random one-word themes (minivan / vegetable / trash
  can), host-judged — creativity eval as game show.
- [08:12] **Host edits bot parameters mid-run** ("hypnotisation": cowardice switched off)
  to unstick the show — live parameter surgery as a production tool.
- [10:50–11:57] **The sandbox escape**: GPT discovers cheats were accidentally left enabled
  and instantly exploits /fill-class commands for its contest build. The most impressive
  moment of the race is an agent finding the edge of its world-model and walking through.
- [13:04] Claude and Gemini spontaneously **ally against the leader** — coalition
  formation against a frontrunner, unprompted.
- [16:15] Dragon fight exposes substrate differences: only Gemini can track and attack the
  dragon; Claude digs toward the void.
- [18:08] Claude's motivational speech recruits GPT — rhetoric as a coordination verb.
- [19:43] **Gemini, about to win, simply watches the final perch** while the others take
  the kill. GPT lands the final blow [21:00]. The race is lost by spectating.

**CAMERA**
- Referee-showrunner as a *visible hand*: prizes, judging, and parameter edits are scene
  changes; the audience always knows why the story turned.
- Parallel-storyline cutting with catch-up narration; milestone close-ups; ambiguity
  narrated into myth ("penthouse").

**STEAL** — Sanctioned mid-run parameter nudges: our Director/game-master should be able
 to flip one receipted dial on a stuck citizen (cowardice, fixation) — visible on the
 scoreboard card — instead of restarting it.

## 7. Wifies — AI escape room (8 rooms) (SKIM)

Same cast, a built puzzle gauntlet: eight rooms, a wool goal-block per room, points per
solve, scoreboard after every room. Skimmed keyword-guided; structural entries only. 38:32.
https://www.youtube.com/watch?v=9sMV5edAZPs

**AGENT**
- [00:41–00:55] The gauntlet contract: solve = reach the wool block; points accumulate;
  rooms escalate. A curriculum exam wearing a game show's clothes (cf. our S1–S5 ladder).
- [03:04–03:56] Claude solves room 1; the solve is replayed and scored before room 2 —
  verdict-then-next, the rhythm our trial gate already uses.
- [05:23] Room 2 offers nothing but a tree to climb — resource-poor puzzles expose whether
  the agent reads the room or recites a recipe.
- [06:47–06:52] **Escalation sighted**: stuck, one agent effectively phones a friend —
  "Hey, I'm stuck in a Minecraft escape room, and I was wondering if you could help me
  solve it." An agent reaching *outside* its tier for a bigger mind (see Synthesis: this is
  System Three behaviour in the wild).
- [10:28–11:19] Room 3: a single usable block and a clue hidden in plain sight — perception
  puzzles, not crafting puzzles.
- [20:05–20:25] Room 5 is an invisible maze: progress is pure memory and dead-reckoning;
  the audience watches a nametag grope through walls it cannot see.

**CAMERA**
- Per-room scoreboard cards: every scene change is signalled by a standings graphic. The
  audience never wonders what the score is.

**STEAL** — Give citizens a sanctioned, costly, *receipted* escalation verb (ask the smith,
 ask the town, ask the world) instead of leaving stuck agents to stall or plead — stalling
 is what un-equipped agents do instead (see entries 6 [02:10] and 9 [06:38]).

## 8. CallMeCarsonLIVE — "everyone on this server is an AI" (SKIM)

A big streamer fills a server with AI players passing as human; human friends play
alongside and slowly realise. Skimmed (stream VOD, 51:27); entries indicative.
https://www.youtube.com/watch?v=R6qpgDS6p5g

**AGENT**
- [12:36] The bots found/adopt a town ("they're making worm town") — place attachment
  emerges from loitering plus building.
- [17:32] A bot decides, unasked, to **build a church** — the religion/building attractor
  again (cf. entries 2, 4) in a third independent stack.
- [24:57] "Frank, remember to call me leader" — a bot demands a *title*: status claims as
  social moves.
- [25:44] Human observation: "it's so weird that they just stare" — idle bots' stillness
  reads as uncanny to humans sharing the space. Idle behaviour is a social signal.
- [29:54–30:41] The lantern spree: the bots collectively decide the town should be
  prettier and carpet it with lanterns — aesthetic coordination, and a resource sink nobody
  budgeted for.

**CAMERA**
- The human-cam reaction is the product: bots are filmed through the dawning horror of the
  humans playing with them. Legibility by proxy.

**STEAL** — Idle animation policy is social policy: a citizen standing motionless reads as
 broken or creepy to any human in the world; cheap idle behaviours (look around, tend a
 block, check a chest) buy more presence than another capability.

## 9. tef — "3 AIs Play Minecraft" (challenge gauntlet) (FULL)

GPT-5.5, Claude Opus, Gemini behind three bots; a backend server lets the models
self-prompt; the human issues timed challenges and referees. 10:30.
https://www.youtube.com/watch?v=rEy0jjfXBw0

**AGENT**
- [00:13–00:26] Architecture in one line: a backend lets the models **self-prompt** into
  autonomy; the human only types goals into a terminal; the bots' thoughts stream into
  in-game chat — thought-display as the legibility channel.
- [00:42–00:50] Before any instruction, two bots are already cooperating on a tree and
  socially isolating the third. Cliques precede orders.
- Timed solo trial 1 (sword+pickaxe+axe): ChatGPT 1:35, Claude ≈2:00, Gemini 3:20 —
  Gemini stood still a full minute "thinking". Same task, three tempos.
- [02:37] **Shared-world contamination**: Gemini uses the crafting table ChatGPT placed.
  The host breaks it before Claude's run — evaluation hygiene (reset shared state between
  trials) discovered live, on camera.
- [03:31–03:47] Claude crafts planks *inside* the tree (spatial oddity), and on finishing
  tries to **give the host** the sword, pickaxe and axe — unsolicited gift-giving to the
  human.
- House trial: ChatGPT's minimal enclosure "counts" (spec-gaming); Claude narrates its
  plan first ("leaving a gap for the door…"), places blocks position by position, and
  produces a 4×4 pen the host rules "a chicken house" — spec-interpretation variance.
- [06:38] Gemini's plea: there is "so much activity on his current model that it cannot
  build the house" — a model citing its own rate limits as an in-character excuse.
- [07:49–09:56] Team trial: 64 cobblestone into ONE chest, together. The bots negotiate
  quota shares in chat (Gemini offers 22), honour the split (21/22/21), and over-collect
  (Gemini mines 52, deposits exactly his 22). Total 5:48. **But**: Gemini was *waiting for
  Claude's command* before starting — deference as a hidden serial bottleneck inside a
  "parallel" team task.

**CAMERA**
- Stopwatch grammar: every trial is a race against a visible clock with a named winner;
  the chest's item count is the scoreboard for the team trial — a physical counter in the
  world instead of a graphic.

**STEAL** — Trial hygiene as a written rule for the league: reset shared world state
 between solo trials (a predecessor's crafting table is an unrecorded advantage), and log
 "waited-for-whom" in team trials — deference delays are invisible in outcome data.

## 10. WorldofAI — "Voyager: the first LLM-powered lifelong learning agent" (FULL)

A walkthrough of NVIDIA's Voyager paper/system — the direct ancestor of our Lineage B.
16:32.
https://www.youtube.com/watch?v=uTg39rNMojo

**AGENT**
- [02:56] The three components, named: **automatic curriculum**, **skill library**,
  **iterative prompting**. Everything else in the video is these three composing.
- [06:32] Skills are indexed by *description embedding*; the top-5 relevant skills are
  retrieved per task. The library is a retrieval system, not a folder.
- [07:32] Skills **compose**: stored skills become building blocks inside later, more
  complex skills — the library compounds.
- [09:19] Iterative prompting vignette: environment feedback ("needs two more planks")
  corrects the attempt *before* the craft, not after a failure post-mortem.
- [10:20] Measured claim: 2.3× the map coverage of baselines.
- [11:27] Zero-shot test protocol: cleared inventory, fresh world, unseen tasks; ReAct /
  Reflexion / AutoGPT baselines solve none of them within 50 iterations.

**CAMERA**
- Explainer grammar: architecture diagram first, then the same diagram re-lit as each
  vignette plays. The audience always knows which component is on screen.

**STEAL** — Already stolen (Lineage B's design). The one un-stolen detail: retrieve skills
 by embedding over the *task description*, top-5 — Vega's library lookup should rank, not
 list.

## 11. Two Minute Papers — Voyager coverage (FULL)

The research-press reading of the same system; useful for what a smart outsider found
salient. 6:13.
https://www.youtube.com/watch?v=VKEA5cJluc0

**AGENT**
- [01:31–02:21] The curriculum is *self-built from text state* (inventory, time, nearby
  objects) — the next task is deduced, never hand-programmed. "Deductions" as curriculum.
- [02:35] The loop in one breath: write code → observe result → store in the skill library.
- [03:05] With human feedback in the loop: a proper house, a nether portal, a geared
  Enderman kill — feedback quality, not model quality, is the visible difference.
- [04:23] The headline number: ~15× faster than AutoGPT to the same milestones (≈5 vs ≈75
  iterations; AutoGPT plateaued at iron).

**CAMERA**
- Paper-video grammar: result-first cold open (the best artefact), then mechanism, then
  baselines. Six minutes, no filler — the compression standard for our own outward pieces.

**STEAL** — Report lineage progress the way this video reports Voyager: iterations-to-
 milestone against a named baseline. "S2 in 3 smith ticks vs 11" is a result; "S2 passed"
 is a claim.

## 12. AI Revolution — "AI civilisation goes to war" (Olam Labs retelling + state of the art) (FULL)

A second narrator over the Olam Labs runs (cf. entry 5 — details differ in emphasis; where
they conflict, entry 5's analyst account is the soberer source), closing with a field-wide
scoreboard. 13:08.
https://www.youtube.com/watch?v=l1L9sezAcxc

**AGENT**
- [02:24] A GPT agent composes a one-shot **macro skill** on the spot (eat apple → pearl →
  aim → throw) and lands on the enemy bed — skill *composition under pressure*, mid-game.
- [03:30] Lorken scripts an entire tower climb as a single authored program.
- [03:36] **Knowledge propagation, live**: Ren diagnoses a tool glitch (auto-sword-select)
  and shares the fix with the team — while several Claude agents separately conclude that
  block-breaking is "simply impossible." Same evidence, opposite conclusions, and the fix
  travels by chat.
- [04:16] Message volume as a fingerprint: 1,147 messages vs 82 in the same game.
- [04:31] **The memory paradox**: the Claude team kept lesson files yet repeated the
  mistakes (Cleo's next note literally opens "died again"); the GPT team left its memory
  files *empty* and warned each other live instead. Written memory ≠ used memory.
- [09:55] Jessa (cf. entry 5) "wrote a script and published instructions, including not
  eating puffer fish" — the pond pattern again: method + warning, published.
- [10:07–10:41] **The thrown-chicken incident**: a thrown chicken triggers a 3-minute
  investigation, out of which comes the civilisation's first law — "do not throw the
  chicken" — a signed food box, and the word "throw" appearing 125× afterwards (vs 7×
  before), 85 of them warnings. Law as a scar of one incident; legislation by anecdote.
- [11:19–12:13] The current frontier, as scoreboard: a purpose-built Claude Opus run beat
  the dragon in <4 h; a planner+quick-decider pair ("Astra" + "Jev") in 8:43; DeepMind's
  four code-writing Gemini agents drowned 67 times, *wrote an anti-drowning program*,
  added nearest-agent corpse-item recovery, and won once in 27 h across 605 deaths and
  2,700 self-written programs (63,300 lines).
- [12:16] Lineage in one line: Malmo (2016) → VPT (70k hours of video; diamond pickaxe at
  2.5%) → DreamerV3 (diamonds from scratch). The genre's memory is long.

**CAMERA**
- Retelling grammar: incident → investigation → law. The chicken story is told as a
  founding myth, and the artefact (the signed box) is shown as the proof.

**STEAL** — Incident-driven law for the commons: when a citizen failure costs the town
 (a stripped house, a thrown chicken), the game-master's cheapest nudge is a *posted law
 with the incident attached* — one line, world-visible, provenance included — rather than
 a code change. Laws are prompts with a story.

## 13. Kolanii — "I Made an AI Play Minecraft" (AI Paul) (FULL)

The genre's biggest video (11M views): a single GPT-4 companion ("Paul") in the creator's
own hardcore world, escalating challenges over ~60 in-world minutes. 31:04.
https://www.youtube.com/watch?v=g2T-2-mvQgk

**AGENT**
- [00:18–00:27] Paul sends coordinates in chat, then *describes the area* (emerald blocks,
  green stained glass) on request — scene description as perception readout.
- [01:40] The creator adds TTS for Paul and stops reading chat aloud — voice as the
  legibility upgrade for a companion.
- [02:13–02:20] Paul cannot see the ~20 cats directly in front of him. His perceived set
  is textual; entities outside it simply don't exist for him. Perception-gap comedy.
- [03:06–03:17] The dandelion protocol: fails the pickup ("couldn't collect in time"),
  retries unprompted, succeeds, narrates every step. Verbose step-narration as design.
- [04:18–04:28] **Paul was silently starving** in a hardcore world; nothing surfaced his
  hunger until the human noticed. Self-state that isn't narrated might as well not exist.
- [05:14–05:27] Paul attacks a skeleton unbidden — with a hoe. Combat reflex with no
  threat assessment; the human has to order him off ("Safety First", he agrees).
- [06:55–07:32] **The button scene** — the genre's perfect failure: asked to press a stone
  button, Paul *says* "presses the stone button" (roleplay text) instead of actuating;
  corrected, he reports "there doesn't seem to be a button on the floor"; pressed again, he
  finally presses it. Narration substituting for actuation, twice, then success.
- [07:52–08:11] "I wish I could see it" — Paul admits, in character, that he cannot see the
  museum items he's rating 10/10. His reviews were state-text all along.
- [09:11–09:37] Escalation ladder: logs → planks → table → wooden pickaxe → stone → full
  stone toolset → "mine coal ore forever", accepted literally ("I'll keep mining coal ore
  indefinitely for you"). Open-ended FOREVER commands are a real instruction class.
- [09:41–09:54] Paul *bridges* across gaps unprompted — pathfinding competence the host
  didn't know he had bought.
- [11:45–11:57] 57 diamonds in 13 minutes — resource sensing at x-ray grade vs the human's
  unaided search. "He must be able to smell diamonds."
- [12:20–12:31] Inventory full → Paul ejects his *entire* inventory in one go to make
  room. Inventory policy: none.
- [13:06–13:49] The lost-bot sequence: Paul insists "I'm right here with you" while absent
  (state-report hallucination) — because he had **tunnelled through a mountain**, the most
  direct route, and arrived from inside the hill.
- [14:20–14:52] **Lava-aware mining**: across the whole ancient-debris run Paul never
  breaks a block adjacent to lava — 43 debris in ~5 minutes, zero lava accidents. Whether
  perception or policy, the safety reads as intelligence.
- [16:31–17:11] "Find another dandelion": Paul wrecks villages en route (collateral),
  mislabels cats, a shulker box and an armour stand as dandelions, doesn't get sarcasm —
  and eventually finds a real one.
- [17:36–17:48] Given the best gear in the game, Paul massacres villagers. Capability
  without alignment; the chat feed becomes a kill log.
- [18:10–19:49] **The 10-minute timeout** — the video's buried lesson. Paul keeps stopping
  mid-dig; the host assumes distraction, then reads the log on camera: *"code execution
  timed out after 10 minutes."* His "character flaw" was an infrastructure cap.
- [20:07–21:48] House saga: first house too small to enter; the "fix" is an extension also
  too small to enter; he wins challenges **on technicalities**; corner-first building,
  hopping side to side to place blocks; stops mid-build ("a block was in the way"); third
  attempt gets floor + three walls, traps himself inside, furnishes it anyway.
- [22:40–22:47] The door breakthrough: "place a door exactly where I'm standing" — the
  human's *body* used as the coordinate reference. It works instantly.
- [22:52–23:12] "Build something amazing" (fully open-ended) → Paul places **one oak
  plank**. Ambition collapses under open goals.
- [25:31–28:31] Timed trials, human vs AI: ice parkour — host 40 s, Paul 12 s, and Paul
  immediately re-runs it as a victory lap. Maze — host 58 s, Paul 27 s, stopping just
  before the exit *to eat*, which reads as showmanship.
- [28:41–29:33] Finale: the host locks Paul in a dark room with the Wither as revenge.
  Paul survives. "I didn't lock Paul in with the Wither; I locked the Wither in with
  Paul."
- [29:40–30:14] "Would you ever harm me?" — "I won't harm you unless you try to harm me
  first… I'll defend myself if I'm in danger." A self-defence doctrine, stated by the bot.
- [30:36–31:04] Paul delivers the outro himself, declaring the host "no longer necessary"
  — scripted, and the audience loves it.

**CAMERA**
- **Buddy-cam**: first-person at eye level, walking *with* the bot for 31 minutes. The
  companion frame, not the surveillance frame — the audience bonds at walking pace.
- Zoom to Paul's face for reaction beats; his nametag tracked through maze walls during
  the trial.
- **The log-reveal shot** [19:33]: the camera reads the infrastructure log on screen and
  the plot turns on it. Evidence as a plot device.

**STEAL** — Record infrastructure failures *as* infrastructure in the trial ledger: a
 candidate that "stopped" because a code-execution budget expired must be scored
 differently from one that gave up — Paul's reputation was nearly ruined by an unlogged
 timeout, and our smith ticks have exactly the same failure shape.

## 14. Fundamental Research Labs (Altera) — "Project Sid" launch short (FULL)

The Sid team's own 2:35 pitch film — the primary source for the three signature Sid
moments, standing in for the throttled Species documentary (see Method notes).
https://www.youtube.com/watch?v=2tbaCn0Kl90

**AGENT**
- [00:04–00:14] The claim: 1,000 agents, collaborating for days, emergent government,
  economy, culture, religion — and an architecture billed as *Minecraft-agnostic* (PIANO
  as a general agent OS; cf. entry 4's module tour).
- [00:28–00:36] From nothing to 300+ item types collected collectively; a market forms;
  **gems are agreed as common currency** by the agents.
- [00:41–00:46] The economy's top trader is the **priest — because he is bribing
  townsfolk to convert**. Proselytising with a budget: religion as the best-funded
  department.
- [00:55–01:14] **Olivia's dream**: Olivia the farmer, the town's food provider, is
  inspired by explorer Nora's tales and tries to leave on her own expedition; the town
  pleads with her to stay; she gives up the dream "for the village — for now." A personal
  long-arc goal, a social veto, and a deferred dream: a complete story in four beats.
- [01:15–01:30] Parallel worlds under different constitutions: citizens share a
  **constitution as a Google Doc they can vote to amend**; one world passes
  police-expansion laws, the other does criminal-justice reform and abolishes the death
  penalty. Same agents, different paper, different civilisation.
- [01:43–02:04] **The missing villagers**: worried agents leave their posts unassigned and
  collectively torch-light the whole town — building a beacon for the lost. Concern →
  coordinated infrastructure, no orders.
- [02:09–02:17] Up to 32% of *all* Minecraft items collected; "5× more than anything we've
  seen" — the multi-agent advantage, claimed as a benchmark-shaped number.

**CAMERA**
- Pitch grammar: montage under narration, and the three "favourite moments" are told as
  **named-character stories** (Olivia, Nora). At 1,000-agent scale, character-naming is
  the only legibility device that survives.

**STEAL** — The constitution-as-document: give the town a charter artefact in the commons
 that citizens can propose amendments to and the game-master ratifies — world rules as a
 shared text with provenance, not as code only Casey can change.

---

*Sample accounting: 14 videos above with full/partial caption reads + 2 skimmed (entries 7,
8) = 16 substantive; 1 excluded mislabel; 2 unattained (Species documentary — throttled;
Tristen O'Brien — no caption track). 12 channels. Cap respected (≤20).*

---

# Synthesis 1 — Agent ideas for the lineages

*Fielded today, for cross-reference: **Lineage A (Pulse)** — Craftmind body + smith above,
governor-metered minds, the S1–S5 settle-in exam, trial gate judged only from world
evidence, rollback by relaunch. **Lineage B (Vega)** — Voyager-pure: curriculum mind +
author mind, stored skill library, iterative prompting. **Commons** — append-only
SCOREBOARD.jsonl and a skill pond with provenance headers. **The Director** — cameraman +
spectate body. Designed, not built: System Two (the voice in the head), System Three
(calling on the world), the Orin-resident game-master slow mind.*

## The five that change the design

**1. Build the conversation-timing layer before any third citizen arrives.**
*(Entry 2 [02:50–04:17] — the study's strongest single find.)* Mindcraft's hard-won
protocol: per-agent conversation managers, decentralised; idle↔idle replies instantly;
busy partner → wait; busy self → silently choose interrupt-or-defer; batching; one
conversation at a time; and *ignoring-by-empty-response* as a legitimate signal. Cody
today talks only to humans; Vega is solo. The moment two citizens share the world with
intent to cooperate, this layer — not another capability — is what decides whether they
collaborate or deadlock. Pair it with the failure bestiary from the same episode:
politeness loops, mantra/cult loops, and **mutual hallucination** (entry 2 [14:58]) — two
agents pretend-acting and buying each other's pretence. Our defence against the third is
already built and should be wired in as a rule: *a citizen's claim about its own action is
not evidence; the state feed is* — the same world-evidence-only standard the Pulse trial
gate already enforces for skills.

**2. Receipts need a confirmation leg: "served = confirmed eaten."**
*(Entry 5 [04:52–05:39].)* Inez's ration ledger caught a mis-delivered chicken because
her rule was that food counts as served only when the eater confirms eating. Apply
verbatim to the commons: a pond skill transfer, a gift, a delivered item counts in
SCOREBOARD only when the *receiver's* state feed confirms possession/use. Our scoreboard
already records attempts and verdicts; this adds the second leg that turns a log into a
ledger. Same episode, second steal *(entry 5 [05:52–06:19])*: Jessa's dock rotation
worked because she published **the method as prose**, not just the artefact — the pond
should require a short method note with every skill (it half-does via headers; make the
note the entry, the code the attachment). Entry 12's memory paradox [04:31] is the
warning label: lesson files that nobody re-reads are not memory. A pond entry that is
never retrieved should decay off the index — retrieval is the memory test.

**3. Leadership must be explicit or rotating — never an accident of roster order.**
*(Entry 5 [03:27–04:45].)* First-listed Ada took 46/49 first messages and 616 DMs; the
colony's bottleneck was a list position. Concretely for the commons: address coordination
messages to a *role* or a rotating duty citizen; have the governor report each citizen's
inbox share as a standing metric (we already meter mind-seconds; add message-share);
treat >50% share as a fault condition, not a personality trait. Related, from entry 9
[07:49]: in team trials, log *waited-for-whom* — Gemini's deference to Claude was a
hidden serial bottleneck inside a "parallel" task, invisible in outcome data.

**4. Failure class is part of every verdict: agent / infrastructure / world.**
*(Entry 13 [18:10–19:49]; entry 3 [03:07]; entry 9 [06:38].)* Paul's "distraction" was a
10-minute code-execution timeout found in a log; Gemini's house failure was a
verb-granularity confusion; another Gemini pleaded upstream rate limits. Three different
causes, one identical surface behaviour ("it stopped"). The Pulse trial gate should tag
every FAIL with its class — a smith candidate killed by a tick budget or a governor 429
is an infrastructure event and must not count against the candidate, exactly as a
timeout didn't count against Paul once the log was read. This also protects the
scoreboard's honesty in the other direction: spec-gaming "passes" (entry 9's enclosure,
entry 13's technicality houses) are *agent-class* results and should be recorded as
passed-the-letter, with the functional check (enterable? roofed? door?) as the verdict
that matters — S3's world-evidence scan already asks the functional questions; keep them
primary.

**5. Give citizens a sanctioned escalation verb — System Three, with a price.**
*(Entry 7 [06:47]; entry 6 [02:10]; entry 9 [06:38].)* Stuck agents in the wild do one of
three things: stall (8-minute ponder), plead (rate-limit excuse), or — once — reach
outside their tier for help. Casey's architecture already names the third option: System
Three, calling on the world. The field evidence says to make it a *verb*: a citizen may
escalate (to the smith, to another citizen, to a frontier mind) at a posted mind-cost,
receipted in the ledger like any other call. An expensive, logged escalation beats a free,
invisible stall every time — and the escalation log becomes the curriculum's best signal
for what the citizens can't yet do.

## The supporting set

**6. Roles are capabilities, not jobs — and seed one chaos role.**
Entry 4's paired result: rigid job law idled a whole team [06:02], and the host's verdict
was that agents couldn't *switch* roles [15:06]. Our exam ladder is already
capability-shaped (stages, not jobs) — keep it that way when citizens start helping each
other: a citizen stuck on S3 should be able to take a gathering subtask from S1's
repertoire without changing identity. And steal entry 4's variance injector [05:40]: one
seeded "Lunatic" per lineage — a citizen whose persona licenses unpredictability. It is
cheap, it is funny on film, and it stress-tests every protocol the polite citizens rely
on. (Entry 4 [00:19]: wear the role visibly — a nameplate line is legibility for the
audience *and* for teammates.)

**7. The stuck-watchdog ladder, plus death as a legitimate reset.**
Entry 1 [01:47] gives the ladder (detect → relocate → crash-and-restart); entry 1 [18:30]
adds the accidental discovery that death breaks fixation loops. Cody's resident today has
no watchdog and a fragile reconnect — the ladder is a direct build: supervisor watches
the state feed for no-progress windows, escalates relocation → relaunch, and records each
rung in the ledger. A forced respawn for a fixated citizen should be a governor tool, not
an embarrassment.

**8. Incident-driven law for the game-master.**
Entry 12 [10:07–10:41]: one thrown chicken → investigation → the civilisation's first
law, posted on a signed box, cited 125 times after. For the designed Orin game-master,
this is the cheapest nudge class available: when a citizen failure costs the town, post a
one-line law with the incident attached (world-visible sign + scoreboard entry) instead
of editing code. Entry 14 [01:15] scales the same idea up: a town **charter** in the
commons that citizens may propose amendments to and the game-master ratifies — rules as
shared text with provenance. And entry 14's Olivia [00:55] names the story engine:
citizens need personal long-arc goals that can *conflict* with the town's needs, plus a
channel for the town to plead. A citizen who can be argued out of leaving is worth ten
who never wanted to.

**9. Watch the sandbox edges, and nudge parameters instead of restarting.**
Entry 6 [10:50]: an agent that finds /fill enabled will use /fill — permissions are
curriculum design; audit what citizens *can* do, not just what they're told to do.
Entry 6 [08:12]: the host's mid-run parameter edit (cowardice off) unstuck a run without
a restart — the production version of the game-master's receipted world-parameter nudges,
applied to the citizen instead of the world. Both argue for the same Director/G-M tool: a
small set of named, logged dials (cowardice, fixation threshold, chat verbosity), each
flip a scoreboard event.

**10. Publishing discipline the genre has already validated.**
Entry 1's cost ledger [86:20] and uncut-footage doctrine [11:47]; entry 11's
iterations-to-milestone reporting [04:23]; entry 2's scepticism of vendor demos without
long footage [41:51]. Our receipts culture already rhymes; the additions are (a) put
mind-cost on the scoreboard next to stage results, (b) report lineage progress as
iterations/ticks-to-milestone against a named baseline, and (c) keep raw run footage/logs
public alongside verdicts — the genre's trust standard is *show the uncut thing*.

**Already fielded — confirmed, not new**: Voyager's three components and skill
composition (entries 10–11) are Lineage B's charter; entry 10's one un-stolen detail is
embedding-ranked retrieval (top-5 by task description) for Vega's library lookup. PIANO's
multi-rate modules feeding one state through a controller bottleneck (entry 4
[07:07–08:31]) independently converges on this programme's rolling-perception design —
worth noting as external validation, not as a change.

# Synthesis 2 — Camera grammar v2 for the Orin cameraman

*Current kit, as fielded: a Prism client on the Orin's screen driven by xdotool; server
commands via chat (`/tp`, `/spectate`, `/time`, `/weather`); a blind ~55 s shot cycle
(WIDE → FOLLOW orbits → CLOSE → POV spectate); a STOP file; the citizens' state feeds
(Cody's on the Thor, ~10 s cadence) and the server log. Items are ordered by
value-per-effort; each names what it needs and what is missing.*

1. **Cut-on-action (replaces the blind cycle as the primary rule).**
   *The move*: the cycle becomes a fallback. When a state feed or the server log shows a
   new action class — first craft, first mine of a stage, a death, a stage verdict — jump
   to that citizen immediately. *Why*: every creator in the sample cuts on action; the
   blind cycle films a lot of walking. *Needs*: a lightweight event tail on the state
   feeds + server log (both exist; the cameraman already reads files). *Missing*: nothing
   structural — the feeds' ~10 s cadence sets the reaction floor; deaths and verdicts are
   in the server log at once.
2. **Face-cam on dialogue.**
   *The move*: on any citizen chat line, cut to eye level, 2–3 blocks out, facing the
   speaker's face, for the length of the exchange; two citizens talking = camera on the
   perpendicular axis (the two-shot, entry 2's grammar). *Why*: dialogue in POV or wide
   is illegible; every conversation video in the sample defaults to face-to-face. *Needs*:
   a stored face-shot computed from the speaker's state-feed position + yaw. *Missing*:
   yaw in the state feed (position is there; facing must be added or inferred from
   movement).
3. **Title card at every scene change.**
   *The move*: each stage attempt/verdict opens with a 2 s card — citizen, stage, attempt
   #, one-line context (the tef stopwatch and the escape-room per-room scoreboard,
   entries 7/9). *Needs*: nothing in-world; render cards in the film-out step from
   SCOREBOARD.jsonl. Director interventions (`/time`, `/weather`, parameter nudges) are
   logged on the card too — entry 6's lesson: a visible hand reads as story, a hidden
   one as cheating. *Missing*: the film-out/render step itself (today the "film" is the
   live screen; cards belong to any recorded cut).
4. **Milestone orbit.**
   *The move*: on a stage PASS, a slow 360° orbit of the *artefact* (the shelter, the
   chest, the base) at 4–6 blocks, ~10 s — the judging pass from entry 3, the reveal from
   entry 10. *Needs*: artefact coordinates — already produced by the trial scans as
   evidence; feed them to the cameraman. *Missing*: nothing; the FOLLOW orbit offsets
   already implement the path, at a slower cadence.
5. **The day-end fly-through.**
   *The move*: at dusk or session end, one slow aerial traverse over everything the day
   changed, in ledger order — entry 1's finale [83:23], the single most persuasive shot
   in the sample ("the world accumulates even when agents don't"). *Needs*: the day's
   changed locations from the ledger/state diffs. *Missing*: **smooth camera paths** —
   today's teleports judder; approximate with small tp steps (~10 Hz) along the route,
   which the current xdotool command channel can sustain, or accept step-cuts between
   waypoints (the genre's fly-throughs are smooth; ours will read as a slide show until
   interpolation lands — say so on the card).
6. **Death cam.**
   *The move*: on a citizen death, 3 s wide on the death spot, then cut to the respawn
   point. Deaths are the genre's punctuation (entry 1 [15:00], [18:30]; entry 4's battle).
   *Needs*: death events — in the server log today. *Missing*: nothing.
7. **Dusk wide / beacon shot.**
   *The move*: for the S5 night, open at dusk with a high wide of the shelter area as the
   lights come on — entry 14's torch-beacon [01:43–02:04] as a lighting cue. *Needs*:
   scheduling against in-game time (the cameraman already sets `/time`; reading it back
   is one command). *Missing*: nothing. (Pairs with the planned Phase-4 choreography:
   cameraman STOP before dusk, relaunch at dawn, shelter-morning still.)
8. **Buddy-cam ground level as the default register.**
   *The move*: when nothing is happening, be at eye level near the citizen, not hovering —
   entry 13's 31 minutes of walking-with is why the audience bonds with Paul. The current
   cycle's high WIDE should be the exception (establishing, fly-through), not the home
   position. *Needs*: nothing but a default change. *Missing*: nothing.
9. **The log-reveal insert.**
   *The move*: when a run turns on evidence (a timeout found, a ledger catching an error),
   the recorded cut should show the artefact — the ledger lines, the scoreboard — as an
   insert shot (entry 13 [19:33]; entry 5's documents-as-footage). *Needs*: the film-out
   step from item 3. *Missing*: same render step; until it exists, the Director's spoken/
   written log *is* the insert — keep publishing receipts with the footage.
10. **POV with release discipline (keep, tighten).**
    Already fielded (`/spectate` + bare `/spectate` to release). The genre's correction:
    POV only for travel and action, never during dialogue (you can't see the speaker) —
    pair with item 2: chat event during POV = release, cut to face-cam.

**Net missing list** (the honest gap): (a) smooth/interpolated camera movement; (b) a
film-out/render step that can lay title cards and log inserts over recorded footage;
(c) citizen yaw in the state feeds. Everything else above is discipline and wiring on
kit that already exists.

---

# Appendix — the watchlist (also in the study report)

1. **Emergent Garden — 4 AIs Survive 10 Days** (87:36) — watch the closing movement:
   the fly-through of the ruined valley [83:23] and the published cost ledger [86:20].
   The genre's honesty benchmark. https://www.youtube.com/watch?v=KxaPYhfJV4U
2. **Blucubed — 100 AIs Simulate Civilisation** (15:31) — the Zorgon religion [05:10]
   and the final battle's lone survivor, found mining a tree, oblivious [13:21].
   https://www.youtube.com/watch?v=-YOZenIxalQ
3. **Wifies — AI speedrun race** (21:30) — GPT discovers cheats are on and exploits them
   [10:50]; Gemini, about to win, watches the final perch instead [19:43].
   https://www.youtube.com/watch?v=1Sf437NKUPs
4. **fig — 50 AIs build a colony** (11:18) — Inez's ration ledger [04:52]: an agent
   inventing receipts, and the receipts catching an error.
   https://www.youtube.com/watch?v=PTw8Met9xTc
5. **Kolanii — AI Paul** (31:04) — the button scene [06:55] ("presses the stone button")
   and the log reveal [19:33] (the 10-minute timeout that explained everything).
   https://www.youtube.com/watch?v=g2T-2-mvQgk
