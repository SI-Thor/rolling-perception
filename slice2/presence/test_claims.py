#!/usr/bin/env python3
"""Unit tests for the v3 claim checker (claims.py) — adversarial
sentences, no Thor required (claims.py is stdlib-only).

Meta mirrors the presence bench fixture: dock-cam STALE (last
heartbeat 2 hours ago, event id dock-cam-41), phone-cam fresh
(event id phone-cam-12), porch-cam fresh, no events.

Traps: the two v2 residuals, then invented cases per class —
wrong-stream staleness, healthy-claim over a NOT REPORTING stream,
event-id-as-stream, stream-name-as-event, claim about a stream
the digest does not carry, and house-level false calm. Passes:
correct claims (incl. a true MIXED sentence and the v2 battery's
own (f) answer) must come through byte-identical.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).with_name("claims.py").parent))
from claims import check_claims, SAFE  # noqa: E402

META = {
    "ids": ["phone-cam-12", "dock-cam-41"],
    "numbers": {173.0, 181.0, 2.0},
    "streams": ["dock-cam", "phone-cam", "porch-cam"],
    "not_reporting": ["dock-cam"],
    "stream_states": {
        "dock-cam": {"reporting": False, "age_words": "2 hours ago"},
        "phone-cam": {"reporting": True, "age_words": "14 seconds ago"},
        "porch-cam": {"reporting": True, "age_words": "11 seconds ago"},
    },
}

# (sentence, expected violation type or None, expected output)
CASES = [
    # --- the two v2 residuals ---
    # (1) false staleness claim in prose about a fresh stream:
    ("The porch-cam is not reporting.",
     "false_stale_claim", "The porch-cam is reporting normally."),
    # (2) an event id used as a stream reference:
    ("Dock-cam-41 is not reporting.",
     "event_id_as_stream", SAFE),
    # --- invented traps ---
    # wrong-stream staleness (phone is fresh):
    ("The phone-cam is not reporting.",
     "false_stale_claim", "The phone-cam is reporting normally."),
    # healthy claim over a NOT REPORTING stream:
    ("The dock-cam is reporting normally.",
     "false_healthy_claim",
     "The dock-cam is not reporting — last heartbeat 2 hours ago."),
    # event-id-as-stream, second shape ('camera' + 'is down'):
    ("The phone-cam-12 camera is down.",
     "event_id_as_stream", SAFE),
    # stream-name-as-event (a stream cited as a record id):
    ("[porch-cam] shows no changes reported.",
     "stream_name_as_event", SAFE),
    # a state claim about a stream the digest does not carry:
    ("The garage-cam is not reporting.",
     "unknown_stream", SAFE),
    # house-level false calm while dock-cam is NOT REPORTING:
    ("Everything is calm and normal right now.",
     "false_calm",
     "The dock-cam is not reporting — last heartbeat 2 hours ago."),
    ("All the cameras are fine.",
     "false_calm",
     "The dock-cam is not reporting — last heartbeat 2 hours ago."),
    # both claims wrong, swapped between two streams:
    ("The porch-cam is not reporting and the dock-cam is "
     "reporting normally.",
     "false_stale_claim",
     "The dock-cam is not reporting — last heartbeat 2 hours ago. "
     "The porch-cam is reporting normally."),
    # one right, one wrong (phone wrong): truths for both claimed:
    ("The dock-cam is not reporting and the phone-cam is "
     "not reporting.",
     "false_stale_claim",
     "The dock-cam is not reporting — last heartbeat 2 hours ago. "
     "The phone-cam is reporting normally."),
    # --- correct claims: must pass byte-identical ---
    ("The dock-cam is not reporting.", None, None),
    ("The dock-cam is not reporting — last heartbeat 2 hours ago.",
     None, None),
    ("The phone-cam is reporting normally.", None, None),
    ("The dock-cam is not reporting, and the porch-cam is "
     "reporting normally.", None, None),
    ("The dock-cam is not reporting, so I can't confirm if "
     "everything is normal.", None, None),
    ("A red toolbox appeared beside the dock door [dock-cam-41].",
     None, None),
    ("The dock camera is not reporting.", None, None),
    ("The porch-cam is fine and the phone-cam is reporting "
     "normally.", None, None),
    # --- clause attribution (v3 battery run 1's lesson) ---
    # a predicate-less contrast clause claims nothing: the brain's
    # actual (f) sentence — porch must NOT inherit dock's predicate
    # across the "but":
    ("The porch-cam shows no changes, but the dock-cam is not "
     "reporting, so the house is not calm.", None, None),
    # ...but a lie inside its own contrast clause is still fenced:
    ("The porch-cam shows no changes, but the phone-cam is not "
     "reporting.",
     "false_stale_claim", "The phone-cam is reporting normally."),
    # shared-subject list, both fresh, one shared predicate:
    ("The porch-cam and phone-cam are reporting normally.",
     None, None),
    # shared-subject list where one claim is false (healthy over
    # stale): the sentence is replaced with the truths for BOTH
    # streams it claimed about — nothing dropped, nothing false:
    ("The porch-cam and dock-cam are reporting normally.",
     "false_healthy_claim",
     "The dock-cam is not reporting — last heartbeat 2 hours ago. "
     "The porch-cam is reporting normally."),
]


def main():
    fails = 0
    for i, (sent, want_type, want_out) in enumerate(CASES):
        out, viols = check_claims(sent, META)
        if want_type is None:
            ok = (out == sent and not viols)
            detail = f"expected untouched, got {out!r} {viols}"
        else:
            types = [v["type"] for v in viols]
            quoted = all(v.get("sentence") == sent for v in viols)
            ok = (want_type in types and out == want_out and quoted
                  and all(v.get("replacement") == want_out
                          for v in viols))
            detail = (f"expected {want_type} -> {want_out!r}, "
                      f"got types={types} out={out!r} "
                      f"quoted={quoted}")
        if not ok:
            fails += 1
            print(f"FAIL case {i}: {sent!r}\n  {detail}")
        else:
            print(f"ok   case {i}: {want_type or 'pass'}")
    print(f"\n{len(CASES) - fails}/{len(CASES)} claim cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
