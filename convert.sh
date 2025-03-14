#!/bin/zsh

# Get absolute path to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Input file path handling
INPUT_FILE="${1}"
FULL_INPUT_PATH="${SCRIPT_DIR}/Contacts Input/${INPUT_FILE##*/}"

# Check if file exists
if [ ! -f "$FULL_INPUT_PATH" ]; then
    echo "Error: File not found - ${FULL_INPUT_PATH}"
    echo "Possible fixes:"
    echo "1. Check file exists in Contacts Input directory"
    echo "2. Verify exact filename match (including spaces/capitalization)"
    exit 1
fi

# Run converter with absolute path
python3 "${SCRIPT_DIR}/csv-vcf-converter.py" "$FULL_INPUT_PATH"