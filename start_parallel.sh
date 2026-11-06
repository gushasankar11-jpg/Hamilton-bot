#!/bin/bash
LIST_FILE="$(pwd)/book_list.txt"
find ~/storage/shared/Hamilton_uploads_abv/books -name "*.pdf" > "$LIST_FILE"
echo "Found $(wc -l < "$LIST_FILE") PDFs. Launching engine..."
cat "$LIST_FILE" | xargs -P 12 -I {} python3 worker_extract.py "{}"
echo "🎉 ALL BOOKS EXTRACTED!"
