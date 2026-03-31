# Missing Datasets

Two of the three datasets required for the RE (Requirements Engineering) evaluation tasks could not be automatically downloaded and must be obtained manually.

---

## 1. NICE Dataset

**Used for:** Multi-class RE classification (FR / NFR / NONE + NFR subtype)

**Expected location:** `data/raw/nice/` (any `.csv` file(s))

**Required CSV columns:**
| Column | Description |
|--------|-------------|
| `text` / `requirementtext` / `sentence` / `req` | Requirement text |
| `label` / `class` / `type` / `category` | FR, NFR, or NONE |
| `nfr_subtype` *(optional)* | e.g. security, performance, usability |

**How to obtain:**
- The NICE dataset is the re-labeled PROMISE NFR dataset from the ICSE 2025 paper:
  *"NICE: A New Dataset for Requirements Classification"*
- Request access from the paper authors or check the paper's supplementary materials / GitHub repo.
- Once you have the CSV, place it at `data/raw/nice/<filename>.csv`.

---

## 2. SecReq Dataset

**Used for:** Binary security requirement classification (security / non-security)

**Expected location:** `data/raw/secreq/` (any `.csv` file(s))

**Required CSV columns:**
| Column | Description |
|--------|-------------|
| `text` / `sentence` / `requirement` / `req` | Requirement text |
| `label` / `class` / `security` / `category` | 1/true/yes/security = security requirement |

**How to obtain:**
- The HuggingFace dataset `infsci2402/SecReq` no longer exists on the Hub.
- The original SecReq dataset comes from the paper:
  *"Automated Identification of Security Requirements from Software Requirements Specifications"*
- Check the paper authors' GitHub or request the dataset directly.
- Alternatively, search for the PROMISE repository subset used for security RE classification.
- Once you have the CSV, place it at `data/raw/secreq/<filename>.csv`.

---

## After Adding the Files

Re-run the data preparation script from the project root:

```bash
.venv/bin/python scripts/prepare_datasets.py
```

This will create the processed JSONL files and pilot samples needed to run the RE evaluation tasks.

---

## Current Status

| Dataset | Status | Pilot Ready |
|---------|--------|-------------|
| NICE | Missing | No |
| SecReq | Missing | No |
| EvalPlus (HumanEval+) | Downloaded | Yes (`data/pilots/codegen_pilot10.jsonl`) |
