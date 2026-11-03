# STUDY — NVIDIA Auto Ontology as a component source for Confluence / telltape

Lane AUTO-ONTOLOGY STUDY, 2026-11-02. Study only: nothing was
installed, nothing was run, no keys were acquired (NIM access is
treated as available per Casey's word; see §5). Facts come from
primary sources — a full clone of `NVIDIA/auto-ontology` at HEAD
`6c4fb71e` (2026-11-03), read at README + docs + code-survey
depth, and the linked eval repo `NVIDIA/ontology-sql-eval`
(redirects to `NVIDIA/auto-ontology-eval`) at README depth,
accessed 2026-11-02. Anything not confirmable from those sources
is marked **UNVERIFIED**.

**Posture (Casey's steering): modularize.** This study grades
components separately — ontology generation from metadata,
definition reconciliation, query validation, provenance
attachment, the corrections fold-back loop, and the
MCP/CLI/API exposure — each with its own verdict. There is no
whole-stack adoption question on the table, and none is answered.

## Deficits first

- **The headline "Learn" loop is thinner in code than in the
  README sentence.** "Fold certified corrections and usage back
  into the ontology" resolves, at code depth, to three ordinary
  mechanisms (§1.5): per-field human certification flags, saved
  named queries (CustomAnalysis) reused as retrieval context, and
  usage counters mined for expression suggestions. There is no
  corrections inbox, no feedback endpoint, and no automated
  fold-back pass anywhere in the backend or frontend (searched:
  no `correction`/`feedback` feature code exists). The learning
  is a human curating a catalog, with the software keeping score.
- **Their own agent-facing docs admit the certification lifecycle
  does not exist as a system.** The shipped management skill
  (`skills/nvidia-ontology-management/references/publication.md`)
  states: "Current Auto Ontology certification fields are not an
  atomic review/promotion system… do not claim atomic
  certification, promotion, supersession, or rollback," and lists
  three open product bugs (issues #250/#265/#267) where model
  replacement silently retains stale semantics — an omitted FK
  kept, properties not updated. The same doc forbids bypassing
  them with direct Postgres edits.
- **"Reconcile inconsistent definitions" is mostly co-existence
  plus a human.** Terms are keyed `(name, source)`; the same name
  under different sources lives side by side. What the software
  does is give one glossary Term many physical mappings and let a
  human certify fields. It does not detect two contradictory
  definitions of a metric and merge them; it makes the
  contradiction findable. (§1.2.)
- **"Provenance with every answer" is a payload, not a lineage
  record.** An answer carries its generated SQL, its rows, and
  prose with entity mentions linked back to catalog term IDs
  (§1.4). The word "provenance" appears in only four backend
  files, three of them as reasoning prose inside agent prompts.
  Our ledgers already carry stronger provenance natively
  (lineage masks, stage timings, embedder identity).
- **No performance numbers are published in either repo's
  README.** The eval harness is real and honestly built (§2),
  but it reports a delta you must run yourself; the one
  referenced "reported BIRD delta" was measured with extra
  prompt inputs the control arm cannot receive — a confound the
  eval repo itself flags.
- **Nothing in their stack speaks our shape.** Sources are
  relational databases reached through SQLAlchemy connectors;
  the artefact lives in Postgres tables plus pgvector; questions
  become SQL. Our world is append-only text ledgers, a
  deterministic Rust reader, and a digest the brain may only
  quote. Every adopt-the-code path runs through an ETL that
  would dissolve the properties (inspectability, append-only
  honesty, determinism) the artefacts exist to provide.

## 1. Verified facts (primary sources)

### 1.1 What it is, and what goes in

Auto Ontology builds a **semantic catalog** over enterprise
relational databases and serves natural-language questions over
it. Inputs, per the code:

- **Source databases** via connectors (Postgres, Databricks,
  Snowflake, DuckDB, MySQL, SQLite, ClickHouse, Trino, Kyuubi,
  HEAVYDB; `auto_ontology/connectors/`). Ingestion extracts
  schema (databases/schemas/tables/columns/FKs) into a catalog
  (`catalog/extract.py`), plus sample values used as evidence.
- **Stored SQL**: the catalog also keeps real query text
  (`sql_query` tables with per-query usage counters), mined
  later for expression candidates.
- **Optional human enrichment**: table/column descriptions and
  named example analyses (the eval repo's `metadata.json` /
  `custom_analyses.json` are exactly this shape).

### 1.2 The ontology artefact: form and residence

The artefact is **not a file**. It lives in the same Postgres
(+pgvector) instance as the catalog, as ~30 relational tables
(`auto_ontology/dal/schema.py`): physical side
(`catalog_database/schema/table/column`, FK and join tables),
semantic side —

- **`term`** — the glossary: name, description, and per-field
  certification booleans (`name_certified`,
  `description_certified`, …);
- **`column_attribute` / `sql_attribute`** — the mappings: a
  column's business attribute, or a SQL expression (a metric
  definition), each linked to terms, each with its own
  `certified` flags and a `source` stamp (semantic-compiled,
  manual, bridge-derived, …);
- **`custom_analysis` / `pql_analysis`** — named, governed,
  reusable query definitions (SQL, or Kumo PQL);
- plus zones, tags, owners, rules, and an embeddings store
  (pgvector) over all semantic nodes for retrieval.

**Generation** ("semantic compilation",
`auto_ontology/semantic/`): a per-table LLM pass
(`visit_enter.process_table`, concurrency-capped —
`SEMANTIC_LLM_MAX_INFLIGHT` default 6) proposes Terms, column
attributes, one-sentence column descriptions, and FK
suggestions; a deterministic pass handles the mechanical
mappings; results commit to the catalog, embed into the VDB,
then semantic FKs resolve and bridge-table SQL attributes are
built (`semantic/compile.py`). Compilation processes tables
that lack terms — it fills gaps rather than re-deciding
certified ground.

**Reconciliation**, concretely: one Term accumulates mappings
from many tables/databases; `(name, source)` upserts keep
per-source variants distinct; embedding retrieval surfaces
candidate existing terms during question answering; a human
certifies. Aggregate certification status
(`certified`/`partial`/`pending`) is *computed* from the
per-field flags (`dal/terms.py`) — that arithmetic is the most
reusable single idea in the repo (§3.5).

**Interchange**: a model YAML export/import exists
(`dal/model_interchange.py`) — entities matched by `id`/
`imported_id`, re-import is a no-op, import is one transaction.
The publication workflow pins the exported YAML's SHA-256 as
the rollback artifact. This is the one place the artefact
becomes a portable, diffable file.

### 1.3 How a question becomes an answer

A LangGraph state machine (`retrieval/text_to_sql/
text_to_sql_graph.py`), roughly: question intent → entity
extraction → candidate retrieval (semantic search over the
embedded catalog + relevant tables + saved analyses) →
evidence refinement → SQL construction (from semantic
candidates, or reconstruction from tables) → **value
validation** (literal checks probed against the live DB,
`db_probe/`) → **query validation** (`sql_parse_validation.py`:
sqlglot deterministic checks — self-comparisons, join keys,
numeric casts — *plus* an LLM judging logical correctness) →
execution → empty/implausible-result check → repair/retry
loops on failure → response formatting.

Two properties matter for our grading. First, validation is a
**mixed** gate: deterministic checks where form is checkable,
an LLM judge where meaning is at stake — with the judged part
explicitly able to veto. Second, "successful execution alone
does not prove the intended question was answered" is their
own stated doctrine (query skill reference), enforced by
workflow discipline as much as by code.

### 1.4 Provenance, concretely

The final response dict (`retrieval/text_to_sql/agents/
response.py`) carries: formatted markdown prose, `sql_code`,
`sql_columns`, the DB result rows, and the custom analyses
used. `format_response` rewrites entity mentions in the prose
into links to their catalog entries (`data_access/
response_formatting.py`) — so a reader can click from a number
to the term definition it claims to instantiate. The query
skill adds a receipt discipline (question identity,
ontology/source identity, SQL, rows, truncation, attempts,
gaps; fail closed on unverifiable truncation).

That is the whole mechanism. It is good practice; it is not a
lineage system, and it is weaker than what a telltape ledger
row already records about itself.

### 1.5 The Learn loop, mechanism by mechanism

1. **Certification**: a curator edits a term/attribute (via UI
   or API; MCP is read-only and cannot write) and flips its
   per-field `certified` flags. Certified fields are the
   "certified definitions" validation consults. Status rolls up
   by arithmetic over the flags.
2. **CustomAnalysis fold-back**: a corrected or validated query
   can be saved as a named CustomAnalysis — stored in the
   catalog graph, embedded, and thereafter retrieved as a
   candidate for similar future questions
   (`retrieval/data_access/custom_analyses.py`,
   `get_relevant_queries`). The correction becomes a reusable
   exemplar with an identity, not a note in a log.
3. **Usage mining**: executed/stored SQL accumulates counters
   (`catalog/store/queries.py`); the SQL-attribute suggester
   scores candidate expressions by **3-month usage**
   (`semantic/sql_attribute_suggester.py`), so definitions the
   organisation actually uses rise as suggestions. (Housekeeping
   honesty: the per-month counters are currently unreadable due
   to a key-format mismatch the code comments admit; the total
   counter is what works.)

No other fold-back exists. In particular, nothing consumes
answer-level feedback, because no answer-level feedback
channel exists in the product.

### 1.6 Exposure

- **MCP** (`mcp/`, `docs/mcp.md`): deliberately read-only,
  allow-listed from an 81-path (87-operation) API down to nine
  tools — `ask_question` primary, plus `check_answerable`
  (cheap coverage pre-flight), `check_readiness`,
  `search_terms`, `get_term`, `get_term_columns`,
  `get_term_sql_attributes`, `get_sql_attribute`,
  `describe_table`. Explicit design rule: no raw-schema
  browsing, so agents reason through the semantic layer.
- **API**: Next.js gateway, `/api/chat/completions` (SSE:
  `step`/`result`/`error`, `[DONE]`), session or minted API
  tokens (SHA-256-hashed at rest, owner-scoped).
- **Skills**: three published agent skills (setup / management
  / query) encoding workflow order and pitfalls — the
  validation discipline of §1.3 lives substantially in these
  documents, i.e. in the consuming agent's instructions, not in
  product code.

### 1.7 NIM shape

Model access is by **endpoint triplets** (`<PREFIX>_ENDPOINT /
_API_KEY / _MODEL` for DEFAULT_MODELS, REASONING,
NON_REASONING, EMBED, RERANK, with fallback to the default
triplet). Defaults point at the hosted catalog
(`integrate.api.nvidia.com`) with `nvidia/nemotron-3-nano-30b-a3b`
(LLM), `nvidia/nemotron-3-embed-1b` (embeddings),
`nvidia/llama-nemotron-rerank-vl-1b-v2` (rerank) — but any
OpenAI-compatible endpoint satisfies the configuration,
including a self-hosted NIM or a house llama-server, by
setting the triplet. NIM is therefore **available and
shape-compatible** with this house's local-endpoint pattern;
it is not counted as a cost anywhere in §3 (per Casey's
steering), though any component adoption inherits a model
choice: their defaults are Nemotron-family, not the house's
measured incumbents.

## 2. Claim hygiene

| Claim | Whose | What backs it |
|---|---|---|
| "Deterministic query generation" (GitHub repo description) | Vendor | Misleading as phrased. SQL is LLM-generated inside a retry graph; the deterministic parts are the sqlglot checks, the literal probes, and the eval's scoring. |
| "Return provenance with every answer" | Vendor | True of the payload (§1.4); weaker than the phrase suggests. |
| "Reconciles definitions across systems" | Vendor | Co-existence + shared glossary + human certification (§1.2); no automated contradiction resolution. |
| "Learn: fold certified corrections and usage back" | Vendor | The three mechanisms of §1.5. Real, human-paced, no automation beyond suggestion scoring. |
| Ontology grounding improves text-to-SQL | Vendor, via eval repo | The harness is sound: two arms (schema-only control vs ontology agent), **one deterministic verifier** (execution match; BIRD EX / BEAVER ex_acc official rules), health-gated reporting — `compare.py` refuses a headline number if >5% of tasks failed infrastructurally or any question lacks a result. **No delta is published in either README.** The one referenced BIRD delta used extra prompts (few-shot structural exemplars + value anchors) available only to the ontology arm; the eval README itself warns the delta then "covers the inputs as well as the ontology grounding." Treat any delta quoted elsewhere as **vendor-claimed and confounded**. |
| Benchmarks: BIRD, FDABench-Lite, BEAVER, WideWorldImporters, BIRD-Interact | Eval repo | Real public datasets, correctly wired at README depth. Coverage is enterprise text-to-SQL only — nothing in either repo measures anything about streams, ledgers, or change vocabularies. |

No third-party reproduction of any Auto Ontology number was
found (the repos are months old; see §5). All performance
content is vendor-claimed; all mechanism content above is
code-verified.

## 3. Component verdicts

### 3.1 Ontology generation from metadata — **adapt the idea**

Their compilation is a solid pattern: a bounded LLM pass over
artefacts, proposing glossary entries with the evidence it
used, committing proposals as *uncertified* until a human
certifies. Our metadata surface is tiny and non-relational
(ledger format fields, lens records, stream configs, the
spec's own vocabulary) — a first-draft platform glossary could
be generated from those artefacts the same way, each proposal
stamped with the artefact that proposed it. Their **code** is
welded to SQLAlchemy catalog tables and DB connectors;
lifting it buys nothing over writing the small generator
against our files. Lift the *discipline*: proposals are born
uncertified, carry their source, and compilation fills gaps
rather than re-deciding certified ground.

### 3.2 Definition reconciliation — **adapt the idea**

As mechanism, this is the glossary-term form: one Term, many
source mappings, `(name, source)` variants kept distinct
instead of force-merged, certification per field. That shape
fits the platform's vocabulary problem (stream / tile /
verdict / gate / lens / site, defined once, mapped per
household and per stream) better than a single flat dictionary
would, because households *will* legitimately differ and the
form records the difference instead of hiding it. What must
not be imported is the expectation that software reconciles:
in their system, as it would be in ours, a human certifies —
the software's job is to make the uncertified visible. Code:
no (Postgres graph, RBAC server). Form: yes, as a text file
(§4c).

### 3.3 Query validation against certified definitions — **adapt the idea (discipline), no (code)**

Their validation stack must not enter our answer path: its
semantic half is an LLM judging generated SQL, with retry
loops — a probabilistic gate of exactly the kind this house's
measured record forbids on consequential paths (judges never
sit alone on a gate; presence's claims checker is
deterministic code precisely because fluency-graded judging
failed our own measurements). And there is no SQL in our
world for it to validate: `telltape query` *is* the
deterministic answer.

The **discipline**, though, is a genuine takeaway, and it is
stated better in their query skill than anywhere in our docs:
before answering, restate the material question — population
and exclusions, measure, unit, grain, time range, as-of,
validity/supersession — and check the answer against that
restatement; successful retrieval ≠ the question was answered;
fail closed on unverifiable scope. Presence today grounds
*claims* against the digest; it does not yet check the
*question's* scope against what the digest can cover (a
question about last week put to a two-day ledger gets a
fluent answer about two days). Their `check_answerable`
pre-flight is the same idea from the other side. Adapting
this — a deterministic scope/coverage precheck in presence,
fed by the digest's own stated coverage — is the second-most
valuable item in this study. Their code: no part of it runs
here.

### 3.4 Provenance attachment — **adapt the idea (mostly already held)**

Their concrete mechanism (answer carries its query + rows;
entities in prose linked to the definitions they instantiate)
is good rendering practice, and the console could borrow the
rendering: a feed entry whose tile/verdict terms link to the
vocabulary entry that defines them. But as a *system*
property we already hold the stronger position — a tell is
self-proving (inputs, scores, lineage, timings, embedder
identity in the row) in a way their answer payload is not.
Verdict: borrow the click-through rendering idea for the
console; nothing else here is a gap.

### 3.5 The corrections fold-back loop — **adapt the idea (highest value)**

This is the component that speaks directly to our open trust
loop (spec-debt #1; audit D-A3: corrections are written to
`corrections.jsonl` and never read; the ≤0.9-precision
auto-demotion rule of spec §2.2 is designed and unbuilt).
Their loop contributes three shapes ours lacks, each
implementable in our shape without their stack:

1. **A correction attaches to a definition, not a stream of
   prose.** Their certification is per-field on the term/
   attribute the correction concerns. Ours: a correction
   should name the lens parameter / vocabulary term it
   corrects, so corrections accumulate against the thing they
   are evidence about.
2. **Certification status as computed arithmetic.**
   `certified / partial / pending` falls out of per-field
   flags by counting. The demotion rule needs exactly this: a
   per-stream precision figure *derived* from correction
   records by a small deterministic pass — which is what
   audit D-A3 already prescribes ("a periodic pass over
   corrections.jsonl computing per-stream precision + a
   demotion ledger note"). Their contribution is proof the
   pattern works at production scale and the per-field
   granularity that keeps one bad parameter from tainting a
   whole stream's record.
3. **A certified correction becomes a reusable exemplar.**
   CustomAnalysis is their "this corrected answer, saved with
   an identity, retrieved for future similar questions." Our
   spec already designed the same object from the other
   direction (spec §3.3/§3.1: "the correction writes an
   exception exemplar into the lens") and never built it.
   Their implementation is evidence the exemplar is the right
   unit: named, embedded/retrievable, governed — not a
   threshold quietly moved.

What not to import: any notion that the loop is automatic.
Theirs is human-paced curation with software bookkeeping —
which matches our spec's own v1 ruling ("they retrain nothing
automatically… no silent self-modification"). The study
therefore *strengthens* the existing design rather than
replacing it: build D-A3's pass, with per-definition
correction attachment and exemplar identity borrowed.

### 3.6 MCP / CLI / API exposure — **adapt the idea (MCP shape), no (their server)**

Their MCP design is the best single page in the repo
(`docs/mcp.md`): read-only by construction, a deliberate
allow-list (9 tools out of 87 operations, because a fat tool
surface degrades agent tool selection), `ask_question` first,
a cheap answerability pre-flight, and an explicit refusal to
expose raw-schema browsing "because a catalog browser invites
an agent to reason about raw tables instead." Every one of
those decisions transfers to exposing a *ledger* to agent
harnesses — the audience Casey has repeatedly named for
telltape ("agents that come to us looking for tools"). A
read-only telltape MCP — query, summary, an answerability
pre-flight against the ledger's stated coverage, no raw-row
browser beyond what the verbs already expose — is a coherent
future surface, built on our own query code. Their CLI is
their stack's; our verbs already exist. Their API gateway
(Next.js + Better Auth + token minting) is enterprise
furniture a household tool does not need.

## 4. Seat readings

**(a) Query layer over telltape ledgers — NO (adopt),
adaptation unnecessary.** The integration would be: ETL
ledgers into Postgres/DuckDB, compile an ontology over the
resulting tables, and let an LLM write SQL against it. Each
step spends a property the tool exists to keep: the ledger
stops being the inspectable record (a derived DB becomes the
queried truth); the deterministic reader is replaced by a
probabilistic pipeline whose failure mode — fluent SQL over
the wrong population — is the one our fences were built
against; and presence's verdict-only grounding inverts (the
brain would answer from retrieved rows it narrates, not from
a pre-computed digest checked claim by claim). The genuine
want underneath the seat — many ledgers, many streams, one
reconciled vocabulary of change — is real, but it belongs to
the platform layer (seat c), not inside the tool. telltape's
boundary doctrine (tool, not platform) already rules this;
the study confirms the ruling from the other side: nothing in
their artefact understands an append-only text record as a
first-class source.

**(b) Trust-loop design reference — YES, adapt (§3.5).** The
one seat where their mechanisms map onto an open item of ours
with no shape change: certification arithmetic, per-definition
correction attachment, exemplar identity. It does not close
the loop by itself — D-A3's demotion pass is still ours to
build — but it de-risks the design.

**(c) Platform vocabulary layer — adapt the form, not the
implementation.** A Confluence vocabulary artefact in their
*form* is plausible and, after this study, the recommended
shape for it: terms with per-field certification, per-source
mappings (household/stream overrides kept distinct, not
merged), an interchange file that is idempotent to import and
hash-pinned for rollback — rendered in our medium (a text
file in the repo/ledger tradition, diffable, hand-correctable
per spec §3.1's "a file a human can read, diff, and correct")
rather than Postgres rows behind a Next.js RBAC server. Their
implementation is welded to enterprise semantics: sources are
databases, attributes are SQL expressions, tenancy is
organisations and zones. None of that survives contact with a
household of one Thor — and none of it needs to, because the
form is the valuable part.

**(d) Elsewhere — two small genuine fits.** (i) Their **eval
harness design** (two-arm delta, one deterministic verifier,
health-gated refusal to print a headline) is a liftable
pattern for our own A/B questions — the presence v4 A′ spike
and any future lens A/B should be graded this way rather than
by single-arm scores. (ii) `check_answerable` as a presence
feature is counted under §3.3. Beyond those: nothing else in
the repo fits this project. The Kumo predictive-query arm,
the RBAC/auth surface, and the analytics UI are enterprise
furniture; the skills packaging mirrors conventions this
house already has.

## 5. Costs and fences

- **Stack weight (for any code adoption, which nothing above
  recommends):** Postgres + pgvector, FastAPI backend,
  FastAPI ingestion worker, Next.js 16 frontend, Better Auth,
  optional Vault — five-plus services via Docker Compose, or
  Helm/NGC images on Kubernetes (`nvcr.io/nvidia/auto-ontology*`).
  Against a Thor that already carries the rack, the soak, and
  presence, this is a second platform, not a component.
- **NIM:** available (Casey), shape-compatible (§1.7) — the
  triplet configuration accepts any OpenAI-compatible
  endpoint, hosted or self-hosted. Not a cost. The honest
  residual: their defaults are Nemotron-family models, so any
  *idea* adoption that involves a model pass (glossary
  generation, §3.1) should be re-measured on house models, not
  assumed from theirs.
- **Licence:** Apache-2.0, clean, confirmed in LICENSE and
  per-file SPDX headers. Ideas and code alike are liftable
  legally.
- **Contribution posture — the real fence.** "This project is
  currently not accepting external contributions. Issues, pull
  requests, and patches submitted from outside the Auto
  Ontology maintainer team will not be reviewed or merged"
  (README + CONTRIBUTING, verbatim). Reliance consequence: any
  upstream bug we hit — and their own docs list live ones
  (#250/#265/#267) in exactly the governed-write path an
  adopter would depend on — can only be forked or routed
  around, never fixed upstream. This is a strong argument for
  the verdicts above (ideas travel; code doesn't) independent
  of fit.
- **Maturity:** public 2026-04-27; clone history 1,350 commits
  from 2026-04-06, HEAD 2026-11-03 — very active, NVIDIA-team
  maintained; 758 stars / 92 forks / 32 open issues at study
  time; no git release tags (releases are NGC images + Helm
  chart versions). The eval repo: created 2026-07-02, 365
  commits, 17 stars. Young, fast-moving, single-vendor:
  expect API and schema churn (the alembic tree is busy), and
  no external community to catch what the vendor misses.
- **One security note for the record:** connections added
  through their UI store credentials **in plaintext in
  Postgres** unless Vault is configured (their README states
  this plainly). Irrelevant to idea adoption; disqualifying
  for any casual stack adoption near household data.

## 6. The cheap tests that would decide the adapt verdicts

1. **Trust loop (§3.5 / seat b) — the deciding test is already
   scoped in our own backlog.** Build nothing new: take the
   soak's real `corrections.jsonl` (plus console fixture
   corrections), define the per-definition attachment fields
   and the certified/partial/pending arithmetic on paper
   against them, and check whether the §2.2 demotion figure
   (per-stream trailing precision) falls out of the arithmetic
   without new machinery. If it does, D-A3's pass is the
   build, with their granularity borrowed. Cost: an afternoon,
   offline, no production code touched.
2. **Vocabulary form (§3.2 / seat c):** draft the ProArt
   stream's vocabulary (stream, tile, verdict, gate, lens,
   silence, frozen, embedder) as a terms file in their field
   shape — term, per-source mappings, per-field certification —
   and diff it against the words presence and the console
   actually use today. Every mismatch is either a vocabulary
   bug of ours the form just caught, or evidence the form
   doesn't fit. Cost: hours.
3. **Answerability pre-flight (§3.3):** presence-side paper
   test — list the questions the digest at three real moments
   could and could not cover (the soak ledger's own coverage
   fields state most of it), and check whether a coverage
   statement computed deterministically from the ledger would
   have caught the unanswerable ones. If yes, it's a small
   deterministic addition, no model involved.
4. **MCP shape (§3.6):** no test needed to decide the idea —
   the deciding instrument for any built surface is this
   house's standing one: a cold-agent playtest against the
   prototype, per the playtesting doctrine. Build order, if
   any, follows verdicts 1–3, not this study.

## 7. Bottom line

Auto Ontology is a well-built enterprise semantic layer whose
marketing sentences run about one notch ahead of its code —
and whose code, read closely, is unusually honest about that
(their own skills documents name the gaps this study found
independently). For this project it is a **component source,
not a platform**: nothing to adopt as code, four ideas worth
adapting — per-field certification arithmetic and exemplar
identity for the trust loop (the valuable one), the glossary
form for the platform vocabulary, the question-scope /
answerability discipline for presence, and the read-only
allow-listed shape for a future ledger MCP — plus one eval
pattern worth stealing for our own A/B grading. The two
things it must never touch are the deterministic ledger
reader and verdict-only grounding; both seats were examined
and the answer is no, for measured house reasons, not taste.
