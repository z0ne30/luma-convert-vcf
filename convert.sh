#!/bin/bash

# Check if a file was provided
if [ $# -eq 0 ]; then
    echo "Usage: ./convert.sh <csv_file>"
    echo "Example: ./convert.sh \"Contacts Input/Yard Sale Harvard Guests Feb 27 2025.csv\""
    exit 1
fi

# Run the converter with the provided file
python3 csv-vcf-converter.py "$1"