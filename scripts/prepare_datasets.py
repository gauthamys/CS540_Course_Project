"""
One-shot data preparation script.

Run from the project root:
    python scripts/prepare_datasets.py

What it does:
  1. Loads NICE, SecReq, and EvalPlus datasets
  2. Applies train/test splits
  3. Writes processed JSONL files to data/processed/
  4. Samples 10-record pilot files to data/pilots/

All paths and seeds are controlled by .env variables.
"""
import os
import sys
import json

# Make src importable when running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.datasets.nice_loader import load_nice
from src.datasets.secreq_loader import load_secreq
from src.datasets.evalplus_loader import load_evalplus
from src.datasets.splitter import split_records, sample_pilot


def write_jsonl(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"  Wrote {len(records):>5} records -> {path}")


def main() -> None:
    print("=== Preparing datasets ===\n")

    # ── NICE ──────────────────────────────────────────────────────────────────
    print("[1/3] Loading NICE dataset...")
    try:
        nice_records = load_nice()
        print(f"  Loaded {len(nice_records)} raw records")
        nice_train, nice_test = split_records(nice_records, stratify_key="label")
        write_jsonl(nice_train, "data/processed/nice_train.jsonl")
        write_jsonl(nice_test, "data/processed/nice_test.jsonl")
        nice_pilot = sample_pilot(nice_test, n=10, stratify_key="label")
        write_jsonl(nice_pilot, "data/pilots/nice_pilot10.jsonl")
    except FileNotFoundError as e:
        print(f"  SKIP: {e}")

    # ── SecReq ────────────────────────────────────────────────────────────────
    print("\n[2/3] Loading SecReq dataset...")
    try:
        secreq_records = load_secreq()
        print(f"  Loaded {len(secreq_records)} raw records")
        secreq_train, secreq_test = split_records(secreq_records, stratify_key="label")
        write_jsonl(secreq_train, "data/processed/secreq_train.jsonl")
        write_jsonl(secreq_test, "data/processed/secreq_test.jsonl")
        secreq_pilot = sample_pilot(secreq_test, n=10, stratify_key="label")
        write_jsonl(secreq_pilot, "data/pilots/secreq_pilot10.jsonl")
    except FileNotFoundError as e:
        print(f"  SKIP: {e}")

    # ── EvalPlus ──────────────────────────────────────────────────────────────
    print("\n[3/3] Loading EvalPlus (HumanEval+ and MBPP+)...")
    try:
        evalplus_records = load_evalplus(include_mbpp=False)  # start with HumanEval+ only
        print(f"  Loaded {len(evalplus_records)} problems")
        # EvalPlus has a single evaluation set; no train split needed
        write_jsonl(evalplus_records, "data/processed/humaneval_plus.jsonl")
        codegen_pilot = sample_pilot(
            evalplus_records, n=10, stratify_key=None, split_filter="test"
        )
        write_jsonl(codegen_pilot, "data/pilots/codegen_pilot10.jsonl")
    except Exception as e:
        print(f"  SKIP: {e}")

    print("\n=== Done. Check data/processed/ and data/pilots/ ===")


if __name__ == "__main__":
    main()
