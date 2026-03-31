"""
Loader for the SecReq dataset.

Tries two sources in order:
  1. Local CSV files under data/raw/secreq/
  2. HuggingFace datasets hub (requires internet, caches locally)

Standard record format:
  {id, text, label, source, split}
  where label is "security" or "non-security"
"""
import os
import glob
import pandas as pd
from typing import Optional


def _normalize_label(raw: str) -> str:
    val = str(raw).strip().lower()
    if val in ("1", "true", "yes", "security", "sec"):
        return "security"
    return "non-security"


def _load_from_csv(data_dir: str) -> list[dict]:
    csv_files = glob.glob(os.path.join(data_dir, "**/*.csv"), recursive=True)
    if not csv_files:
        return []

    frames = [pd.read_csv(f) for f in sorted(csv_files)]
    df = pd.concat(frames, ignore_index=True)

    text_col = next(
        (c for c in df.columns if c.lower() in ("text", "sentence", "requirement", "req")),
        df.columns[0],
    )
    label_col = next(
        (c for c in df.columns if c.lower() in ("label", "class", "security", "category")),
        df.columns[1],
    )

    records = []
    for idx, row in df.iterrows():
        records.append(
            {
                "id": f"secreq_{idx:05d}",
                "text": str(row[text_col]).strip(),
                "label": _normalize_label(row[label_col]),
                "source": "secreq",
                "split": None,
            }
        )
    return records


def _load_from_hf() -> list[dict]:
    from datasets import load_dataset  # type: ignore

    # Try known HuggingFace SecReq dataset identifiers
    candidates = ["infsci2402/SecReq", "secreq"]
    for name in candidates:
        try:
            ds = load_dataset(name, trust_remote_code=True)
            records = []
            for split_name, split_ds in ds.items():
                for idx, row in enumerate(split_ds):
                    text = row.get("text") or row.get("sentence") or row.get("requirement", "")
                    label_raw = row.get("label") or row.get("security") or row.get("class", "0")
                    records.append(
                        {
                            "id": f"secreq_{split_name}_{idx:05d}",
                            "text": str(text).strip(),
                            "label": _normalize_label(str(label_raw)),
                            "source": "secreq",
                            "split": None,
                        }
                    )
            if records:
                return records
        except Exception:
            continue
    return []


def load_secreq(data_dir: Optional[str] = None) -> list[dict]:
    """
    Load SecReq dataset. Falls back to HuggingFace if no local CSV found.
    Returns list of standard record dicts.
    """
    if data_dir is None:
        data_dir = os.getenv("SECREQ_DATA_DIR", "./data/raw/secreq")

    records = _load_from_csv(data_dir)
    if records:
        return records

    print("No local SecReq CSV found, trying HuggingFace datasets hub...")
    records = _load_from_hf()
    if records:
        return records

    raise FileNotFoundError(
        f"SecReq dataset not found. Either place CSV files in {data_dir} "
        "or ensure the 'datasets' package can access the HuggingFace hub."
    )
