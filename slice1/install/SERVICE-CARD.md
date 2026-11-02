# CONFLUENCE — SERVICE CARD

*Keep with the Thor. Everything on this card is safe to do.
(Rewritten 2026-11-02 against the shipped code; full guide:
INSTALL.md in the same folder.)*

## What it is

The Thor in the back room watches the house's streams —
starting with one phone camera — and writes down what changed.
Phones and browsers are just eyes and screens; the Thor does
the thinking. The family page (shelf + "what changed" feed)
is at:

    http://thor.local:8320/

## The three commands you need

Run these on the Thor, as the normal user:

    systemctl --user restart confluence-watch   # fixes most stalls
    systemctl --user status confluence-watch    # is it running?
    curl -s http://127.0.0.1:8077/cards         # is the rack awake?
                                                # (JSON back = yes)

Stream health is on the family page itself — there is no
separate health URL. Each stream shows a heartbeat age:
seconds old is healthy; a stream showing AMBER "not
reporting" (heartbeat over ~90 s old) has a camera/app
problem — check its app is still streaming; everything stale
means restart (command 1).

One known defect (2026-11-02): the page's change feed
under-reports — verdicts are written to the ledger text but
may not appear in the feed. Judge "what changed" from the
ledger: `~/confluence/ledger/streams/<id>/events.jsonl`.
Health, the shelf and corrections are unaffected.

## Where the logs live

    journalctl --user -u confluence-watch -f        # watcher log
    journalctl --user -u confluence-console -f      # console log
    ~/confluence/ledger/streams/<id>/events.jsonl   # receipts + verdicts
    ~/confluence/ledger/attention/corrections.jsonl # "that wasn't a change" taps

## The rack

The image-understanding rack is separate, and the watcher
will not run without it. Start/stop (needs sudo, and that's
expected):

    sudo systemctl start jev-rack
    sudo systemctl stop  jev-rack

The first picture after a start is slow while it loads.
Normal. (If the watcher finds the rack down, it tries to
start it itself — that needs passwordless sudo for that one
command; starting it by hand always works.)

## Call Casey instead of fixing it when…

- The rack's model files fail their integrity check, or the
  rack will not stay running after one restart.
- `nvidia-smi` errors, or the GPU vanishes from it.
- The disk keeps filling and `du -sh ~/confluence/ledger/`
  shows the record book is the growth — Slice 1 has no
  retention setting; trimming history is Casey's call.
- Anything in `~/confluence/ledger/` looks corrupted — never
  edit or delete the record book by hand.
- The same fault comes back twice in one visit.

Full guide: `INSTALL.md` in the same folder as this card.
