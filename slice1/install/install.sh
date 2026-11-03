#!/usr/bin/env bash
# Confluence — Slice 1 installer for the Jetson AGX Thor.
#
# DRY-RUN FIRST: with no flags this script changes nothing. It
# checks the machine, then prints every action it WOULD take.
# In dry-run, failed machine checks are printed as warnings and
# the plan still prints, so the plan can be rehearsed anywhere;
# with --apply the same checks are fatal (except the documented
# rehearsal bypass below).
#
#   bash install.sh                        dry run (the default)
#   bash install.sh --apply                create layout + build + install
#   bash install.sh --apply --enable-service
#                                          also switch the services on
#
# The services are never enabled without the explicit
# --enable-service flag, and that flag is refused without
# --apply in the same run. Re-running the script is safe:
# folders are created only if missing, installed files are
# refreshed, and existing config files are never overwritten.
#
# What gets installed (names verified against the code,
# 2026-11-02 — see INSTALL-PROOF.md for a full run):
#   app/bin/confluence-watch   the watcher (the workspace crate
#                              slice1/core; its only CLI is
#                              `confluence-watch --config <file>`)
#   app/core/                  the watcher's Python ingest
#                              (ingest/ingest.py) + bundled
#                              fixtures, laid out exactly as the
#                              ingest resolves them
#   app/console/               the household page (console/app.py
#                              + index.html; FastAPI, port 8320)
#   config/watch.conf          starter watcher config — the
#                              camera URL in it is site-specific
#                              and MUST be edited (INSTALL.md §5)
#   two systemd user units:    confluence-watch.service,
#                              confluence-console.service
#
# Environment knobs (all optional):
#   CONFLUENCE_HOME            install root (default ~/confluence)
#   CONFLUENCE_SRC_DIR         repo checkout to build from
#                              (default: the checkout this script
#                              ships in, else $ROOT/src clone)
#   CONFLUENCE_REPO_URL        clone URL when no checkout is at
#                              hand (the repo is private until
#                              graduation; a fresh Thor needs a
#                              checkout placed by hand — the
#                              installer says so when it matters)
#   CONFLUENCE_UNIT_DIR        where units are written
#                              (default ~/.config/systemd/user;
#                              point it into a scratch tree for a
#                              rehearsal and systemctl steps are
#                              skipped, with a printed note)
#   CONFLUENCE_PYTHON          interpreter for the console unit
#                              (default: first of ~/ml/.venv,
#                              python3 that can import fastapi +
#                              uvicorn; if none can, the unit is
#                              still written and the exact pip
#                              command is printed — the console
#                              will not start until then)
#   CONFLUENCE_ALLOW_UNTESTED_MACHINE=1
#                              rehearsal bypass: downgrades the
#                              Thor-only machine checks (arch,
#                              GPU, CUDA, rack service present)
#                              to loud warnings during --apply.
#                              For CI/rehearsal on other hardware;
#                              never for a real Thor install.

set -euo pipefail

# ----------------------------------------------------------------
# Settings

