import csv
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

OUTPUT = Path("/app/output/word_frequency_report.json")
EXPECTED_VISIBLE = Path("/tests/expected_visible_output.json")
ANALYZER = Path("/app/analyzer.py")
STOPWORDS_PATH = Path("/app/stopwords.txt")
CORPUS_DIR = Path("/app/corpus")

REQUIRED_KEYS = {
    "total_files_seen",
    "processed_files",
    "skipped_files",
    "malformed_records",
    "total_words",
    "unique_words",
    "top_words",
    "top_words_by_role",
    "per_file",
}

ROLE_KEYS = {"user", "assistant", "tool_error", "unknown"}
SUPPORTED_EXTENSIONS = {".txt", ".md", ".log", ".csv", ".jsonl"}
TEXT_FIELDS = ["text", "content", "message"]


def load_stopwords():
    if not STOPWORDS_PATH.exists():
        return set()
    return {
        line.strip().lower()
        for line in STOPWORDS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


STOPWORDS = load_stopwords()


def extract_words(text):
    words = re.findall(r"[A-Za-z]+", text.lower())
    return [word for word in words if len(word) > 1 and word not in STOPWORDS]


def sorted_word_items(counter, limit=20):
    return [
        {"word": word, "count": count}
        for word, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def top_word_for_counter(counter):
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def text_from_json_object(obj):
    if not isinstance(obj, dict):
        return ""
    values = []
    for field in TEXT_FIELDS:
        value = obj.get(field)
        if isinstance(value, str):
            values.append(value)
    return " ".join(values)


def compute_expected(corpus_dir):
    global_counts = Counter()
    role_counts = {role: Counter() for role in ROLE_KEYS}
    per_file = {}

    total_files_seen = 0
    processed_files = 0
    skipped_files = 0
    malformed_records = 0

    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file():
            continue

        total_files_seen += 1
        rel = path.relative_to(corpus_dir).as_posix()

        if path.suffix not in SUPPORTED_EXTENSIONS:
            skipped_files += 1
            continue

        processed_files += 1
        file_counts = Counter()
        file_role_counts = Counter()

        if path.suffix in {".txt", ".md", ".log"}:
            text = path.read_text(encoding="utf-8")
            words = extract_words(text)
            global_counts.update(words)
            role_counts["unknown"].update(words)
            file_counts.update(words)
            file_role_counts["unknown"] += len(words)

        elif path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    role = row.get("role", "unknown")
                    if role not in ROLE_KEYS:
                        role = "unknown"
                    text = " ".join(
                        row.get(field, "")
                        for field in TEXT_FIELDS
                        if isinstance(row.get(field, ""), str)
                    )
                    words = extract_words(text)
                    global_counts.update(words)
                    role_counts[role].update(words)
                    file_counts.update(words)
                    file_role_counts[role] += len(words)

        elif path.suffix == ".jsonl":
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        malformed_records += 1
                        continue

                    role = obj.get("role", "unknown") if isinstance(obj, dict) else "unknown"
                    if role not in ROLE_KEYS:
                        role = "unknown"

                    words = extract_words(text_from_json_object(obj))
                    global_counts.update(words)
                    role_counts[role].update(words)
                    file_counts.update(words)
                    file_role_counts[role] += len(words)

        per_file[f"corpus/{rel}"] = {
            "word_count": sum(file_counts.values()),
            "unique_words": len(file_counts),
            "top_word": top_word_for_counter(file_counts),
        }

    return {
        "total_files_seen": total_files_seen,
        "processed_files": processed_files,
        "skipped_files": skipped_files,
        "malformed_records": malformed_records,
        "total_words": sum(global_counts.values()),
        "unique_words": len(global_counts),
        "top_words": sorted_word_items(global_counts),
        "top_words_by_role": {
            role: sorted_word_items(role_counts[role])
            for role in sorted(ROLE_KEYS)
        },
        "per_file": dict(sorted(per_file.items())),
    }


def load_json(path):
    assert path.exists(), f"Missing file: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} is not valid JSON: {exc}") from exc


def assert_schema(data):
    assert isinstance(data, dict), "Output must be a JSON object"
    assert set(data.keys()) == REQUIRED_KEYS, (
        f"Top-level keys mismatch. Expected {sorted(REQUIRED_KEYS)}, got {sorted(data.keys())}"
    )
    assert set(data["top_words_by_role"].keys()) == ROLE_KEYS, (
        f"Role keys mismatch. Expected {sorted(ROLE_KEYS)}, got {sorted(data['top_words_by_role'].keys())}"
    )
    assert isinstance(data["per_file"], dict), "per_file must be an object"


def assert_deterministic_order(data):
    top_words = data["top_words"]
    assert top_words == sorted(top_words, key=lambda x: (-x["count"], x["word"])), (
        "top_words must be sorted by count descending, then word ascending"
    )

    for role, items in data["top_words_by_role"].items():
        assert items == sorted(items, key=lambda x: (-x["count"], x["word"])), (
            f"top_words_by_role[{role}] must be sorted deterministically"
        )

    assert list(data["per_file"].keys()) == sorted(data["per_file"].keys()), (
        "per_file keys must be sorted"
    )


def run_analyzer():
    result = subprocess.run(
        ["python", str(ANALYZER)],
        cwd="/app",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Analyzer failed with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert OUTPUT.exists(), "Analyzer did not produce /app/output/word_frequency_report.json"


def write_hidden_corpus():
    if CORPUS_DIR.exists():
        shutil.rmtree(CORPUS_DIR)
    CORPUS_DIR.mkdir(parents=True)

    (CORPUS_DIR / "notes").mkdir()
    (CORPUS_DIR / "events").mkdir()
    (CORPUS_DIR / "unsupported").mkdir()

    (CORPUS_DIR / "notes" / "incident.md").write_text(
        "Retry checkout failed. Retry checkout recovered. Hindi भुगतान ignored.",
        encoding="utf-8",
    )

    (CORPUS_DIR / "events" / "agent.log").write_text(
        "assistant observed calendar timeout. tool_error reported checkout timeout.",
        encoding="utf-8",
    )

    with (CORPUS_DIR / "events" / "messages.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["role", "message", "metadata"])
        writer.writeheader()
        writer.writerow({"role": "user", "message": "checkout refund failed retry", "metadata": "source=web"})
        writer.writerow({"role": "assistant", "message": "retry checkout with calendar", "metadata": "source=agent"})
        writer.writerow({"role": "tool_error", "message": "calendar timeout timeout", "metadata": "source=tool"})

    with (CORPUS_DIR / "agent_runs.jsonl").open("w", encoding="utf-8") as f:
        rows = [
            {"role": "user", "content": "checkout failed after timeout"},
            {"role": "assistant", "content": "retry checkout and refund"},
            {"role": "tool_error", "content": "checkout api timeout"},
        ]
        for row in rows:
            f.write(json.dumps(row) + "\n")
        f.write('{"role": "broken", "content": "this row is malformed"\n')

    (CORPUS_DIR / "unsupported" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (CORPUS_DIR / "unsupported" / "ignore.me").write_text(
        "checkout retry should not be counted",
        encoding="utf-8",
    )


def main():
    assert ANALYZER.exists(), "Missing analyzer artifact: /app/analyzer.py"

    visible_actual = load_json(OUTPUT)
    visible_expected = load_json(EXPECTED_VISIBLE)

    assert_schema(visible_actual)
    assert_deterministic_order(visible_actual)

    assert visible_actual == visible_expected, (
        "Visible output did not match expected output.\n"
        f"Actual:\n{json.dumps(visible_actual, indent=2, sort_keys=True)}\n"
        f"Expected:\n{json.dumps(visible_expected, indent=2, sort_keys=True)}"
    )

    write_hidden_corpus()
    if OUTPUT.exists():
        OUTPUT.unlink()

    run_analyzer()

    hidden_actual = load_json(OUTPUT)
    hidden_expected = compute_expected(CORPUS_DIR)

    assert_schema(hidden_actual)
    assert_deterministic_order(hidden_actual)

    assert hidden_actual == hidden_expected, (
        "Hidden rerun output did not match expected output.\n"
        f"Actual:\n{json.dumps(hidden_actual, indent=2, sort_keys=True)}\n"
        f"Expected:\n{json.dumps(hidden_expected, indent=2, sort_keys=True)}"
    )

    print("Visible and hidden verifier checks passed.")


if __name__ == "__main__":
    main()
