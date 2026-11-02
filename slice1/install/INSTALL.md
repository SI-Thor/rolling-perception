# Confluence — Technician's Install & Service Guide

*Slice 1 edition, rewritten 2026-11-02 against the shipped code.
Every program name, command line, port and file path in this
guide was verified against the code and against a complete
install run recorded in `INSTALL-PROOF.md` (same folder). If a
step here disagrees with what the machine tells you, believe
the machine and write down what it said.*

## What this system is, in five sentences

1. One Jetson AGX Thor in the house does all the thinking — it is
   the engine room, and the only computer in the system with a
   brain.
2. Phones, tablets, old laptops and browsers are thin devices:
   they lend the system their cameras, microphones, speakers and
   screens, and do no thinking of their own.
3. The Thor watches the streams those devices send it (starting
   with one camera), works out what "normal" looks like for each
   one, and keeps a plain-text record of what it sees.
4. The household opens one web page — the shelf of their media
   library plus a feed that says what changed — and otherwise
   the system stays silent.
5. Everything is open source, everything runs on the home
   network, and no account, subscription or cloud service is
   involved.

Words used in this guide: the **rack** is a program already on
the Thor that does the heavy image-understanding work (it lives
on port 8077). The **record book** (the *ledger*) is a folder of
plain-text files under `~/confluence/ledger/` where the system
writes down what it has seen — if a page ever disagrees with the
record book, the record book is right. The **watcher** is the
program `confluence-watch`; the **console** is the household web
page it pairs with.

**What is NOT in Slice 1 yet** (roadmap, not hidden): the
platform does not sweep the LAN to discover cameras — you type
the camera's address into a config file (§5). There is no
retention setting for old records (§7, fault 4). The reference
deployment also uses a small "pusher" helper on the camera
computer that sends pictures *to* the Thor; that helper is not
yet shipped in this repo, so a fresh install uses a camera the
Thor can poll directly (§5). Multi-camera installs run one
watcher service per camera; a single service watches one
stream.

---

## 1. Hardware assumptions

- One **NVIDIA Jetson AGX Thor** (aarch64, Ubuntu 24.04), on the
  home LAN, reachable as `thor.local` (its address can drift;
  the name is the durable thing).
- At least **50 GB free disk** on the filesystem that will hold
  `~/confluence/` (the ledger and the media library grow over
  time; more is better).
- One **Android phone** for the first camera (any recent phone;
  iPhone works too with an equivalent streaming app — see §5).
- The phone and the Thor on the **same Wi-Fi / LAN**.
- You have a login on the Thor. `sudo` on it is needed only to
  start/stop the rack by hand — the watcher can start the rack
  itself if it has passwordless sudo for that one command
  (§4).

## 2. Prerequisites — check before you install

Run each check on the Thor. Every one must pass before §3.

```bash
# Right machine?
uname -m
# expect: aarch64

# Graphics chip present and answering?
nvidia-smi
# expect: a table naming the NVIDIA Thor GPU, no errors

# CUDA compiler present? (it is not on the default path — set it)
export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH
nvcc --version
# expect: a line ending in a CUDA version, e.g. release 13.2

# Rust toolchain present? (same PATH line as above)
cargo --version
# expect: cargo 1.9x or newer

# Python 3 with the ingest's libraries?
python3 -c "import numpy, PIL, requests; print('ingest deps ok')"
# expect: ingest deps ok   (the watcher drives a Python ingest)

# An interpreter for the console (needs FastAPI + uvicorn)?
python3 -c "import fastapi, uvicorn; print('console deps ok')"
# If this fails for python3, the Thor's usual interpreter is
# ~/ml/.venv/bin/python — try that. If neither works, the
# installer still installs everything and prints the pip
# command that fixes it; the console just won't start until
# then. The watcher does not depend on the console.

# Is the image-understanding rack installed? (running or not)
systemctl cat jev-rack >/dev/null && echo "rack installed"
systemctl is-active jev-rack
# "rack installed" must print. is-active may say "inactive" —
# that is normal; §4 explains. If "rack installed" does NOT
# print, stop: the rack is a separate install, call Casey.

# Enough disk, on the filesystem that will hold the install?
df -h ~
# expect: Avail of 50G or more

# Git present?
git --version
```