ROOT="${CONFLUENCE_HOME:-$HOME/confluence}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="${CONFLUENCE_REPO_URL:-https://github.com/SI-Thor/rolling-perception.git}"
BIN_DIR="$ROOT/app/bin"
CORE_DIR="$ROOT/app/core"
CONSOLE_DIR="$ROOT/app/console"
UNIT_DIR="${CONFLUENCE_UNIT_DIR:-$HOME/.config/systemd/user}"
WATCH_UNIT="$UNIT_DIR/confluence-watch.service"
CONSOLE_UNIT="$UNIT_DIR/confluence-console.service"
MIN_FREE_GB=50
BYPASS=0
[ "${CONFLUENCE_ALLOW_UNTESTED_MACHINE:-0}" = "1" ] && BYPASS=1

# Where the source comes from: an explicit override, else the
# checkout this script ships in (slice1/install/../../), else a
# clone under the install root.
if [ -n "${CONFLUENCE_SRC_DIR:-}" ]; then
    SRC_DIR="$CONFLUENCE_SRC_DIR"
    SRC_MODE="explicit"
elif [ -f "$SCRIPT_DIR/../../Cargo.toml" ]; then
    SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
    SRC_MODE="checkout"
else
    SRC_DIR="$ROOT/src/rolling-perception"
    SRC_MODE="clone"
fi

APPLY=0
ENABLE=0

# The Thor keeps its toolchains off the default path.
export PATH="$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH"

# ----------------------------------------------------------------
# Small helpers

die() {
    printf 'STOP: %s\n' "$*" >&2
    exit 1
}

note() {
    printf '%s\n' "$*"
}

would() {
    printf '  WOULD: %s\n' "$*"
}

# check <fatal-if-apply:0/1> <description> <command...>
# In dry-run everything is a warning; in apply, a check marked
# fatal stops the script. The rehearsal bypass un-fatalises the
# Thor-only machine checks (they call check with FATAL_MACHINE).
FATAL_MACHINE=1
[ "$BYPASS" -eq 1 ] && FATAL_MACHINE=0
check() {
    local fatal="$1" desc="$2"
    shift 2
    if "$@" >/dev/null 2>&1; then
        note "  ok: $desc"
        return 0
    fi
    if [ "$APPLY" -eq 1 ] && [ "$fatal" -eq 1 ]; then
        die "$desc — check failed; stopping (see INSTALL.md section 2)."
    fi
    note "  WARN: $desc — check failed."
    if [ "$APPLY" -eq 1 ]; then
        note "        (continuing: rehearsal bypass or dry-run semantics)"
    else
        note "        (dry run: the plan below still prints; --apply would stop here)"
    fi
    return 0
}

# run <description> <command...>: print in dry-run, execute in apply.
run() {
    local desc="$1"
    shift
    if [ "$APPLY" -eq 1 ]; then
        printf '  DO: %s\n' "$desc"
        "$@"
    else
        would "$desc"
    fi
}

# write_file <path>: reads content from stdin. In dry-run, prints
# the intention only; in apply, writes only if the file is absent
# unless FORCE_WRITE=1 is set by the caller.
FORCE_WRITE=0
write_file() {
    local path="$1"
    local content
    content="$(cat)"
    if [ "$APPLY" -eq 0 ]; then
        would "write $path ($(printf '%s' "$content" | wc -l) lines)"
        return 0
    fi
    if [ -e "$path" ] && [ "$FORCE_WRITE" -ne 1 ]; then
        printf '  KEEP: %s already exists, not overwriting\n' "$path"
        return 0
    fi
    printf '  DO: write %s\n' "$path"
    mkdir -p "$(dirname "$path")"
    printf '%s\n' "$content" >"$path"
}

# ----------------------------------------------------------------
# Arguments

for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        --enable-service) ENABLE=1 ;;
        -h | --help)
            sed -n '2,16p' "$0"
            exit 0
            ;;
        *) die "unknown argument: $arg (try --help)" ;;
    esac
done

if [ "$ENABLE" -eq 1 ] && [ "$APPLY" -eq 0 ]; then
    die "--enable-service needs --apply in the same run: enabling is a deliberate step taken on a completed install."
fi

if [ "$APPLY" -eq 1 ]; then
    note "Confluence installer — APPLY mode. Changes will be made."
else
    note "Confluence installer — DRY RUN. Nothing will be changed."
fi
note "Install root: $ROOT"
note "Source: $SRC_DIR ($SRC_MODE)"
[ "$BYPASS" -eq 1 ] && note "REHEARSAL BYPASS is on (CONFLUENCE_ALLOW_UNTESTED_MACHINE=1): Thor-only machine checks are warnings, not stops."
note ""

# ----------------------------------------------------------------
# Prerequisite checks. In dry-run a miss is a warning (the plan
# still prints); in apply a miss stops the script, except under
# the rehearsal bypass.

note "Checking prerequisites..."

check $FATAL_MACHINE "Jetson AGX Thor (aarch64); this machine reports $(uname -m)" \
    test "$(uname -m)" = "aarch64"

if command -v nvidia-smi >/dev/null 2>&1; then
    check $FATAL_MACHINE "GPU answers (nvidia-smi)" nvidia-smi
else
    check $FATAL_MACHINE "GPU answers (nvidia-smi) — nvidia-smi not on PATH" false
fi

check $FATAL_MACHINE "CUDA compiler (nvcc)" command -v nvcc
if command -v nvcc >/dev/null 2>&1; then
    note "      ($(nvcc --version | grep -o 'release [0-9.]*' | head -n 1))"
fi

check 1 "Rust toolchain (cargo)" command -v cargo
if command -v cargo >/dev/null 2>&1; then
    note "      (cargo $(cargo --version | awk '{print $2}'))"
fi

check 1 "git" command -v git
check 1 "python3 (the ingest is a Python program)" command -v python3
check 1 "python3 can import numpy, Pillow and requests (ingest dependencies)" \
    python3 -c "import numpy, PIL, requests"

