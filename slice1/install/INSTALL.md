# Confluence — Technician's Install & Service Guide

*Slice 1 edition. If a step here disagrees with what the machine
tells you, believe the machine and write down what it said.*

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
   library plus a feed that says what changed, with a picture of
   the part that changed — and otherwise the system stays silent.
5. Everything is open source, everything runs on the home network,
   and no account, subscription or cloud service is involved.

Words used in this guide: the **rack** is a program already on the
Thor that does the heavy image-understanding work (it lives on
port 8077). The **record book** is a folder of plain-text files
under `~/confluence/ledger/` where the system writes down what it
has seen — if a page ever disagrees with the record book, the
record book is right. The **health page** is a web page the system
itself serves that says, per stream, whether it is seeing,
thinking and reporting on time.

---

## 1. Hardware assumptions

- One **NVIDIA Jetson AGX Thor** (aarch64, Ubuntu 24.04), on the
  home LAN, reachable as `thor.local` (currently <thor-lan-ip> —
  the name is the durable thing, the number can drift).
- At least **50 GB free disk** on the Thor (retained evidence
  pictures grow over time; more is better).
- One **Android phone** for the first camera (any recent phone;
  iPhone works too with an equivalent streaming app — see §5).
- The phone and the Thor on the **same Wi-Fi / LAN**.
- You have a login on the Thor and `sudo` on it (needed only to
  start/stop the rack — everything else runs as the normal user).

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

# Is the image-understanding rack installed? (running or not)
systemctl cat jev-rack >/dev/null && echo "rack installed"
systemctl is-active jev-rack
# "rack installed" must print. is-active may say "inactive" —
# that is normal; §4 starts it. If "rack installed" does NOT
# print, stop: the rack is a separate install, call Casey.

# Enough disk?
df -h ~
# expect: Avail of 50G or more

# Git present?
git --version
```

## 3. Install

The installer is **dry-run first**: with no flags it changes
nothing and prints every action it *would* take. Read that list
before you let it touch the machine.

```bash
cd slice1/install            # (from the rolling-perception repo)
bash install.sh              # DRY RUN — prints the plan, changes nothing
bash install.sh --apply      # does the layout + build, nothing more
```

What `--apply` does, in order:

1. Creates the folder layout under `~/confluence/`
   (`app/`, `src/`, `config/`, `ledger/`, `frames/`, `logs/`).
2. Clones the open-source code into `~/confluence/src/`
   (re-running the installer later updates it in place).
3. Builds the programs (Rust, release build — allow 10–20
   minutes on first build).
4. Copies the built programs into `~/confluence/app/bin/`.
5. Writes starter config files in `~/confluence/config/`
   (existing config is never overwritten).
6. Writes a service definition (a systemd *user* unit named
   `confluence`) — but does **not** switch the service on.

### Switching the service on (a separate, deliberate step)

```bash
bash install.sh --apply --enable-service
systemctl --user status confluence
```

`--enable-service` only works together with `--apply`, and the
installer says so if you forget. After enabling, check the health
page from any browser on the LAN [interface]:

```
http://thor.local:8210/health
```

You should see one line per stream with a recent heartbeat time.
The household page itself is at `http://thor.local:8210/`
[interface].

> One thing the installer cannot do for you: a user service only
> survives logout if "linger" is on for the user. Check with
> `loginctl show-user $USER -p Linger`. If it says `Linger=no`,
> run `sudo loginctl enable-linger $USER` once.

## 4. Start the rack (needed for full-strength watching)

The Thor's image-understanding rack is a separate system service.
The platform health-checks it and reports honestly when it is
down (watching continues in a reduced, clearly-labelled mode),
but the 48-hour acceptance run needs it up:

```bash
sudo systemctl start jev-rack
curl -s http://127.0.0.1:8077/cards | head -c 200; echo
# expect: JSON listing the rack's tools.
# The first real picture takes ~12 s while the model loads —
# that pause happens once, at first use, and is normal.
```

Stop it the same way when a service window calls for it:
`sudo systemctl stop jev-rack`.

## 5. Add a phone as a camera

The phone does no thinking — it just sends pictures. Any app that
streams the camera over the local network works. The reference
app on Android is **IP Webcam** (free, by Pavel Khlebovich).

1. Connect the phone to the **same Wi-Fi** as the Thor.
2. Install **IP Webcam**, open it, scroll to the bottom, tap
   **Start server**. The phone screen now shows an address like
   `http://<lan-ip>:8080`. Leave the app running and plug
   the phone into power — streaming drains a battery.
3. Prop the phone where it can see the scene (door, harbour,
   driveway — wherever this install is watching).
4. Wait a minute, then open the console's camera list
   [interface]. The platform sweeps the LAN for streaming phones
   and the new camera appears by the address it found.
   If it does not appear: confirm the phone and Thor are on the
   same network, confirm the app still says the server is
   running, and type the address from the phone's screen into a
   browser on the LAN — you should see the app's camera page.
   If the browser can't see it either, the network is the
   problem (some guest Wi-Fi modes isolate devices — move the
   phone to the main network).
