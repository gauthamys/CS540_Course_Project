"""
Loader for the PURE (Pure Unfiltered Requirements Examples) dataset.
Ferrari et al., RE'17. https://zenodo.org/records/1414117

Expected raw file location: data/raw/pure/requirements-xml.zip
  (or already extracted *.xml files under data/raw/pure/)

Two XML schemas are present in the dataset:

  Schema A — explicit <req> tags (6 documents):
    <req id="..."><text_body>...</text_body></req>
    FR/NFR inferred from nearest ancestor <p><title>.

  Schema B — leaf <p> nodes (12 documents):
    Requirements are leaf-level <p> elements (no nested <p>, has <text_body>)
    containing "shall" or "must". FR/NFR inferred from ancestor <p><title>.

Standard record format:
  {id, text, label, nfr_subtype, project_id, source, split}
"""
import os
import re
import glob
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

_REQ_KEYWORDS = re.compile(r"\b(shall|must)\b", re.IGNORECASE)

# Keywords in <p><title> that signal an NFR section
_NFR_TITLE_KEYWORDS = (
    "non-functional", "nonfunctional", "non functional",
    "quality attribute", "quality requirement",
    "nfr", "performance requirement", "security requirement",
    "usability requirement", "reliability requirement",
    "maintainability", "portability requirement", "availability",
)

_SUBTYPE_KEYWORDS: list[tuple[str, str]] = [
    ("performance", "performance"),
    ("scalab", "performance"),
    ("security", "security"),
    ("privacy", "security"),
    ("usab", "usability"),
    ("look and feel", "usability"),
    ("look & feel", "usability"),
    ("reliab", "reliability"),
    ("fault toleran", "reliability"),
    ("maintain", "maintainability"),
    ("portab", "portability"),
    ("availab", "availability"),
]


def _strip_ns(xml_bytes: bytes) -> str:
    """Remove namespace declarations that cause ET unbound-prefix errors."""
    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', "", text)
    text = re.sub(r'\s+xsi:\w+="[^"]*"', "", text)
    return text


def _infer_label_from_title(title: str) -> tuple[str, Optional[str]]:
    """Given an ancestor section title, return (label, nfr_subtype)."""
    t = title.strip().lower()
    is_nfr = any(kw in t for kw in _NFR_TITLE_KEYWORDS)
    if not is_nfr:
        return "FR", None
    subtype = next(
        (st for kw, st in _SUBTYPE_KEYWORDS if kw in t),
        "other",
    )
    return "NFR", subtype


def _elem_text(elem: ET.Element) -> str:
    """Extract all inner text from an element, collapsed to single spaces."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem.iter():
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return " ".join(" ".join(p.split()) for p in parts if p.strip()).strip("'\" ")


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    parent_map: dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in parent:
            parent_map[child] = parent
    return parent_map


def _nearest_p_title(elem: ET.Element, parent_map: dict) -> str:
    """Walk up the tree; return title text of the nearest <p> ancestor."""
    node = parent_map.get(elem)
    while node is not None:
        if node.tag == "p":
            title_elem = node.find("title")
            return (title_elem.text or "").strip() if title_elem is not None else ""
        node = parent_map.get(node)
    return ""


def _parse_xml(xml_str: str, project_id: str, offset: int = 0) -> list[dict]:
    """
    Parse one PURE XML document into standard requirement records.
    Handles both Schema A (<req> tags) and Schema B (leaf <p> nodes).
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return []

    parent_map = _build_parent_map(root)
    records: list[dict] = []
    seen_texts: set[str] = set()

    def add_record(elem: ET.Element, text: str) -> None:
        text = text.strip("'\" ")
        if not text or text in seen_texts:
            return
        seen_texts.add(text)
        section_title = _nearest_p_title(elem, parent_map)
        label, subtype = _infer_label_from_title(section_title)
        records.append({
            "id": f"pure_{project_id}_{offset + len(records):04d}",
            "text": text,
            "label": label,
            "nfr_subtype": subtype,
            "project_id": project_id,
            "source": "pure",
            "split": None,
        })

    # ── Schema A: explicit <req> tags ─────────────────────────────────────────
    req_elems = list(root.iter("req"))
    if req_elems:
        for req in req_elems:
            tb = req.find("text_body")
            text = _elem_text(tb if tb is not None else req)
            add_record(req, text)
        return records

    # ── Schema B: leaf <p> nodes filtered by "shall/must" ─────────────────────
    for p in root.iter("p"):
        # Leaf <p>: has <text_body> but no nested <p>
        if p.find("p") is not None:
            continue
        tb = p.find("text_body")
        if tb is None:
            continue
        text = _elem_text(tb)
        if _REQ_KEYWORDS.search(text):
            add_record(p, text)

    return records


def _extract_zip(zip_path: str, target_dir: str) -> None:
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target_dir)


def load_pure(data_dir: Optional[str] = None) -> list[dict]:
    """
    Load all PURE XML documents and return a flat list of requirement records.

    Looks for:
      1. requirements-xml.zip under data_dir/ → extracts automatically
      2. Already-extracted *.xml files under data_dir/ (including subdirs)

    Returns:
        list of {id, text, label, nfr_subtype, project_id, source, split}
    """
    if data_dir is None:
        data_dir = os.getenv("PURE_DATA_DIR", "./data/raw/pure")

    zip_path = os.path.join(data_dir, "requirements-xml.zip")

    # Load directly from zip without extracting to disk
    if os.path.exists(zip_path):
        all_records: list[dict] = []
        with zipfile.ZipFile(zip_path, "r") as z:
            xml_names = [
                n for n in z.namelist()
                if n.endswith(".xml") and not os.path.basename(n).startswith("._")
            ]
            for name in sorted(xml_names):
                project_id = os.path.splitext(os.path.basename(name))[0]
                raw = z.read(name)
                xml_str = _strip_ns(raw)
                recs = _parse_xml(xml_str, project_id, offset=len(all_records))
                all_records.extend(recs)
        if all_records:
            return all_records

    # Fallback: already-extracted files on disk
    xml_files = sorted(glob.glob(os.path.join(data_dir, "**/*.xml"), recursive=True))
    if not xml_files:
        raise FileNotFoundError(
            f"No XML files found in {data_dir}. "
            "Download requirements-xml.zip from https://zenodo.org/records/1414117 "
            "and place it in data/raw/pure/."
        )

    all_records = []
    for xml_path in xml_files:
        project_id = os.path.splitext(os.path.basename(xml_path))[0]
        with open(xml_path, "rb") as f:
            xml_str = _strip_ns(f.read())
        recs = _parse_xml(xml_str, project_id, offset=len(all_records))
        all_records.extend(recs)

    return all_records


def load_pure_by_project(data_dir: Optional[str] = None) -> dict[str, list[dict]]:
    """
    Load PURE dataset grouped by project_id (one entry per XML document).

    Returns:
        dict mapping project_id → list of requirement records.
    """
    records = load_pure(data_dir)
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(r["project_id"], []).append(r)
    return groups
