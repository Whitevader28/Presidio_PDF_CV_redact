#!/bin/bash

# Simple script to process all directories in a folder with the redact.py script

# Check if arguments are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <input_root_dir> <output_root_dir>"
    exit 1
fi

INPUT_ROOT="$1"
OUTPUT_ROOT="$2"

# Check if input directory exists
if [ ! -d "$INPUT_ROOT" ]; then
    echo "Error: Input directory '$INPUT_ROOT' does not exist."
    exit 1
fi

# Create output root if it doesn't exist
mkdir -p "$OUTPUT_ROOT"

echo "Processing all directories in $INPUT_ROOT"

# Loop through all immediate subdirectories of the input root
for DIR in "$INPUT_ROOT"/*/; do
    if [ -d "$DIR" ]; then
        # Get the directory name without path
        DIR_NAME=$(basename "$DIR")
        
        # Create corresponding output directory
        OUTPUT_DIR="$OUTPUT_ROOT/$DIR_NAME"
        mkdir -p "$OUTPUT_DIR"
        
        echo "===================================="
        echo "Processing directory: $DIR_NAME"
        echo "===================================="
        
        # Run the Python script to process this directory's PDFs
        python3 redact.py --input "$DIR" --output "$OUTPUT_DIR" --batch
    fi
done

echo "All directories processed!"
