#!/bin/bash
# Harbor runs this after the agent. Reward goes to /logs/verifier/reward.txt (exit code ignored).
set -e
cd /app
mkdir -p /logs/verifier

git add -A
git -c user.email=eval@local -c user.name=eval commit -qm agent-changes || true
git diff --stat base HEAD > /logs/verifier/diff-stat.txt || true
if command -v node >/dev/null 2>&1 && [ -f /opt/galaxy-brain/scripts/test-guard.js ]; then
  node /opt/galaxy-brain/scripts/test-guard.js base..HEAD --repo /app --json \
    > /logs/verifier/test-guard.json 2>&1 || true
fi

set +e
python -m ruff check .
lint=$?
python -m pytest -q
suite=$?
set -e

if [ $lint -eq 0 ] && [ $suite -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
