# Agent Log Frequency Analyzer

This app contains a broken/missing analyzer.

The analyzer must recursively scan /app/corpus and write:

/app/output/word_frequency_report.json

Supported formats:
- .txt
- .md
- .log
- .csv
- .jsonl

Unsupported files should be skipped.
Malformed JSONL rows should not crash the analyzer.
Only normalized English words should be counted.