if systemctl cat jev-rack >/dev/null 2>&1; then
    rack_state="$(systemctl is-active jev-rack 2>/dev/null || true)"
    note "  ok: image-understanding rack (jev-rack) is installed; currently: ${rack_state:-unknown}"
    note "      (The watcher starts it itself when it finds it down —"
    note "       that needs passwordless sudo for 'systemctl start"
    note "       jev-rack', or start it by hand first: INSTALL.md §4.)"
else
    check $FATAL_MACHINE "image-understanding rack (jev-rack service) is installed — it is a separate install; if this fails on a real Thor, stop and call Casey" \
        systemctl cat jev-rack
fi

# Disk is measured on the filesystem that will hold the install
# root, not on $HOME's.
root_probe="$ROOT"
while [ ! -e "$root_probe" ] && [ "$root_probe" != "/" ]; do
    root_probe="$(dirname "$root_probe")"
done
free_kb="$(df -Pk "$root_probe" | awk 'NR==2 {print $4}')"
free_gb=$((free_kb / 1024 / 1024))
if [ "$free_gb" -ge "$MIN_FREE_GB" ]; then
    note "  ok: disk under $root_probe (${free_gb} GB free, minimum ${MIN_FREE_GB} GB)"
elif [ "$APPLY" -eq 1 ] && [ "$BYPASS" -eq 0 ]; then
    die "only ${free_gb} GB free under $root_probe; Confluence needs at least ${MIN_FREE_GB} GB (the ledger and media library grow over time)."
else
    note "  WARN: only ${free_gb} GB free under $root_probe (minimum ${MIN_FREE_GB} GB)."
fi

# Console interpreter: the console needs fastapi + uvicorn. The
# reference Thor serves it from ~/ml/.venv; accept any interpreter
# that can import both, and say plainly when none can.
CONSOLE_PY=""
for cand in "${CONFLUENCE_PYTHON:-}" "$HOME/ml/.venv/bin/python" "$(command -v python3 || true)"; do
    [ -n "$cand" ] && [ -x "$cand" ] || continue
    if "$cand" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
        CONSOLE_PY="$cand"
        break
    fi
done
if [ -n "$CONSOLE_PY" ]; then
    note "  ok: console interpreter ($CONSOLE_PY imports fastapi + uvicorn)"
else
    note "  WARN: no interpreter found that imports fastapi + uvicorn."
    note "        The console unit will be written for python3 and will NOT"
    note "        start until its dependencies are installed, e.g.:"
    note "          python3 -m pip install fastapi uvicorn"
    note "        (or set CONFLUENCE_PYTHON to an interpreter that has them)."
    CONSOLE_PY="python3"
fi

note ""

# ----------------------------------------------------------------
# The plan / the work

note "Actions:"

for dir in \
    "$ROOT" \
    "$ROOT/app" \
    "$BIN_DIR" \
    "$CORE_DIR" \
    "$CONSOLE_DIR" \
    "$ROOT/config" \
    "$ROOT/ledger/streams" \
    "$ROOT/ledger/items" \
    "$ROOT/ledger/household" \
    "$ROOT/ledger/attention" \
    "$ROOT/media" \
    "$UNIT_DIR"; do
    run "create folder $dir" mkdir -p "$dir"
done

case "$SRC_MODE" in
    clone)
        if [ -d "$SRC_DIR/.git" ]; then
            run "update code checkout in $SRC_DIR" git -C "$SRC_DIR" pull --ff-only
        else
            run "clone $REPO_URL into $SRC_DIR" git clone "$REPO_URL" "$SRC_DIR"
            if [ "$APPLY" -eq 1 ]; then
                note "      NOTE: the repo is private until graduation — if the"
                note "      clone fails with an auth error, place a checkout by"
                note "      hand and re-run with CONFLUENCE_SRC_DIR=<checkout>."
            fi
        fi
        ;;
    *)
        note "  ok: building from the checkout at $SRC_DIR (no clone needed)"
        ;;
esac

run "build the watcher (cargo build --release -p confluence-watch; first build can take 10-20 minutes)" \
    cargo build --release -p confluence-watch --manifest-path "$SRC_DIR/Cargo.toml"

if [ "$APPLY" -eq 1 ]; then
    built="$SRC_DIR/target/release/confluence-watch"
    if [ -x "$built" ]; then
        run "install program confluence-watch into $BIN_DIR" cp "$built" "$BIN_DIR/confluence-watch"
    else
        die "expected build product $built not found — the build interface has changed; stop and report this line."
    fi