## 3. Install

The installer is **dry-run first**: with no flags it changes
nothing and prints every action it *would* take. In dry-run,
failed machine checks print as warnings and the plan still
prints, so you can rehearse the plan anywhere. With `--apply`,
the same checks stop the script. Read the plan before you let
it touch the machine.

```bash
cd slice1/install            # (from the rolling-perception repo)
bash install.sh              # DRY RUN — prints the plan, changes nothing
bash install.sh --apply      # does the layout + build + install
```

What `--apply` does, in order:

1. Creates the folder layout under `~/confluence/`:
   `app/bin/`, `app/core/`, `app/console/`, `config/`,
   `ledger/` (with `streams/`, `items/`, `household/`,
   `attention/` inside), and `media/`.
2. Builds the watcher from the checkout you ran the installer
   from (`cargo build --release -p confluence-watch` — allow
   10–20 minutes on a first build) and installs it as
   `~/confluence/app/bin/confluence-watch`. (The workspace also
   builds a `harbor-watch` experiment binary; the service does
   not use it and the installer does not install it.)
3. Installs the watcher's Python ingest and the bundled test
   fixtures into `~/confluence/app/core/`, and the console
   (`app.py` + `index.html`) into `~/confluence/app/console/`.
4. Writes a starter watcher config at
   `~/confluence/config/watch.conf` — **existing config is
   never overwritten** on a re-run. The camera URL in it is a
   placeholder for your site; §5 is a required step, not an
   optional one.
5. Writes two systemd *user* units — `confluence-watch` and
   `confluence-console` — but does **not** switch either on.

### Switching the services on (a separate, deliberate step)

First do §4 (rack) and §5 (camera URL) — the watcher exits
immediately if the rack is not healthy, and watches nothing
until its config points at a real camera. Then:

```bash
bash install.sh --apply --enable-service
systemctl --user status confluence-watch
systemctl --user status confluence-console
```

`--enable-service` only works together with `--apply`, and the
installer refuses it otherwise. The household page is then at:

```
http://thor.local:8320/
```

> One thing the installer cannot do for you: a user service
> only survives logout if "linger" is on for the user. Check
> with `loginctl show-user $USER -p Linger`. If it says
> `Linger=no`, run `sudo loginctl enable-linger $USER` once.

### Checking the install without a camera (the staged rig)

The checkout ships a self-test sequence (a scene cut, an object
appearing, a slow drift) built from bundled photo fixtures. On
a box with the rack running, the full acceptance — watcher,
ingest, rack and all — is one command from the checkout:

```bash
cd slice1/core && bash acceptance.sh
```

It proves: cut and object publish verdicts, drift stays silent,
and the rack is left exactly as it was found. (The gate/diff
layer alone, with no rack, can be checked anywhere with
`python3 slice1/core/prove_fixtures.py`.)

## 4. The rack (needed for watching at all)

The Thor's image-understanding rack is a separate system
service, and the watcher will not start without it: at startup
the watcher checks the rack's health on
`http://127.0.0.1:8077`. If the rack is down and the config's
`rack_autostart` is `true` (the starter config sets it), the
watcher starts it with `sudo -n systemctl start jev-rack` —
that needs passwordless sudo for that command; if your Thor
doesn't grant it, start the rack by hand before the watcher:

```bash
sudo systemctl start jev-rack
curl -s http://127.0.0.1:8077/cards | head -c 200; echo
# expect: JSON listing the rack's tools.
# The first real picture is slow while the model loads —
# that pause happens once, at first use, and is normal.
```

When the watcher exits, it stops the rack again **only if it
started it** (`stop_rack_on_exit`, also `true` in the starter
config) — a rack you started by hand is left running. Stop it
yourself with `sudo systemctl stop jev-rack`.

## 5. Point the watcher at a camera

The phone does no thinking — it just sends pictures, and the
Thor polls it. Any app that streams the camera over the local
network works. The reference app on Android is **IP Webcam**
(free, by Pavel Khlebovich).

1. Connect the phone to the **same Wi-Fi** as the Thor.
2. Install **IP Webcam**, open it, scroll to the bottom, tap
   **Start server**. The phone screen now shows an address like
   `http://<lan-ip>:8080`. Leave the app running and plug
   the phone into power — streaming drains a battery.
