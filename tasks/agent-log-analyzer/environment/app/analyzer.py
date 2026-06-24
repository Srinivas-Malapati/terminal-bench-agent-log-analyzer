from pathlib import Path
from collections import Counter
import json
import re

CORPUS_DIR = Path("/app/corpus")
OUTPUT_PATH = Path("/app/output/word_frequency_report.json")

SUPPORTED_EXTENSIONS = {".txt", ".md", ".log", ".csv", ".jsonl"}

def extract_words(text):
    """
    BUGGY STARTER:
    - Does not use stopwords
    - Counts too many noisy words
    - Does not handle roles
    - Does not properly separate CSV/JSONL fields
    """
    return re.findall(r"[A-Za-z]+", text.lower())

def analyze():
    counts = Counter()
    total_files_seen = 0
    processed_files = 0
    skipped_files = 0

    # BUG: only scans top-level files, not recursively
    for path in CORPUS_DIR.iterdir():
        if not path.is_file():
            continue

        total_files_seen += 1

        if path.suffix not in SUPPORTED_EXTENSIONS:
            skipped_files += 1
            continue

        processed_files += 1

        # BUG: reads every supported file as plain text
        # BUG: malformed JSONL can crash or be counted incorrectly
        text = path.read_text(encoding="utf-8")
        for word in extract_words(text):
            counts[word] += 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # BUG: wrong/incomplete schema
    result = {
        "top_words": [
            {"word": word, "count": count}
            for word, count in counts.most_common(20)
        ],
        "total_files_seen": total_files_seen,
        "processed_files": processed_files,
        "skipped_files": skipped_files,
    }

    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

if __name__ == "__main__":
    analyze()
