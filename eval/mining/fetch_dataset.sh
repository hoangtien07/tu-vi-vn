#!/usr/bin/env bash
# SPEC_V05 I20 — fetch Renhuai Dataset v3 into eval/dataset/ (gitignored).
# Usage: eval/mining/fetch_dataset.sh
set -euo pipefail

REL="https://github.com/Renhuai123/ziwei-doushu/releases/download/v3.0-samples"
DIR="$(cd "$(dirname "$0")" && pwd)/../dataset"
mkdir -p "$DIR"
cd "$DIR"

PARTS=(ziwei-samples-v3-part1.zip.001 ziwei-samples-v3-part2.zip.002 ziwei-samples-v3-part3.zip.003)

echo "== SHA256SUMS =="
[ -f SHA256SUMS.txt ] || curl -fL "$REL/SHA256SUMS.txt" -o SHA256SUMS.txt
cat SHA256SUMS.txt

echo "== download parts (~5.5GB total) =="
for p in "${PARTS[@]}"; do
  if [ -f "$p" ]; then echo "skip $p (exists)"; else
    curl -fL --retry 3 -C - "$REL/$p" -o "$p"
  fi
done

echo "== verify sha256 =="
grep -E "$(IFS='|'; echo "${PARTS[*]}")" SHA256SUMS.txt | sha256sum -c -

echo "== join parts =="
if [ ! -f ziwei-samples-v3-full.zip ]; then
  cat "${PARTS[@]}" > ziwei-samples-v3-full.zip
fi
ls -la ziwei-samples-v3-full.zip

echo "== unzip =="
if [ ! -d samples ]; then
  unzip -q ziwei-samples-v3-full.zip -d samples
fi
echo "done → $DIR/samples"
find samples -type f | head -5
find samples -type f | wc -l
