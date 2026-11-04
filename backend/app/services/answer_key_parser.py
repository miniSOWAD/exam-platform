"""Parse answer-only TXT/PDF files into numbered MCQ answer entries.

Accepted examples include:
  1. A  2. B
  1)ক  2)খ
  ১.ক ২.খ
  ১) ক\n২) খ

PDFs with an embedded text layer are read directly. Image-only PDFs use the
same Bengali-capable OCR configuration as the question-paper importer.
"""
from __future__ import annotations

import re
import unicodedata
from io import BytesIO
from typing import Any

import fitz
import httpx
from app.services.pdf_exam_parser import (
    OCRServiceError,
    OCRUnavailableError,
    _ocr_space_image,
    _ocr_tesseract,
    _render,
    _tesseract_ready,
)

BENGALI_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
OPTION_INDEX = {"ক": 0, "খ": 1, "গ": 2, "ঘ": 3, "a": 0, "b": 1, "c": 2, "d": 3}
OPTION_LABELS = ["ক", "খ", "গ", "ঘ"]

# The separator may be punctuation (., ), ।, :, -) or whitespace.
# Requiring an option label immediately after the separator prevents ordinary
# numbered headings and question text from being mistaken for answers.
ANSWER_TOKEN_RE = re.compile(
    r"(?<![0-9])(?P<number>[0-9]{1,4})[ \t]*(?:[.)।:：\-–—][ \t]*|[ \t]+)"
    r"(?P<option>[কখগঘa-dA-D])(?=$|[\s,;|/\)\].।:：\-–—])",
    re.IGNORECASE,
)


def parse_answer_key_text(text: str) -> list[dict[str, Any]]:
    """Return one grouped entry per question number, preserving conflicting labels."""
    normalized = unicodedata.normalize("NFKC", text or "").translate(BENGALI_DIGITS)
    grouped: dict[int, list[dict[str, Any]]] = {}

    for match in ANSWER_TOKEN_RE.finditer(normalized):
        number = int(match.group("number"))
        raw_label = match.group("option")
        label = raw_label if raw_label in OPTION_LABELS else raw_label.upper()
        index = OPTION_INDEX.get(raw_label.casefold())
        if index is None:
            continue
        item = {"label": label, "index": index}
        bucket = grouped.setdefault(number, [])
        if item not in bucket:
            bucket.append(item)

    return [
        {
            "question_number": number,
            "option_labels": [item["label"] for item in items],
            "option_indices": [item["index"] for item in items],
        }
        for number, items in sorted(grouped.items())
    ]


def _decode_text_file(raw: bytes) -> str:
    if not raw:
        raise ValueError("The TXT answer-key file is empty.")
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode the TXT file. Save it as UTF-8 and upload again.")


def _pdf_page_texts(raw: bytes, max_pages: int) -> tuple[fitz.Document, list[str]]:
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise ValueError("The uploaded answer-key PDF is not readable.") from exc

    if document.is_encrypted:
        document.close()
        raise ValueError("Password-protected PDFs are not supported. Upload an unlocked PDF.")
    if len(document) > max_pages:
        count = len(document)
        document.close()
        raise ValueError(f"The answer-key PDF has {count} pages; the limit is {max_pages} pages.")
    return document, [page.get_text("text", sort=True) for page in document]


def extract_answer_key_file(
    raw: bytes,
    filename: str,
    ocr_space_api_key: str = "",
    ocr_space_engine: int = 3,
    ocr_space_timeout_seconds: int = 90,
    max_pages: int = 30,
) -> dict[str, Any]:
    """Extract answer-key text from a UTF-8 TXT or PDF upload."""
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if extension == "txt":
        text = _decode_text_file(raw)
        entries = parse_answer_key_text(text)
        if not entries:
            raise ValueError("No answer entries were found. Use formats such as 1. A, 1)ক, or ১.ক.")
        return {"entries": entries, "source_type": "txt", "ocr_used": False, "ocr_engine": "plain-text", "pages": 0}

    if extension != "pdf":
        raise ValueError("Upload an answer-key PDF or TXT file.")

    document, page_texts = _pdf_page_texts(raw, max_pages)
    try:
        native_entries = [parse_answer_key_text(text) for text in page_texts]
        ocr_used = False
        ocr_engine = "embedded-text"
        # OCR only pages without parseable answer entries. This preserves the
        # text layer where available and also supports mixed text/scanned PDFs.
        pages_needing_ocr = [i for i, entries in enumerate(native_entries) if not entries]
        if pages_needing_ocr:
            if _tesseract_ready():
                ocr_engine = "tesseract-ben+eng"
                for page_index in pages_needing_ocr:
                    image = _render(document[page_index], document[page_index].rect, 300)
                    page_texts[page_index] = _ocr_tesseract(image, 6)
                    ocr_used = True
            elif ocr_space_api_key.strip():
                ocr_engine = f"ocr.space-engine-{ocr_space_engine}"
                with httpx.Client(timeout=httpx.Timeout(ocr_space_timeout_seconds, connect=20)) as client:
                    for page_index in pages_needing_ocr:
                        image = _render(document[page_index], document[page_index].rect, 300)
                        page_texts[page_index] = _ocr_space_image(
                            client, image, ocr_space_api_key, ocr_space_engine
                        )
                        ocr_used = True
            elif not any(native_entries):
                if any(text.strip() for text in page_texts):
                    raise ValueError(
                        "The PDF contains text, but no numbered answer pairs were recognized. "
                        "Use formats such as 1. A, 1)ক, or ১.ক."
                    )
                raise OCRUnavailableError(
                    "This answer-key PDF appears to be scanned. Install Bengali and English Tesseract language data, "
                    "or configure OCR_SPACE_API_KEY to read scanned answer sheets."
                )

        all_entries: dict[int, list[dict[str, Any]]] = {}
        for text in page_texts:
            for entry in parse_answer_key_text(text):
                number = entry["question_number"]
                bucket = all_entries.setdefault(number, [])
                for label, index in zip(entry["option_labels"], entry["option_indices"]):
                    item = {"label": label, "index": index}
                    if item not in bucket:
                        bucket.append(item)

        entries = [
            {
                "question_number": number,
                "option_labels": [item["label"] for item in items],
                "option_indices": [item["index"] for item in items],
            }
            for number, items in sorted(all_entries.items())
        ]
        if not entries:
            raise ValueError(
                "No answer entries were found in this PDF. Use one answer per line, such as 1. A or ১)খ."
            )
        return {
            "entries": entries,
            "source_type": "pdf",
            "ocr_used": ocr_used,
            "ocr_engine": ocr_engine,
            "pages": len(document),
        }
    finally:
        document.close()
