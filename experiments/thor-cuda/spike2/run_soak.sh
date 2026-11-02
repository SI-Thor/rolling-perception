#!/bin/bash
# Bounded 10-minute soak wrapper (runs ON the Thor, in ~/rolling-perception-play/spike2)
cd ~/rolling-perception-play/spike2 || exit 1
{
  echo "=== BEFORE $(date -Is) ==="
  uptime
  nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used --format=csv,noheader
  echo "=== SOAK START $(date -Is) ==="
} > soak_summary.log

./spike2_soak 600 > soak_run.log 2>&1 &
SOAK_PID=$!
tegrastats --interval 10000 > soak_telemetry.log 2>&1 &
TEG_PID=$!
wait $SOAK_PID
SOAK_RC=$?
kill $TEG_PID 2>/dev/null
sleep 5
{
  echo "=== AFTER $(date -Is) soak_rc=$SOAK_RC ==="
  uptime
  nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used --format=csv,noheader
  echo "--- pgrep check (bracket trick, must print GONE) ---"
  if pgrep -f 'spike2_soa[k]' > /dev/null; then echo "STILL-RUNNING (BAD)"; pgrep -af 'spike2_soa[k]'; else echo "GONE"; fi
  echo "--- soak_run.log ---"
  cat soak_run.log
  echo "--- tegrastats lines: $(wc -l < soak_telemetry.log) ---"
  head -2 soak_telemetry.log
  tail -2 soak_telemetry.log
} >> soak_summary.log
cat soak_summary.log
