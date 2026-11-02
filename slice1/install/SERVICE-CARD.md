# CONFLUENCE — SERVICE CARD

*Keep with the Thor. Everything on this card is safe to do.*

## What it is

The Thor in the back room watches the house's streams — starting
with one phone camera — and writes down what changed. Phones and
browsers are just eyes and screens; the Thor does the thinking.
The family page (shelf + "what changed" feed) is at:

    http://thor.local:8210/            [interface]

## The three commands you need

Run these on the Thor, as the normal user:

    systemctl --user restart confluence     # fixes most stalls
    systemctl --user status confluence      # is it running?
    curl -s http://127.0.0.1:8077/cards     # is the rack awake?
                                            # (JSON back = yes)

The health page — one line per stream, heartbeat ages — is at
`http://thor.local:8210/health` [interface]. Fresh heartbeats
(seconds old) mean healthy. Everything stale means restart
(command 1). One stream stale means that phone/camera — check
its app is still streaming.

## Where the logs live

    journalctl --user -u confluence -f          # live log
    ~/confluence/ledger/attention/feed.jsonl    # the feed, as text
    ~/confluence/logs/                          # stage receipts

## The rack

The image-understanding rack is separate. Start/stop (needs
sudo, and that's expected):

    sudo systemctl start jev-rack
    sudo systemctl stop  jev-rack

First picture after a start takes ~12 s while it loads. Normal.

## Call Casey instead of fixing it when…

- The rack's model files fail their integrity check, or the
  rack will not stay running after one restart.
- `nvidia-smi` errors, or the GPU vanishes from it.
- The disk is still full after old evidence pictures age out
  (check `df -h ~` and `du -sh ~/confluence/frames/`).
- Anything in `~/confluence/ledger/` looks corrupted — never
  edit or delete the record book by hand.
- The same fault comes back twice in one visit.

Full guide: `INSTALL.md` in the same folder as this card.
