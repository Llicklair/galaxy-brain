#!/bin/sh
# Arm-independent verifier for t5-ruff-gate: lint green AND suite green.
set -e
python -m ruff check .
python -m pytest -q
