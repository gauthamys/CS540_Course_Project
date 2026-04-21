"""
Extract NICE classification data from the already-processed RE elicitation JSONL.

The re_elicitation_projects.jsonl file contains ground_truth_requirements for each
project, which already have {id, text, label, nfr_subtype} — exactly what the RE
classification pipeline needs. This script flattens them and creates the pilot file.

Run from project root:
    python scripts/prepare_re_classification_data.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.datasets.splitter import split_records, sample_pilot

ELICITATION_PATH = "data/processed/re_elicitation_projects.jsonl"


def write_jsonl(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"  Wrote {len(records):>5} records -> {path}")


def main() -> None:
    print("=== Extracting NICE classification data from elicitation JSONL ===\n")

    if not os.path.exists(ELICITATION_PATH):
        print(f"ERROR: {ELICITATION_PATH} not found. Run prepare_re_elicitation.py first.")
        sys.exit(1)

    # Flatten all ground_truth_requirements from all projects
    records = []
    with open(ELICITATION_PATH) as f:
        for line in f:
            project = json.loads(line)
            project_id = project["project_id"]
            for req in project["ground_truth_requirements"]:
                records.append({
                    "id": req["id"],
                    "text": req["text"],
                    "label": req["label"],
                    "nfr_subtype": req.get("nfr_subtype"),
                    "project_id": project_id,
                    "source": "nice",
                    "split": None,
                })

    from collections import Counter
    label_counts = Counter(r["label"] for r in records)
    print(f"  Loaded {len(records)} requirements from elicitation JSONL")
    print(f"  Label distribution: {dict(label_counts)}")

    # Split into train/test (stratified by label)
    train, test = split_records(records, stratify_key="label")
    write_jsonl(train, "data/processed/nice_train.jsonl")
    write_jsonl(test, "data/processed/nice_test.jsonl")

    # Sample 10-record pilot (stratified)
    pilot = sample_pilot(test, n=10, stratify_key="label")
    write_jsonl(pilot, "data/pilots/nice_pilot10.jsonl")

    print(f"\n  Train: {len(train)}, Test: {len(test)}, Pilot: {len(pilot)}")
    print("\n=== Done. Run scripts/run_pilot_multi.py to evaluate RE classification. ===")


if __name__ == "__main__":
    main()