5. Name the camera in the console (e.g. "Front door") so the
   change feed speaks in household words.

iPhone: use any app that offers an MJPEG or RTSP stream on the
local network; the steps are the same from step 3 on.

Note for the customer: phone addresses can change when the phone
rejoins Wi-Fi (see fault 5). A fixed address reservation in the
router, made once, prevents it.

## 6. Add the first library folder

1. Put the household's video files in a folder the Thor can
   read — for a first install, use the folder the installer
   made: `~/confluence/media/` — or pick an existing folder.
2. Tell the platform about it: add the folder's full path, one
   per line, to `~/confluence/config/library.txt` [interface].
3. Restart the service so it picks the folder up:

   ```bash
   systemctl --user restart confluence
   ```

4. Open the household page. The shelf lists what it found
   (names and details; playback arrives in a later slice).
   New files dropped into a listed folder are picked up on the
   next scan [interface].

## 7. Daily service

### The three verbs

```bash
systemctl --user start confluence      # start
systemctl --user stop confluence       # stop
systemctl --user restart confluence    # restart (after config edits)
systemctl --user status confluence     # is it running?
```

The rack (system service, needs sudo) is started/stopped with
`sudo systemctl start|stop jev-rack` — see §4.

### Reading the health page

Open `http://thor.local:8210/health` [interface]. Per stream it
shows: last picture seen, last verdict written, and the age of
the last heartbeat. The rules of thumb:

- **Heartbeat seconds old** — healthy.
- **Heartbeat minutes old on one stream** — that stream is in
  trouble (fault 1 or 5), the rest of the system is fine.
- **All heartbeats stale** — the watcher itself has stalled
  (fault 2).
- **A line saying the rack is down** — reduced-mode watching;
  start the rack (§4) if the customer wants full strength.

### Logs

```bash
journalctl --user -u confluence -f        # live service log
ls ~/confluence/logs/                     # [interface] stage receipts
tail ~/confluence/ledger/attention/feed.jsonl   # the change feed itself, as text
```

### The five faults you will actually meet

**1. One stream is silent, but the box is busy.**
*Symptom:* no new entries for one camera; other streams fine;
Thor clearly working.
*Check:* is the phone app still running and the phone awake?
Then check the health page: "last picture seen" for that stream
tells you when it stopped.
*Fix:* restart the app on the phone (Start server again). The
platform deliberately drops a stuck stream rather than stalling
the others — silence from one stream is the design working;
restarting the sender is the fix.

**2. The feed has gone quiet and every heartbeat is stale.**
*Symptom:* no entries at all, health page shows old heartbeats
across the board.
*Check:* `systemctl --user status confluence` — running?
`curl -s http://127.0.0.1:8077/cards` on the Thor — rack
answering? A stalled watcher fakes "all quiet", so treat total
quiet as a fault until proven otherwise.
*Fix:* `systemctl --user restart confluence`. If the rack is
not answering, `sudo systemctl restart jev-rack` too. If
heartbeats go stale again within the hour, stop and call Casey
— repeated stalls are a defect, not a routine.

**3. The rack is not loaded / not answering.**
*Symptom:* health page flags the rack down; verdicts continue
in reduced mode (labelled as such — quick look only, no
image-understanding).
*Check:* `systemctl is-active jev-rack`. If inactive, start
it (§4). If active but `/cards` fails, read its log:
`journalctl -u jev-rack -n 50`.
*Fix:* start/restart as above, then send one real picture
through (wave a hand at the camera) and confirm full-strength
verdicts resume. First picture after a start takes ~12 s while
the model loads — wait for it before concluding anything.
Model files failing their integrity check is **not** a
field fix — call Casey.

**4. The disk is filling up.**
*Symptom:* `df -h ~` shrinking week over week; health page may
warn.
*Check:* `du -sh ~/confluence/frames/` — retained evidence
pictures are the usual growth. `du -sh ~/confluence/ledger/`
should stay small; if it hasn't, something is wrong — call
Casey.
*Fix:* evidence pictures are kept so the household can review
"what changed"; the retention window is set in
`~/confluence/config/` [interface]. Shorten it if the customer
prefers space over history, restart the service, and confirm
`df -h` recovers as old pictures age out. Never delete from
`ledger/` by hand.

**5. The phone changed its address.**
*Symptom:* a camera stream goes silent after the phone left
and rejoined Wi-Fi (or the router rebooted); the phone app is
running and shows a *different* address than before.
*Check:* compare the address on the phone's screen with the
address in the console's camera list.
*Fix:* wait for the platform's next LAN sweep — it re-finds
the phone by its stream, not just its old address [interface].
If it hasn't reappeared in 10 minutes, restart the service.
Permanent cure: set a DHCP reservation for the phone in the
router (router's admin page → connected devices → reserve).
Show the customer this setting while you're there; it is the
difference between a one-off fix and a fixed system.

---

*Open source: this guide ships with the code it describes
(SI-Thor/rolling-perception, `slice1/install/`), and the
stranger reading it on the internet gets the same document you
are holding. Anything marked [interface] names a surface the
core/console programs expose; if the shipped build names it
differently, the build's name wins and this guide gets a patch.*
