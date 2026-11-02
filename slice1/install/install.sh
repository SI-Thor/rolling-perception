#!/usr/bin/env bash
# Confluence — Slice 1 installer for the Jetson AGX Thor.
#
# DRY-RUN FIRST: with no flags this script changes nothing. It
# checks the machine, then prints every action it WOULD take.
#
#   bash install.sh                        dry run (the default)
#   bash install.sh --apply                create layout + build
#   bash install.sh --apply --enable-service
#                                          also switch the service on
#
# The service is never enabled without the explicit
# --enable-service flag. Re-running the script is safe: folders
# are created only if missing, the code checkout is updated in
# place, and existing config files are never overwritten.
#
# [interface] marks places that depend on the core/console build
# (program names, the service command line). If the shipped
# build differs, adjust the marked lines — nowhere else.

set -euo pipefail

# ----------------------------------------------------------------
# Settings

ROOT="${CONFLUENCE_HOME:-$HOME/confluence}"
REPO_URL="${CONFLUENCE_REPO_URL:-https://github.com/SI-Thor/rolling-perception.git}"
SRC_DIR="$ROOT/src/rolling-perception"
BIN_DIR="$ROOT/app/bin"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_FILE="$UNIT_DIR/confluence.service"
MIN_FREE_GB=50

# Programs the build is expected to produce. [interface]
PROGRAMS="confluence harbor-watch"

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
note ""

# ----------------------------------------------------------------
# Prerequisite checks — run in every mode; a miss stops the script.

note "Checking prerequisites..."

[ "$(uname -m)" = "aarch64" ] ||
    die "this installer is for the Jetson AGX Thor (aarch64); this machine reports $(uname -m)."

command -v nvidia-smi >/dev/null 2>&1 ||
    die "nvidia-smi not found — the NVIDIA driver is not installed or not on PATH."
nvidia-smi >/dev/null 2>&1 ||
    die "nvidia-smi ran but the GPU did not answer — check the driver before installing."
note "  ok: GPU answers (nvidia-smi)"

command -v nvcc >/dev/null 2>&1 ||
    die "nvcc not found — install the CUDA toolkit (expected under /usr/local/cuda/bin)."
note "  ok: CUDA compiler ($(nvcc --version | grep -o 'release [0-9.]*' | head -n 1))"

command -v cargo >/dev/null 2>&1 ||
    die "cargo not found — install Rust (expected under ~/.cargo/bin)."
note "  ok: Rust ($(cargo --version | awk '{print $2}'))"

command -v git >/dev/null 2>&1 ||
    die "git not found — install git before continuing."
note "  ok: git"

command -v systemctl >/dev/null 2>&1 ||
    die "systemctl not found — this installer expects a systemd system."

if systemctl cat jev-rack >/dev/null 2>&1; then
    rack_state="$(systemctl is-active jev-rack 2>/dev/null || true)"
    note "  ok: image-understanding rack (jev-rack) is installed; currently: ${rack_state:-unknown}"
    note "      (Slice 1's full-strength watching needs it started — see INSTALL.md section 4."
    note "       The installer deliberately never starts system services.)"
else
    die "the jev-rack service is not installed on this Thor — it is a separate install; stop here and call Casey."
fi

free_kb="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
free_gb=$((free_kb / 1024 / 1024))
[ "$free_gb" -ge "$MIN_FREE_GB" ] ||
    die "only ${free_gb} GB free on the home filesystem; Confluence needs at least ${MIN_FREE_GB} GB (retained evidence pictures grow over time)."
note "  ok: disk (${free_gb} GB free, minimum ${MIN_FREE_GB} GB)"

note ""

# ----------------------------------------------------------------
# The plan / the work

note "Actions:"

for dir in \
    "$ROOT" \
    "$ROOT/app" \
    "$BIN_DIR" \
    "$ROOT/src" \
    "$ROOT/config" \
    "$ROOT/ledger/streams" \
    "$ROOT/ledger/items" \
    "$ROOT/ledger/household" \
    "$ROOT/ledger/attention" \
    "$ROOT/frames" \
    "$ROOT/logs" \
    "$ROOT/media" \
    "$UNIT_DIR"; do
    run "create folder $dir" mkdir -p "$dir"
done

if [ -d "$SRC_DIR/.git" ]; then
    run "update code checkout in $SRC_DIR" git -C "$SRC_DIR" pull --ff-only
else
    run "clone $REPO_URL into $SRC_DIR" git clone "$REPO_URL" "$SRC_DIR"
fi

run "build the programs (Rust release build; first build can take 10-20 minutes)" \
    cargo build --release --manifest-path "$SRC_DIR/Cargo.toml"

if [ "$APPLY" -eq 1 ]; then
    for prog in $PROGRAMS; do
        built="$SRC_DIR/target/release/$prog"
        if [ -x "$built" ]; then
            run "install program $prog into $BIN_DIR" cp "$built" "$BIN_DIR/$prog"
        else
            printf '  WARN: expected build product %s not found — core build interface may have changed; see [interface] in this script.\n' "$built"
        fi
    done
else
    for prog in $PROGRAMS; do
        would "install program $prog into $BIN_DIR"
    done
fi

write_file "$ROOT/config/library.txt" <<EOF
# Library folders — one full path per line. Lines starting with
# # are ignored. The installer created the starter folder below;
# add the household's real folders under it.
$ROOT/media
EOF

write_file "$ROOT/config/streams.txt" <<'EOF'
# Streams — one per line, added by the console or by hand.
# Cameras found on the LAN (streaming phones) are recorded here
# by the platform; this file starts empty on purpose.
EOF

FORCE_WRITE=1 write_file "$UNIT_FILE" <<EOF
[Unit]
Description=Confluence — home stream watcher (Thor)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$BIN_DIR/confluence serve --config $ROOT/config
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
FORCE_WRITE=0

run "refresh the user service manager" systemctl --user daemon-reload

if [ "$ENABLE" -eq 1 ]; then
    run "enable and start the confluence service" \
        systemctl --user enable --now confluence.service
else
    would "enable and start the confluence service (skipped: pass --enable-service with --apply when ready)"
fi

note ""
if [ "$APPLY" -eq 1 ]; then
    note "Apply pass complete."
else
    note "Dry run complete — nothing was changed."
fi
note "Next steps (INSTALL.md):"
note "  1. sudo systemctl start jev-rack        # the rack, section 4"
if [ "$ENABLE" -eq 0 ]; then
    note "  2. bash install.sh --apply --enable-service   # when ready"
fi
note "  3. open http://thor.local:8210/health   # [interface] health page"
note "  4. add a phone camera and a library folder (sections 5 and 6)"
