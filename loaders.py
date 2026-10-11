"""
loaders.py

Suraksha — Multi-Format Document Loaders (pattern carried over from Pramaan)
================================================================================
Each function takes a file path and returns a list of dicts:
{"text": <string>, "metadata": {"source": <filename>, ...}} — one common
shape regardless of original file format, so everything downstream never
needs to know which loader produced a given chunk.

Adapted for the IT Security Policy domain:
  - the CSV loader now skips "#" metadata lines (the Security Incident Log
    carries its Document ID / Version / Effective Date convention there),
  - the JSON loader reads the "vendor_categories" list from the Approved
    Vendor Security Requirements document.
"""
import csv
import json
import fitz  # PyMuPDF
import docx  # python-docx
from bs4 import BeautifulSoup


def load_pdf(filepath: str) -> list[dict]:
    docs = []
    pdf = fitz.open(filepath)
    for page_num, page in enumerate(pdf, start=1):
        text = page.get_text().strip()
        if text:
            docs.append({
                "text": text,
                "metadata": {"source": filepath.split("/")[-1], "page": page_num},
            })
    pdf.close()
    return docs


def load_docx(filepath: str) -> list[dict]:
    d = docx.Document(filepath)
    full_text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    return [{
        "text": full_text,
        "metadata": {"source": filepath.split("/")[-1]},
    }]


def load_html(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    docs = []
    filename = filepath.split("/")[-1]

    intro = soup.find("p")
    if intro:
        docs.append({"text": intro.get_text(strip=True),
                      "metadata": {"source": filename, "section": "header"}})

    for heading in soup.find_all("h2"):
        section_title = heading.get_text(strip=True)
        paragraph = heading.find_next_sibling("p")
        section_text = paragraph.get_text(strip=True) if paragraph else ""
        docs.append({
            "text": f"{section_title}\n{section_text}",
            "metadata": {"source": filename, "section": section_title},
        })
    return docs


def load_csv(filepath: str) -> list[dict]:
    docs = []
    filename = filepath.split("/")[-1]
    with open(filepath, "r", encoding="utf-8") as f:
        # The incident log opens with "# Document ID / Version / Effective Date"
        # metadata lines — skip them so DictReader gets a clean header row.
        lines = [line for line in f if not line.startswith("#")]
    reader = csv.DictReader(lines)
    for row in reader:
        text = ", ".join(f"{key}: {value}" for key, value in row.items())
        docs.append({
            "text": text,
            "metadata": {"source": filename, "row_id": row.get("incident_id", "")},
        })
    return docs


def load_json(filepath: str) -> list[dict]:
    filename = filepath.split("/")[-1]
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    records = data.get("vendor_categories", [])
    for record in records:
        text = ", ".join(f"{key}: {value}" for key, value in record.items())
        docs.append({
            "text": text,
            "metadata": {"source": filename, "category": record.get("category_name", "")},
        })
    return docs


LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".html": load_html,
    ".csv": load_csv,
    ".json": load_json,
}


def load_document(filepath: str) -> list[dict]:
    ext = "." + filepath.rsplit(".", 1)[-1].lower()
    if ext not in LOADERS:
        raise ValueError(f"No loader registered for file type: {ext}")
    return LOADERS[ext](filepath)
