#!/bin/sh
# Stage private inputs into the Harbor task dirs (everything staged here is gitignored):
# repo snapshot at the pinned broken commit, instruction.md from eval/tasks prompts, verifiers.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
CONSEJO=${1:?usage: prepare.sh <path-to-consejo-7-sabios>}
PIN=${2:-4df1873}

for t in t1-json-non-dict t2-signed-int32 t5-ruff-gate; do
  dir="$HERE/tasks/$t"
  rm -rf "$dir/environment/repo"
  mkdir -p "$dir/environment/repo"
  git -C "$CONSEJO" archive "$PIN" | tar -x -C "$dir/environment/repo"
  cp "$HERE/../tasks/$t/prompt.md" "$dir/instruction.md"
done
cp "$HERE/../tasks/t1-json-non-dict/verify_t1_test.py" "$HERE/tasks/t1-json-non-dict/tests/"
cp "$HERE/../tasks/t2-signed-int32/verify_t2_test.py" "$HERE/tasks/t2-signed-int32/tests/"
echo "staged: repo@$PIN + instructions + verifiers (all gitignored)"