3. Prop the phone where it can see the scene (door, harbour,
   driveway — wherever this install is watching).
4. Put the phone's address into the watcher config. Open
   `~/confluence/config/watch.conf` and change the `--url` in
   the `ingest_cmd` line to the address from the phone's
   screen, keeping the `/shot.jpg` ending:

   ```
   ingest_cmd = python3 /home/<user>/confluence/app/core/ingest/ingest.py --source shot --url http://<lan-ip>:8080/shot.jpg --gate 3.0 --cadence-ms 500
   ```

   (For the app's continuous stream instead of polled stills,
   use `--source mjpeg --url http://<lan-ip>:8080/video`.)
   The name the household sees for this camera is the
   `stream_id` at the top of the same file (`cam1` in the
   starter config) — set it to household words, e.g.
   `stream_id = front-door`, and change `ledger_dir` to match
   (`.../ledger/streams/front-door`).
5. Restart the watcher: `systemctl --user restart
   confluence-watch`. Within a few seconds the camera's light
   should be on and the ledger for the stream
   (`~/confluence/ledger/streams/<stream_id>/state.txt`)
   should show `frames_seen` climbing.

If the watcher exits instead: check its log
(`journalctl --user -u confluence-watch -n 50`) — it names the
cause (rack not healthy, or the ingest failing). Type the
phone's address into a browser on the LAN — you should see the
app's camera page. If the browser can't see it either, the
network is the problem (some guest Wi-Fi modes isolate devices
— move the phone to the main network).

iPhone: use any app that offers an MJPEG stream or JPEG stills
on the local network; the steps are the same from step 3 on.

Note for the customer: phone addresses can change when the
phone rejoins Wi-Fi (see fault 5). A fixed address reservation
in the router, made once, prevents it.

## 6. The library shelf

The console's shelf is a plain media folder:

1. The installer made `~/confluence/media/`. Put the
   household's image and video files there (or in subfolders).
2. That's it. The console re-reads the folder **on every
   request** — new files appear on the shelf at the next page
   load, no restart and no scan step.
3. To shelve a different folder instead, edit the console
   unit (`~/.config/systemd/user/confluence-console.service`):
   change `CONSOLE_MEDIA_DIR` to the folder's full path, then
   `systemctl --user daemon-reload` and
   `systemctl --user restart confluence-console`.

