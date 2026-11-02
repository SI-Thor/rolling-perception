#!/usr/bin/env python3
"""Presence v3 — the deterministic claim checker.

v2 fenced ids and numbers with string matching (grounding_check in
presence.py). Its two recorded residuals were prose-shaped:

  1. A false staleness CLAIM in plain words — "The porch-cam is not
     reporting" said about a fresh stream — contains no bracketed
     id and no number, so the v2 check waved it through.
  2. An event id used loosely as a stream reference ("dock-cam-41
     is not reporting") — the id EXISTS, so the v2 check passed it;
     the misuse is grammatical, not referential.

This module fences both the same mechanical way: before a reply is
spoken, every sentence's CHECKABLE claims are verified against the
digest's computed meta (never against the brain's words):

  * stream-state claims — a sentence asserting a stream is or is
    not reporting / healthy / down, checked against the digest's
    per-stream computed state. Attribution is CLAUSE-LOCAL: the
    sentence is split on commas/semicolons and contrastive
    conjunctions (but/while/whereas/yet), and a mention takes the
    nearest state predicate IN ITS OWN CLAUSE. A clause with no
    state predicate makes no state claim — "The porch-cam shows
    no changes, but the dock-cam is not reporting" claims nothing
    about porch (v3's first battery run taught this: nearest-in-
    sentence attribution fenced a true sentence). Inside a clause,
    a true mixed pair ("dock-cam is not reporting and phone-cam
    is not reporting either") still verifies per mention.
  * entity references — a bracketed citation that names a STREAM
    (stream-name-as-event), a bare event id carrying a stream
    predicate (event-id-as-stream), and a state claim about a
    "-cam" name the digest does not carry (unknown stream).
  * house-level calm claims — "everything is normal / all cameras
    are fine" while any stream is NOT REPORTING (and the sentence
    is not itself negated) is a false_calm violation.

A failed sentence is replaced with the TEMPLATE TRUTH for its kind:
the computed state rendered in words ("The porch-cam is reporting
normally." / "The dock-cam is not reporting — last heartbeat
2 hours ago."), or the safe template for referentially broken
sentences. The violation is returned with the original sentence
quoted, for the receipts. Correct claims pass byte-identical.

Pure stdlib (re only): small, deterministic, unit-tested by
test_claims.py against adversarial sentences.
"""
import re

SAFE = "I don't have a record of that."

# State predicates. NEG = the sentence asserts NOT reporting;
# POS = asserts reporting/healthy. Word-bounded so "is reporting"
# never matches inside "is not reporting" (the words between break
# the match) and "showed up" never matches "is up".
_NEG = re.compile(
    r"\b(not reporting|n't reporting|stopped reporting|"
    r"no longer reporting|gone silent|went silent|is silent|"
    r"is down|is offline|not watching|stopped watching|"
    r"no heartbeat)\b", re.I)
_POS = re.compile(
    r"\b(is reporting|are reporting|reporting normally|"
    r"is healthy|are healthy|is fine|are fine|is working|"
    r"is up|is online|is watching|are watching)\b", re.I)
# House-level calm assertions (checked only when not negated).
_CALM = re.compile(
    r"\b(everything is (calm|normal|fine|ok)|everything's "
    r"(calm|normal|fine|ok)|all is (calm|normal|fine)|"
    r"the house is (calm|normal|fine)|"
    r"all (the )?cameras are (fine|ok|healthy|reporting))\b", re.I)
_NEGATION = re.compile(r"\b(not|no|never)\b|n't", re.I)

