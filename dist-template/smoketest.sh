#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

MAIN_PY="$SCRIPT_DIR/pylisa"

# Prepend SCRIPT_DIR to all input paths
INPUT_1=(
    "$SCRIPT_DIR/test/01/main.py"
)

PROPERTY="$SCRIPT_DIR/test/valid-assert.prp"

# Run the command
python3 "$MAIN_PY" --version
python3 "$MAIN_PY" check --inputs "${INPUT_1[@]}" --property "$PROPERTY"
