#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

PYLISA="$SCRIPT_DIR/pylisa"

# Prepend SCRIPT_DIR to all input paths
INPUT_1=(
    "$SCRIPT_DIR/test/01/main.py"
)

PROPERTY="$SCRIPT_DIR/test/valid-assert.prp"

# Run the command
"$PYLISA" --version
"$PYLISA" check --inputs "${INPUT_1[@]}" --property "$PROPERTY"