_ID_BARE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+-\d+\b")
_CAM_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*-cam\b(?![-\d])", re.I)
_BRACKET = re.compile(r"\[([^\]]+)\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(r"[,;]|\b(?:but|while|whereas|yet)\b", re.I)


def _sentences(text):
    return [s for s in _SENT_SPLIT.split(" ".join(text.split())) if s]


def _truth(name, state):
    """The computed stream state, rendered as one true sentence."""
    if state.get("reporting"):
        return f"The {name} is reporting normally."
    age = state.get("age_words")
    if age and age != "never":
        return f"The {name} is not reporting — last heartbeat {age}."
    return f"The {name} is not reporting."


def _mention_spans(sentence, name):
    """Spans where a stream is mentioned: its digest name (guarded
    so 'dock-cam' does NOT match inside the event id 'dock-cam-41')
    or the spoken form 'the dock camera'."""
    spans = [m.span() for m in re.finditer(
        re.escape(name) + r"(?![-\d])", sentence, re.I)]
    if name.lower().endswith("-cam"):
        base = name[:-4]
        spans += [m.span() for m in re.finditer(
            r"\b" + re.escape(base) + r"\s+camera\b", sentence, re.I)]
    return spans


def _sentence_claims(sentence, meta):
    """Check one sentence. Returns (violations, state_claimed) where
    state_claimed = set of stream names the sentence makes a state
    claim about (right or wrong) — the caller needs them to build
    template-truth replacements."""
    streams = meta.get("streams", [])
    states = meta.get("stream_states", {})
    by_lower = {s.lower(): s for s in streams}
    violations = []
    state_claimed = set()

    # Bracketed citations: a stream name cited as a record id.
    for tok in _BRACKET.findall(sentence):
        if tok.strip().lower() in by_lower:
            violations.append({
                "type": "stream_name_as_event",
                "value": tok.strip(),
                "stream": by_lower[tok.strip().lower()]})

    # Mask citations out: bare-token rules must not see inside them.
    masked = _BRACKET.sub(lambda m: " " * len(m.group(0)), sentence)

    # Clause-local attribution: mentions, predicates and entity
    # tokens are matched within a clause, never across a contrast.
    for clause in _CLAUSE_SPLIT.split(masked):
        preds = [(m.start(), m.end(), "neg")
                 for m in _NEG.finditer(clause)]
        preds += [(m.start(), m.end(), "pos")
                  for m in _POS.finditer(clause)]
        if not preds:
            continue
        mentions = {}
        for name in streams:
            spans = _mention_spans(clause, name)
            if spans:
                mentions[name] = spans
        # Per-mention polarity by nearest predicate in the clause.
        for name, spans in mentions.items():
            reporting = bool(states.get(name, {}).get("reporting"))
            for (ms, me) in spans:
                pol = min(preds, key=lambda p: min(
                    abs(p[0] - me), abs(ms - p[1])))[2]
                state_claimed.add(name)
                if pol == "neg" and reporting:
                    violations.append({
                        "type": "false_stale_claim", "stream": name})
                elif pol == "pos" and not reporting:
                    violations.append({
                        "type": "false_healthy_claim", "stream": name})
        # Unknown '-cam' names carrying a state predicate.
        for m in _CAM_TOKEN.finditer(clause):
            tok = m.group(0)
            if tok.lower() not in by_lower and not any(
                    tok.lower() == n.lower() for n in mentions):
                violations.append({
                    "type": "unknown_stream", "value": tok})
        # A bare event id carrying a stream predicate, with no
        # stream mentioned for the predicate to belong to.
        if not mentions:
            for m in _ID_BARE.finditer(clause):
                violations.append({
                    "type": "event_id_as_stream", "value": m.group(0)})

    # House-level calm while a stream is NOT REPORTING.
    if meta.get("not_reporting") and _CALM.search(sentence) \
            and not _NEGATION.search(sentence):
        violations.append({"type": "false_calm",
                           "stream": meta["not_reporting"][0]})
    return violations, state_claimed


def check_claims(reply, meta):
    """Verify every checkable claim in a reply against digest meta.
    Returns (new_reply, violations): failed sentences replaced with
    template truths (state failures) or the safe template (entity
    failures), each violation carrying the original sentence.
    Untainted sentences pass through byte-identical."""
    if not reply or not meta.get("streams"):
        return reply, []
    states = meta.get("stream_states", {})
    out, violations = [], []
    for sent in _sentences(reply):
        found, claimed = _sentence_claims(sent, meta)
        if not found:
            out.append(sent)
            continue
        entity = [v for v in found if v["type"] in (
            "unknown_stream", "event_id_as_stream",
            "stream_name_as_event")]
        state = [v for v in found if v["type"] in (
            "false_stale_claim", "false_healthy_claim")]
        if entity:
            replacement = SAFE
        elif state:
            names = [n for n in meta["streams"] if n in claimed]
            replacement = " ".join(_truth(n, states.get(n, {}))
                                    for n in names)
        else:  # false_calm alone
            replacement = " ".join(
                _truth(n, states.get(n, {}))
                for n in meta["not_reporting"])
        for v in found:
            violations.append({**v, "sentence": sent,
                               "replacement": replacement})
        out.append(replacement)
    return " ".join(out), violations
