#!/usr/bin/env bash
# Fetch the decision kernel's circuit tables from the GitHub Release
# and place them next to sim.cpp. The .bin files are not in git (they
# are derived from the FlyWire connectivity, CC BY-NC 4.0), they are
# distributed as the asset kernel-data.zip of Release tag kernel-v1.
#
#   scripts/download_kernel_data.sh
#
# Run from anywhere. Verifies the zip's SHA256 and each file's size.

set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
dest="$root/src/flyforager_q/python/kernel"
url="https://github.com/hamling-ling/fly-forager/releases/download/kernel-v1/kernel-data.zip"
want_sha="2bd7ae67ad1411d74f936b32a985e212fe724cc0faae97bdfe3ec8a162be9e49"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "download $url"
curl -fL -o "$tmp/kernel-data.zip" "$url"

got_sha=$(sha256sum "$tmp/kernel-data.zip" | awk '{print $1}')
if [[ "$got_sha" != "$want_sha" ]]; then
  echo "sha256 mismatch: got $got_sha" >&2
  exit 1
fi
echo "sha256 ok"

mkdir -p "$dest"
if command -v unzip >/dev/null 2>&1; then
  unzip -o "$tmp/kernel-data.zip" -d "$dest"
else
  python3 -m zipfile -e "$tmp/kernel-data.zip" "$dest"
fi

# name size-in-bytes, as packed in kernel-data.zip
while read -r name size; do
  actual=$(stat -c %s "$dest/$name")
  if [[ "$actual" != "$size" ]]; then
    echo "size mismatch: $name is $actual, want $size" >&2
    exit 1
  fi
  echo "ok $name ($size bytes)"
done <<'EOF'
gaba.bin 37601
indptr.bin 5504
post.bin 150404
sugar.bin 80
w_base.bin 300808
EOF

echo "kernel data ready in $dest"
