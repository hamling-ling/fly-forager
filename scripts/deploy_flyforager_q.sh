#!/usr/bin/env bash
# Stop flyforager_q on the Uno Q, copy this tree, and start it again.
#
# Adapted from fly-car's deploy_flycar_q.sh. The app is self-contained
# under src/flyforager_q (Python, sketch, and the C++ kernel with its
# circuit tables), so a single copy deploys everything. The kernel
# binary is compiled on the board by the app itself on first start.
#
# app.yaml and sketch/ are hashed. When that hash matches
# ~/ArduinoApps/flyforager_q/.sketch-hash the sketch cache stays, and
# start reuses the build and the venv. A different hash, a leftover
# .sketch-hash.pending from a wipe whose start did not finish, or
# --rebuild removes .cache so the next start compiles. The stamp is
# written only after app start succeeds. A missing stamp keeps the
# cache: the last deploy already compiled this sketch. app start
# refuses while a container for this app is still running, and app
# stop can report success after resetting the microcontroller with
# that container left up. Remove it before start.
#
#   scripts/deploy_flyforager_q.sh
#   scripts/deploy_flyforager_q.sh --rebuild
#   scripts/deploy_flyforager_q.sh arduino@other.local
#   scripts/deploy_flyforager_q.sh --rebuild arduino@other.local
#
# Run from anywhere.

set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
rebuild=0
host=arduino@uno-q-1.local
for arg in "$@"; do
  case "$arg" in
    --rebuild) rebuild=1 ;;
    -*)
      echo "unknown option: ${arg}" >&2
      exit 2
      ;;
    *) host=$arg ;;
  esac
done
remote=ArduinoApps/flyforager_q
ssh=(ssh -o BatchMode=yes -o ConnectTimeout=10)

kernel_dir="$root/src/flyforager_q/python/kernel"
for bin in gaba.bin indptr.bin post.bin sugar.bin w_base.bin; do
  if [[ ! -f "$kernel_dir/$bin" ]]; then
    echo "kernel data missing: $bin (run scripts/download_kernel_data.sh first)" >&2
    exit 1
  fi
done

sketch_hash=$(
  tar -C "$root/src/flyforager_q" \
    --sort=name \
    --mtime='@0' \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    -cf - app.yaml sketch \
    | sha256sum \
    | awk '{print $1}'
)
if [[ ! "$sketch_hash" =~ ^[0-9a-f]{64}$ ]]; then
  echo "sketch hash failed" >&2
  exit 1
fi

echo "stop ${host}:~/${remote}"
"${ssh[@]}" "$host" "arduino-app-cli app stop ~/${remote}" || true

echo "copy src/flyforager_q"
tar -C "$root/src/flyforager_q" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.cache' \
  --exclude='python/kernel/sim' \
  -cf - . \
  | "${ssh[@]}" "$host" "mkdir -p ~/${remote} && tar -C ~/${remote} -xf -"

"${ssh[@]}" "$host" "find ~/${remote} -type d -name __pycache__ -prune -exec rm -rf {} +"

echo "sketch cache ${host}:~/${remote}/.cache"
"${ssh[@]}" "$host" "sh -s -- ${sketch_hash} ${rebuild}" <<'EOF'
set -eu
want=$1
rebuild=$2
remote=$HOME/ArduinoApps/flyforager_q
stamp=$remote/.sketch-hash
pending=$remote/.sketch-hash.pending
wipe=0
if [ "$rebuild" = 1 ]; then
  echo "rebuild: clear sketch cache"
  wipe=1
elif [ -f "$pending" ]; then
  echo "previous compile did not finish: clear sketch cache"
  wipe=1
elif [ -f "$stamp" ]; then
  got=$(tr -d '[:space:]' < "$stamp")
  if [ "$got" != "$want" ]; then
    echo "sketch changed: clear sketch cache"
    wipe=1
  else
    echo "sketch unchanged: keep cache"
  fi
else
  echo "sketch cache kept (no stamp yet)"
fi
if [ "$wipe" = 1 ]; then
  rm -rf "$remote/.cache"
  printf '%s\n' "$want" > "$pending"
fi
EOF

echo "remove leftover container ${host}:~/${remote}"
"${ssh[@]}" "$host" "{
  docker ps -aq --filter label=cc.arduino.app.path=\"\$HOME/${remote}\"
  docker ps -aq --filter name=flyforager_q
  docker ps -aq --filter name=flyforager-q
} | sort -u | xargs -r docker rm -f"

echo "start ${host}:~/${remote}"
"${ssh[@]}" "$host" "arduino-app-cli app start ~/${remote} && printf '%s\n' '${sketch_hash}' > ~/${remote}/.sketch-hash && rm -f ~/${remote}/.sketch-hash.pending"