else
    would "install program confluence-watch into $BIN_DIR"
fi
note "      (the workspace also builds a harbor-watch experiment binary;"
note "       the service does not use it and the installer does not install it)"

run "install the ingest (ingest.py) into $CORE_DIR/ingest" \
    cp -r "$SRC_DIR/slice1/core/ingest" "$CORE_DIR/"
run "install the bundled fixtures into $CORE_DIR/fixtures" \
    cp -r "$SRC_DIR/slice1/core/fixtures" "$CORE_DIR/"
# A checkout that has ever run the ingest carries __pycache__
# beside it; bytecode from someone else's machine does not ship.
if [ "$APPLY" -eq 1 ]; then
    run "remove any __pycache__ copied from the checkout" \
        find "$CORE_DIR" -name __pycache__ -type d -exec rm -rf {} +
else
    would "remove any __pycache__ copied from the checkout"
fi
run "install the console (app.py + index.html) into $CONSOLE_DIR" \
    cp "$SRC_DIR/slice1/console/app.py" "$SRC_DIR/slice1/console/index.html" "$CONSOLE_DIR/"

# Starter watcher config. Never overwritten once present: the
# camera URL in it is the household's own.
write_file "$ROOT/config/watch.conf" <<EOF
# Confluence watcher — starter config (key = value; # comments).
# EDIT the camera URL in ingest_cmd before enabling the service:
# it must point at YOUR camera (INSTALL.md section 5). Everything
# else in this file works as written.
stream_id = cam1
ledger_dir = $ROOT/ledger/streams/cam1
ingest_cmd = python3 $CORE_DIR/ingest/ingest.py --source shot --url http://127.0.0.1:8091/shot.jpg --gate 3.0 --cadence-ms 500
rack_url = http://127.0.0.1:8077
rack_autostart = true
stop_rack_on_exit = true
threshold = 0.25
alpha = 0.1
focus_k = 4
soak = false
# Perception budget (SPEC 2.2): embed-seconds per rolling hour.
budget_embed_s_per_hour = 300
# Tenancy (SPEC 2.3): the yield ladder is on — if foreign work
# takes the GPU, the watcher steps down (budgets halve, then
# reflex-only) and receipts every step in the ledger.
tenancy = true
EOF

FORCE_WRITE=1 write_file "$WATCH_UNIT" <<EOF
[Unit]
Description=Confluence — stream watcher (confluence-watch)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$CORE_DIR
ExecStart=$BIN_DIR/confluence-watch --config $ROOT/config/watch.conf
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

FORCE_WRITE=1 write_file "$CONSOLE_UNIT" <<EOF
[Unit]
Description=Confluence — household console (shelf + change feed)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$CONSOLE_DIR
Environment=CONSOLE_LEDGER_DIR=$ROOT/ledger
Environment=CONSOLE_MEDIA_DIR=$ROOT/media
Environment=CONSOLE_PORT=8320
ExecStart=$CONSOLE_PY $CONSOLE_DIR/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
FORCE_WRITE=0

if [ "$UNIT_DIR" = "$HOME/.config/systemd/user" ]; then
    run "refresh the user service manager" systemctl --user daemon-reload
else
    note "  SKIP: systemctl --user daemon-reload (units were written to a"
    note "        non-default CONFLUENCE_UNIT_DIR=$UNIT_DIR — rehearsal layout;"
    note "        a real install writes to ~/.config/systemd/user and reloads)"
fi

if [ "$ENABLE" -eq 1 ]; then
    run "enable and start the confluence-watch service" \
        systemctl --user enable --now confluence-watch.service
    run "enable and start the confluence-console service" \
        systemctl --user enable --now confluence-console.service
else
    would "enable and start confluence-watch + confluence-console (skipped: pass --enable-service with --apply when ready)"
fi

note ""
if [ "$APPLY" -eq 1 ]; then
    note "Apply pass complete."
else
    note "Dry run complete — nothing was changed."
fi
note "Next steps (INSTALL.md):"
note "  1. edit the camera URL: \$EDITOR $ROOT/config/watch.conf   (§5)"
note "  2. sudo systemctl start jev-rack        # the rack (§4)"
if [ "$ENABLE" -eq 0 ]; then
    note "  3. bash install.sh --apply --enable-service   # when ready"
fi
note "  4. open http://thor.local:8320/         # the household page"
note "     (stream health is on that page — there is no separate"
note "      health URL; per-stream heartbeat ages are in"
note "      http://thor.local:8320/api/state)"