Per-item perception notes on the shelf (titles, "what is in
this picture") are written by a later slice's backfill into
`~/confluence/ledger/items/`; Slice 1 shelves files with their
names only.

## 7. Daily service

### The verbs

```bash
systemctl --user start   confluence-watch      # start watching
systemctl --user stop    confluence-watch      # stop watching
systemctl --user restart confluence-watch      # after config edits
systemctl --user status  confluence-watch      # is it running?
systemctl --user restart confluence-console    # the web page
```

The rack (system service, needs sudo) is started/stopped with
`sudo systemctl start|stop jev-rack` — see §4.

### Reading stream health

There is no separate health page or health URL. Health lives
in two places, both fed by the watcher's own heartbeat files:

- **The console page** (`http://thor.local:8320/`): each stream
  shows its state and heartbeat age; a stream whose heartbeat
  is more than ~90 seconds old shows **AMBER "not reporting"**.
  The same data as JSON is at `http://thor.local:8320/api/state`.
- **The ledger itself**: `~/confluence/ledger/streams/<id>/`
  holds `health.txt` (embed latencies, frame age), `state.txt`
  (counters, spend), `lens.txt` (the stream's learned rhythm)
  and `events.jsonl` (service receipts + published verdicts,
  append-only). The household's "that wasn't a change" taps in
  the console append to
  `~/confluence/ledger/attention/corrections.jsonl`.

Rules of thumb:

- **Heartbeat seconds old** — healthy.
- **Heartbeat minutes old on one stream** — that stream is in
  trouble (fault 1 or 5); the rest of the system is fine.
- **All heartbeats stale** — the watcher itself has stalled
  (fault 2).

**Known defect (found 2026-11-02 by the install proof run,
recorded in INSTALL-PROOF.md):** the console's change *feed*
currently under-reports — the watcher writes its verdict rows
with a `changed_tiles` field the console's feed reader doesn't
pick up, so verdicts that are plainly in `events.jsonl` may
not appear on the page. Stream health, the shelf, and
corrections all work; the ledger text is complete and correct.
Until that mismatch is fixed, judge "what changed" from
`events.jsonl`, not from the page's feed.

### Logs

```bash
journalctl --user -u confluence-watch -f     # live watcher log
journalctl --user -u confluence-console -f   # live console log
cat ~/confluence/ledger/streams/<id>/events.jsonl   # receipts + verdicts
cat ~/confluence/ledger/attention/corrections.jsonl # household corrections
```

### The five faults you will actually meet

**1. One stream is silent, but the box is busy.**
*Symptom:* no new entries for one camera; other streams fine;
Thor clearly working.
*Check:* is the phone app still running and the phone awake?
Then check the stream's `state.txt`: `frames_seen` tells you
the last frame the watcher processed.
*Fix:* restart the app on the phone (Start server again).
Silence from one stream while the sender is dead is the design
working; restarting the sender is the fix.

**2. The feed has gone quiet and every heartbeat is stale.**
*Symptom:* no entries at all; every stream shows AMBER.
*Check:* `systemctl --user status confluence-watch` —
running? `curl -s http://127.0.0.1:8077/cards` on the Thor —
rack answering? A stalled watcher fakes "all quiet", so treat
total quiet as a fault until proven otherwise.
*Fix:* `systemctl --user restart confluence-watch`. If the
rack is not answering, `sudo systemctl restart jev-rack` too.
If heartbeats go stale again within the hour, stop and call
Casey — repeated stalls are a defect, not a routine.

**3. The rack is not loaded / not answering.**
*Symptom:* the watcher exits at startup (or won't stay up)
and its log says the rack is not healthy. There is no
reduced mode: without the rack there are no embeddings and
the watcher refuses to pretend otherwise.
*Check:* `systemctl is-active jev-rack`. If inactive, start
it (§4). If active but `/cards` fails, read its log:
`journalctl -u jev-rack -n 50`.
*Fix:* start/restart as above, then send one real picture
through (wave a hand at the camera) and confirm verdicts
resume. The first picture after a start is slow while the
model loads — wait for it before concluding anything. Model
files failing their integrity check is **not** a field fix —
call Casey.

**4. The disk is filling up.**
*Symptom:* `df -h ~` shrinking week over week.
*Check:* `du -sh ~/confluence/ledger/` and
`du -sh ~/confluence/media/`. The ledger's `events.jsonl`
grows with every verdict and service receipt; the media
folder is the household's own library.
*Fix:* there is **no retention setting in Slice 1** — nothing
ages out automatically, and this guide won't pretend
otherwise. If the ledger is the growth, call Casey: trimming
history is a decision, not a field fix, and `ledger/` is
never edited or deleted by hand. If the media folder is the
growth, that's the customer's library — talk to the customer.

**5. The phone changed its address.**
*Symptom:* a camera stream goes silent after the phone left
and rejoined Wi-Fi (or the router rebooted); the phone app is
running and shows a *different* address than before.
*Check:* compare the address on the phone's screen with the
`--url` in `~/confluence/config/watch.conf`.
*Fix:* edit the `--url` in `watch.conf` to the new address
and `systemctl --user restart confluence-watch`. (Slice 1
does not re-discover cameras by itself — the address in the
config is the whole mechanism.) Permanent cure: set a DHCP
reservation for the phone in the router (router's admin page
→ connected devices → reserve). Show the customer this
setting while you're there; it is the difference between a
one-off fix and a fixed system.

---

*Open source: this guide ships with the code it describes
(SI-Thor/rolling-perception, `slice1/install/`), and the
stranger reading it on the internet gets the same document you
are holding. The names in it — `confluence-watch`,
`confluence-console`, port 8320, the ledger paths — are the
shipped names, verified against the code and a recorded
install run (INSTALL-PROOF.md) on 2026-11-02. Where a surface
is marked "not yet" or "roadmap", the program genuinely does
not do it yet.*
