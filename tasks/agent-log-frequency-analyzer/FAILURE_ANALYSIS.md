# Failure Analysis

## Expected failure modes

This task is designed to fail when an agent only makes shallow fixes to the starter analyzer.

Likely failure modes include:

1. Not scanning nested directories recursively.
2. Treating CSV and JSONL files as plain text.
3. Crashing on malformed JSONL rows.
4. Counting stopwords, timestamps, IDs, or JSON keys.
5. Missing role-based counts for `user`, `assistant`, `tool_error`, and `unknown`.
6. Producing an incomplete or incorrectly sorted JSON schema.
7. Including unsupported files in `per_file`.

## Why the no-op agent fails

The starter analyzer only scans top-level files and writes an incomplete schema. It does not process the nested corpus correctly, does not produce `top_words_by_role`, does not produce `per_file`, and does not match the expected deterministic output.

## Verification strategy

The verifier checks the declared output artifact:

`/app/output/word_frequency_report.json`

It validates schema, deterministic ordering, role keys, per-file fields, and exact expected output.
