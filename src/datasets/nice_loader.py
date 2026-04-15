"""
Loader for the NICE dataset (ICSE 2025 re-labeled PROMISE dataset).

Expected raw file location: data/raw/nice/
Accepted formats:
  1. NICE PROMISE-relabeled CSV (primary):
     Columns: ProjectID, RequirementText, IsFunctional, IsQuality,
              Availability (A), Fault Tolerance (FT), Legal (L), Look & Feel (LF),
              Maintainability (MN), Operability (O), Performance (PE), Portability (PO),
              Scalability (SC), Security (SE), Usability (US), Other (OT)

  2. Simple CSV with columns [text, label] where label is one of FR, NFR, NONE.

Label derivation (format 1):
  - IsFunctional=1 → "FR"
  - IsFunctional=0 and IsQuality=1 → "NFR"
  - IsFunctional=0 and IsQuality=0 → "NONE"
  (rows that are both IsFunctional=1 and IsQuality=1 are labelled "FR")

NFR subtype is the one-hot column with value 1 among the quality attribute columns.
"""
import os
import glob
import pandas as pd
from typing import Optional

# ── One-hot column → subtype name mapping ─────────────────────────────────────

ONEHOT_SUBTYPE_MAP = {
    "availability (a)":      "availability",
    "fault tolerance (ft)":  "reliability",
    "legal (l)":             "other",
    "look & feel (lf)":      "usability",
    "maintainability (mn)":  "maintainability",
    "operability (o)":       "usability",
    "performance (pe)":      "performance",
    "portability (po)":      "portability",
    "scalability (sc)":      "performance",
    "security (se)":         "security",
    "usability (us)":        "usability",
    "other (ot)":            "other",
}

# ── Fallback label/subtype maps for simple CSV format ─────────────────────────

LABEL_MAP = {
    "f": "FR", "fr": "FR", "functional": "FR",
    "nf": "NFR", "nfr": "NFR", "non-functional": "NFR",
    "none": "NONE", "not a requirement": "NONE", "n": "NONE", "o": "NONE", "other": "NONE",
}

SUBTYPE_MAP = {
    "pe": "performance", "performance": "performance",
    "se": "security", "security": "security",
    "us": "usability", "usability": "usability",
    "re": "reliability", "reliability": "reliability",
    "ma": "maintainability", "maintainability": "maintainability",
    "po": "portability", "portability": "portability",
    "av": "availability", "availability": "availability",
    "ft": "reliability", "lf": "usability", "sc": "performance",
    "a": "availability", "l": "other", "mn": "maintainability", "mnt": "maintainability",
}


def _normalize_label(raw: str) -> str:
    return LABEL_MAP.get(str(raw).strip().lower(), "NONE")


def _normalize_subtype(raw: Optional[str]) -> Optional[str]:
    if not raw or pd.isna(raw):
        return None
    return SUBTYPE_MAP.get(str(raw).strip().lower(), "other")


def _is_onehot_format(df: pd.DataFrame) -> bool:
    """Return True if this looks like the NICE PROMISE one-hot CSV."""
    cols_lower = {c.lower() for c in df.columns}
    return "isfunctional" in cols_lower and "isquality" in cols_lower


def _load_onehot(df: pd.DataFrame, source_offset: int = 0) -> list[dict]:
    """Parse the NICE PROMISE-relabeled one-hot CSV into standard records."""
    # Normalise column names for reliable access
    df.columns = [c.strip() for c in df.columns]
    col_map = {c.lower(): c for c in df.columns}

    text_col = col_map.get("requirementtext", df.columns[1])
    project_col = col_map.get("projectid", df.columns[0])
    is_func_col = col_map.get("isfunctional")
    is_qual_col = col_map.get("isquality")

    # Identify quality attribute (subtype) columns
    subtype_cols = [
        c for c in df.columns
        if c.lower() in ONEHOT_SUBTYPE_MAP
    ]

    records = []
    for idx, row in df.iterrows():
        is_func = int(row[is_func_col]) if is_func_col else 0
        is_qual = int(row[is_qual_col]) if is_qual_col else 0

        if is_func:
            label = "FR"
        elif is_qual:
            label = "NFR"
        else:
            label = "NONE"

        subtype = None
        if label == "NFR" and subtype_cols:
            for sc in subtype_cols:
                try:
                    if int(row[sc]) == 1:
                        subtype = ONEHOT_SUBTYPE_MAP[sc.lower()]
                        break
                except (ValueError, TypeError):
                    pass
            if subtype is None:
                subtype = "other"

        project_id = str(row[project_col]).strip()

        records.append({
            "id": f"nice_{source_offset + idx:05d}",
            "text": str(row[text_col]).strip().strip("'"),
            "label": label,
            "nfr_subtype": subtype,
            "project_id": project_id,
            "source": "nice",
            "split": None,
        })

    return records


def _load_simple(df: pd.DataFrame, source_offset: int = 0) -> list[dict]:
    """Parse a simple text/label CSV."""
    df.columns = [c.strip() for c in df.columns]
    col_lower = {c.lower(): c for c in df.columns}

    text_col = next(
        (col_lower[k] for k in ("requirementtext", "text", "sentence", "req") if k in col_lower),
        df.columns[0],
    )
    label_col = next(
        (col_lower[k] for k in ("label", "class", "type", "category") if k in col_lower),
        df.columns[1],
    )
    subtype_col = next(
        (c for c in df.columns if "subtype" in c.lower() or "nfr" in c.lower()),
        None,
    )
    project_id_col = next(
        (col_lower[k] for k in ("projectid", "project_id", "project") if k in col_lower),
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

        project_id = (
            str(row[project_id_col]).strip()
            if project_id_col
            else f"proj_{source_offset + idx:05d}"
        )

        records.append({
            "id": f"nice_{source_offset + idx:05d}",
            "text": str(row[text_col]).strip(),
            "label": label,
            "nfr_subtype": subtype,
            "project_id": project_id,
            "source": "nice",
            "split": None,
        })

    return records


def load_nice(data_dir: Optional[str] = None) -> list[dict]:
    """
    Load all CSV files under data_dir and return a list of standard record dicts:
      {id, text, label, nfr_subtype, project_id, source, split}

    'split' is set to None here; splitter.py assigns it later.
    Handles both the NICE PROMISE one-hot format and simple label CSVs.
    """
    if data_dir is None:
        data_dir = os.getenv("NICE_DATA_DIR", "./data/raw/nice")

    csv_files = glob.glob(os.path.join(data_dir, "**/*.csv"), recursive=True)
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {data_dir}. "
            "Download the NICE dataset and place it there."
        )

    all_records: list[dict] = []
    for fpath in sorted(csv_files):
        df = pd.read_csv(fpath)
        offset = len(all_records)
        if _is_onehot_format(df):
            all_records.extend(_load_onehot(df, source_offset=offset))
        else:
            all_records.extend(_load_simple(df, source_offset=offset))

    return all_records


def load_nice_by_project(data_dir: Optional[str] = None) -> dict[str, list[dict]]:
    """
    Load NICE dataset grouped by project_id.

    Returns:
        dict mapping project_id → list of requirement records.
        Each record has: id, text, label, nfr_subtype, project_id, source, split.
    """
    records = load_nice(data_dir)
    groups: dict[str, list[dict]] = {}
    for r in records:
        pid = r["project_id"]
        groups.setdefault(pid, []).append(r)
    return groups
