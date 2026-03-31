"""
Loader for the NICE dataset (ICSE 2025 re-labeled PROMISE dataset).

Expected raw file location: data/raw/nice/
Accepted formats: CSV with columns [text, label] where label is one of
  FR, NFR, or NONE (case-insensitive). If an nfr_subtype column exists it
  will be used; otherwise it is inferred as "other" for NFR rows.

The script scripts/prepare_datasets.py calls load_nice() and passes the
result to src/datasets/splitter.py.
"""
import os
import glob
import pandas as pd
from typing import Optional


LABEL_MAP = {
    "f": "FR",
    "fr": "FR",
    "functional": "FR",
    "nf": "NFR",
    "nfr": "NFR",
    "non-functional": "NFR",
    "none": "NONE",
    "not a requirement": "NONE",
    "n": "NONE",
    "o": "NONE",
    "other": "NONE",
}

SUBTYPE_MAP = {
    "pe": "performance",
    "performance": "performance",
    "se": "security",
    "security": "security",
    "us": "usability",
    "usability": "usability",
    "re": "reliability",
    "reliability": "reliability",
    "ma": "maintainability",
    "maintainability": "maintainability",
    "po": "portability",
    "portability": "portability",
    "av": "availability",
    "availability": "availability",
    "ft": "other",
    "lf": "usability",
    "sc": "security",
    "a": "availability",
    "l": "usability",
    "mn": "maintainability",
    "mnt": "maintainability",
}


def _normalize_label(raw: str) -> str:
    key = str(raw).strip().lower()
    return LABEL_MAP.get(key, "NONE")


def _normalize_subtype(raw: Optional[str]) -> Optional[str]:
    if not raw or pd.isna(raw):
        return None
    key = str(raw).strip().lower()
    return SUBTYPE_MAP.get(key, "other")


def load_nice(data_dir: Optional[str] = None) -> list[dict]:
    """
    Load all CSV files under data_dir and return a list of standard record dicts:
      {id, text, label, nfr_subtype, source, split}

    'split' is set to None here; splitter.py assigns it later.
    """
    if data_dir is None:
        data_dir = os.getenv("NICE_DATA_DIR", "./data/raw/nice")

    csv_files = glob.glob(os.path.join(data_dir, "**/*.csv"), recursive=True)
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {data_dir}. "
            "Download the NICE dataset and place it there."
        )

    frames = [pd.read_csv(f) for f in sorted(csv_files)]
    df = pd.concat(frames, ignore_index=True)

    # Detect text column
    text_col = next(
        (c for c in df.columns if c.lower() in ("requirementtext", "text", "sentence", "req")),
        df.columns[0],
    )
    # Detect label column
    label_col = next(
        (c for c in df.columns if c.lower() in ("label", "class", "type", "category")),
        df.columns[1],
    )
    # Detect optional subtype column
    subtype_col = next(
        (c for c in df.columns if "subtype" in c.lower() or "nfr" in c.lower()),
        None,
    )

    records = []
    for idx, row in df.iterrows():
        label = _normalize_label(row[label_col])
        subtype = None
        if label == "NFR":
            if subtype_col:
                subtype = _normalize_subtype(row.get(subtype_col))
            if subtype is None:
                subtype = "other"

        records.append(
            {
                "id": f"nice_{idx:05d}",
                "text": str(row[text_col]).strip(),
                "label": label,
                "nfr_subtype": subtype,
                "source": "nice",
                "split": None,
            }
        )

    return records
