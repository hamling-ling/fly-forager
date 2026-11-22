#!/usr/bin/env bash
# Stream flyforager_q logs to this terminal and to a file in logs/.
#
# Ctrl-C stops the stream. The file stays. Pass another destination
# when the board is not uno-q-1:
#
#   scripts/logs_flyforager_q.sh
#   scripts/logs_flyforager_q.sh arduino@other.local
#
# Run from anywhere. The default matches scripts/deploy_flyforager_q.sh.
# Adapted from fly-car's logs_flycar_q.sh, minus the JPEG pulling
# (this app writes no frames).

set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
host=${1:-arduino@uno-q-1.local}
remote=ArduinoApps/flyforager_q
stamp=$(date +%Y%m%d-%H%M%S)
out=$root/logs/flyforager_q-$stamp.log
mkdir -p "$root/logs"

echo "follow ${host}:~/${remote}"
echo "save ${out}"
echo "Ctrl-C で切る。ログが残る。"

# ServerAlive: a stalled Wi-Fi link otherwise hangs ssh silently
# instead of failing, which looks exactly like a stalled log.
ssh=(ssh -o BatchMode=yes -o ConnectTimeout=10
     -o ServerAliveInterval=5 -o ServerAliveCountMax=3)
"${ssh[@]}" "$host" "arduino-app-cli app logs ~/${remote} --follow --tail 30" \
  | tee "$out"
