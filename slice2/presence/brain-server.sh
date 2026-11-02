#!/bin/bash
# Presence brain server — start/stop the standing chat brain.
#
# Winner (BRAIN-BENCH.md): Qwen3-Coder-30B-A3B-Instruct Q4_K_M, the
# file already on the Thor's disk. Fallback: LFM2-1.2B Q8_0 — named,
# never silent: it serves only behind digest v2's disciplines.
#
# HOW IT MUST BE STARTED ON THIS BOX (measured 2026-11-01, the hard
# way): the Thor's memory-admission daemon (thor-admit) treats any
# UNLEASED multi-GB process as a runaway and SIGTERMs it. Three
# launches of this model died that way — a setsid child, a
# setsid+nohup shell launch, and a systemd user service running
# llama-server directly (daemon log: guard.terminated,
# trigger=runaway, 18.5 GB). The only legitimate route is a lease:
#
#   thor-admit serve <Model> --port <n> --peak <size> -- llama-server …
#
# The serve client stays resident and heartbeats the lease, so it is
# run here as a transient systemd user unit (linger is on for this
# user, so it survives SSH logout). First serve of a model needs an
# explicit --peak; thor-admit learns the label's history from the
# run. Stop releases the lease and the daemon stops the server.
#
# Usage:
#   brain-server.sh start [winner|fallback] [port]   (default winner 8310)
#   brain-server.sh stop [port]                      (default 8310)
#   brain-server.sh status [port]
set -u
LLAMA="${LLAMA_SERVER:-$HOME/llama.cpp/build/bin/llama-server}"
ADMIT="${THOR_ADMIT:-$HOME/lm-tools/thor-admit}"
WINNER_MODEL="$HOME/models/Qwen3-Coder-30B-A3B-Instruct-GGUF/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
FALLBACK_MODEL="$HOME/models/LFM2-1.2B/LFM2-1.2B-Q8_0.gguf"

unit_for() { echo "presence-brain-$1"; }

cmd="${1:-status}"
case "$cmd" in
  start)
    kind="${2:-winner}"; port="${3:-8310}"
    case "$kind" in
      winner)   model="$WINNER_MODEL";   name="Qwen3-Coder-30B-A3B"; peak="24G"; alias="confluence-presence-brain" ;;
      fallback) model="$FALLBACK_MODEL"; name="LFM2-1.2B";           peak="4G";  alias="confluence-presence-fallback" ;;
      *) echo "unknown brain kind: $kind (winner|fallback)" >&2; exit 2 ;;
    esac
    unit="$(unit_for "$port")"
    if systemctl --user is-active --quiet "$unit" 2>/dev/null; then
      echo "already running: $unit"; exit 0
    fi
    systemd-run --user --unit="$unit" \
      --description="Confluence presence brain ($kind)" \
      "$ADMIT" serve "$name" --port "$port" --peak "$peak" -- \
      "$LLAMA" -m "$model" --host 127.0.0.1 --port "$port" \
      -ngl 99 --ctx-size 4096 --alias "$alias"
    echo "starting $kind brain as $unit (lease via thor-admit, peak $peak); health: curl http://127.0.0.1:$port/health"
    ;;
  stop)
    port="${2:-8310}"; unit="$(unit_for "$port")"
    systemctl --user stop "$unit" 2>/dev/null \
      && echo "stopped $unit (lease released; daemon stops the server)" \
      || echo "$unit not active"
    ;;
  status)
    port="${2:-8310}"; unit="$(unit_for "$port")"
    systemctl --user is-active "$unit" || true
    curl -s -m 3 "http://127.0.0.1:$port/health" || echo "no answer on :$port"
    echo
    ;;
  *) echo "usage: $0 start [winner|fallback] [port] | stop [port] | status [port]" >&2; exit 2 ;;
esac
