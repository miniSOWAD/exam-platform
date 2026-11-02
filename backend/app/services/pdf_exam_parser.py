"""Low-cost PDF exam parser: PyMuPDF text extraction plus local Tesseract OCR.

Bangla PDFs often use legacy embedded fonts whose Unicode text layer is corrupt.
For Bengali documents we OCR rendered pages to recover readable Bangla text.
Extracted answers are never guessed; the answer key stays empty unless supplied.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

import fitz
import pytesseract
from PIL import Image
from io import BytesIO

BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
QUESTION_MARKER_RE = re.compile(
    r"^\s*(?P<token>[০-৯0-9]{1,3}|[>vVbBdD][a-zA-Z0-9]{0,2})\s*[.,।)]\s+(?P<body>\S.*)$"
)
OPTION_MARKER_RE = re.compile(
    r"(?<!\S)(?:(?P<letter>[A-D])\s*[.,)]\s*|(?P<digit>[0-4][০-৯]?|[০-৯])\s*[.,)]{1,2}\s+|(?P<ocr>[\[|])\s*[.)]{1,2}\s+)",
    re.IGNORECASE,
)


def _clean(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "")
    value = value.replace("\x0c", " ").replace("\u200b", "")
    return re.sub(r"[ \t]+", " ", value).strip()


def _ascii_digits(value: str) -> str:
    return value.translate(BN_DIGITS)


def _metadata(text: str) -> dict[str, Any]:
    lines = [_clean(x) for x in text.splitlines() if _clean(x)]
    first = lines[0] if lines else ""
    second = lines[1] if len(lines) > 1 else ""

    chapter_start = re.search(r"অধ্যা[য়য়]|\bchapter\b", first, re.IGNORECASE)
    subject = first
    chapter = None
    if chapter_start:
        chapter = first[chapter_start.start():].strip(" _—–-:")
        subject = first[:chapter_start.start()].strip(" _—–-:")

    set_match = re.search(r"(?:সেট|\bset)\s*([০-৯0-9A-Za-z]+)", second, re.IGNORECASE)
    set_name = f"সেট {set_match.group(1)}" if set_match and "সেট" in set_match.group(0) else (f"Set {set_match.group(1)}" if set_match else None)
    exam_title = second
    if set_match:
        exam_title = re.split(r"(?:সেট|\bset)\s*", second, maxsplit=1, flags=re.IGNORECASE)[0].strip(" _—–-:")
    exam_title = exam_title.replace("বিশৃবিদ্যালয়", "বিশ্ববিদ্যালয়").replace("বিশৃবিদ্যালয়", "বিশ্ববিদ্যালয়")

    count_match = re.search(r"(?:মোট\s*প্রশ্ন|total\s+questions|no\.?\s+of\s+questions)\s*[:：]?\s*([০-৯0-9]+)", text, re.IGNORECASE)
    duration_match = re.search(r"(?:সময়|time)\s*[:：]?\s*([০-৯0-9]+)\s*(?:মিনিট|minutes?|mins?)", text, re.IGNORECASE)
    marks_match = re.search(r"(?:পূর্ণমান|মোট\s*নম্বর|মোট\s*মার্ক|full\s+marks|total\s+marks|maximum\s+marks)\s*[:：]?\s*([০-৯0-9]+)", text, re.IGNORECASE)

    return {
        "subject": subject or None,
        "chapter": chapter or None,
        "exam_title": exam_title or None,
        "set_name": set_name,
        "declared_question_count": int(_ascii_digits(count_match.group(1))) if count_match else None,
        "duration_minutes": int(_ascii_digits(duration_match.group(1))) if duration_match else None,
        "total_marks": float(_ascii_digits(marks_match.group(1))) if marks_match else None,
    }


def _looks_like_option_line(line: str) -> bool:
    matches = list(OPTION_MARKER_RE.finditer(line))
    if len(matches) >= 2:
        return True
    return bool(re.match(r"^\s*[A-D]\s*[.,)]", line, re.IGNORECASE))


def _question_marker(line: str, expected_number: int | None = None) -> tuple[int | None, str] | None:
    if _looks_like_option_line(line):
        return None
    match = QUESTION_MARKER_RE.match(line)
    if not match:
        return None
    token = _ascii_digits(match.group("token"))
    number = int(token) if token.isdigit() else None
    body = _clean(match.group("body"))
    if len(body) < 5:
        return None
    # OCR often reads B/C/D option labels as 3/0/1. Those single-digit
    # markers are treated as question numbers only when they match the
    # next expected number in sequence.
    if number is not None and number <= 4 and expected_number is not None and number != expected_number:
        return None
    return number, body


def _extract_options_and_prompt(lines: list[str]) -> tuple[str, list[dict[str, str]], list[str]]:
    prompt_lines: list[str] = []
    options: list[dict[str, str]] = []
    warnings: list[str] = []
    option_mode = False

    for raw_line in lines:
        line = _clean(raw_line)
        if not line:
            continue
        matches = list(OPTION_MARKER_RE.finditer(line))
        is_option_line = bool(matches) and (len(matches) >= 2 or bool(re.match(r"^\s*(?:[A-D]|[0-4][০-৯]?|[০-৯])\s*[.,)]", line, re.IGNORECASE)) or option_mode)

        if is_option_line:
            option_mode = True
            for index, marker in enumerate(matches):
                start = marker.end()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
                option_text = _clean(line[start:end]).strip(" ,;|")
                if option_text:
                    key = chr(ord("A") + len(options))
                    if len(options) < 4:
                        options.append({"key": key, "text": option_text})
                    else:
                        options[-1]["text"] += " " + option_text
            continue

        if option_mode and options:
            # OCR may wrap an option onto a continuation line.
            options[-1]["text"] = _clean(options[-1]["text"] + " " + line)
        else:
            prompt_lines.append(line)

    prompt = _clean(" ".join(prompt_lines))
    if len(options) == 1:
        warnings.append("Only one option was detected; check the OCR result and question type.")
    if len(options) == 0:
        warnings.append("No options detected. Confirm this is a short-answer question or repair the OCR text.")
    if len(options) == 3:
        warnings.append("Only three options were detected; check whether an option was missed by OCR.")
    if len(options) > 4:
        warnings.append("More than four option fragments were detected; check the OCR result.")
    return prompt, options, warnings


def _parse_question_pages(page_texts: list[str], declared_count: int | None) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    current_number = 0
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines, current_number
        if not current_lines:
            return
        prompt, options, warnings = _extract_options_and_prompt(current_lines)
        if prompt:
            kind = "mcq" if len(options) >= 2 else "short_answer"
            if len(options) == 2 and re.search(r"সত্য|মিথ্যা|true|false", " ".join(x["text"] for x in options), re.IGNORECASE):
                kind = "true_false"
            elif len(options) == 2:
                warnings.append("Only two options were detected; verify whether additional options are missing.")
            questions.append({
                "number": current_number or len(questions) + 1,
                "kind": kind,
                "prompt": prompt,
                "options": options,
                "answer_key": {},
                "marks": 1,
                "negative_marks": 0,
                "confidence": 0.80 if len(prompt) > 12 and len(options) == 4 else (0.62 if len(options) == 3 else 0.45),
                "needs_review": True,
                "answer_key_missing": True,
                "warnings": warnings,
            })
        current_lines = []

    for page_text in page_texts:
        lines = [_clean(line) for line in page_text.splitlines()]
        lines = [line for line in lines if line]
        first_marker_index = None
        for i, line in enumerate(lines):
            candidate = _question_marker(line, current_number + 1 if current_number else None)
            if candidate:
                first_marker_index = i
                break
        if first_marker_index is None:
            continue

        first_on_page = True
        for line in lines[first_marker_index:]:
            expected = current_number + 1 if current_number else 1
            marker = _question_marker(line, expected)
            if marker:
                flush()
                detected_number, body = marker
                if first_on_page:
                    if detected_number and detected_number > current_number and detected_number <= (declared_count or 1000):
                        current_number = detected_number
                    else:
                        current_number = current_number + 1 if current_number else 1
                    first_on_page = False
                else:
                    # Within a page use sequential numbering; OCR occasionally
                    # confuses a question number with a unit or option label.
                    current_number += 1
                current_lines = [body]
            elif current_lines:
                current_lines.append(line)
        flush()

    for i, question in enumerate(questions):
        if i and question["number"] != questions[i - 1]["number"] + 1:
            question["warnings"].append("Question numbering is not consecutive; verify page boundaries and OCR.")
    return questions


def parse_exam_pdf(raw: bytes, filename: str, max_pages: int = 30, dpi: int = 240) -> dict[str, Any]:
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise ValueError("The uploaded file is not a readable PDF.") from exc
    if document.is_encrypted:
        document.close()
        raise ValueError("Password-protected PDFs are not supported. Upload an unlocked PDF.")
    page_count = len(document)
    if page_count > max_pages:
        document.close()
        raise ValueError(f"This PDF has {page_count} pages; the current limit is {max_pages} pages.")

    native_text = "\n".join(page.get_text("text") for page in document)
    has_bengali = bool(BENGALI_RE.search(native_text))
    page_texts: list[str] = []
    ocr_used = False
    # A blank text layer is typical of scanned/image-only PDFs; OCR those too.
    use_ocr = has_bengali or len(native_text.strip()) < 100
    if use_ocr:
        ocr_used = True
        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
            with Image.open(BytesIO(pix.tobytes("png"))) as image:
                text = pytesseract.image_to_string(image, lang="ben+eng", config="--oem 1 --psm 3")
            page_texts.append(text)
    else:
        page_texts = [page.get_text("text") for page in document]
    document.close()

    combined_text = "\n".join(page_texts)
    metadata = _metadata(combined_text)
    questions = _parse_question_pages(page_texts, metadata["declared_question_count"])
    warnings: list[str] = []
    if not metadata["subject"]:
        warnings.append("Could not confidently identify the subject from the PDF heading.")
    if not metadata["chapter"]:
        warnings.append("Chapter was not detected. Enter it manually if applicable.")
    if not metadata["set_name"]:
        warnings.append("Set name was not detected. Enter it manually if applicable.")
    if metadata["declared_question_count"] and metadata["declared_question_count"] != len(questions):
        warnings.append(f"The PDF declares {metadata['declared_question_count']} questions, but {len(questions)} question blocks were detected. Review missing or merged questions.")
    if not questions:
        warnings.append("No structured questions were detected. This PDF may need a different OCR layout or manual entry.")
    for q in questions:
        if q["confidence"] < 0.7:
            warnings.append(f"Question {q['number']} needs manual review.")

    return {
        "filename": filename,
        "pages": page_count,
        "ocr_used": ocr_used,
        "metadata": metadata,
        "questions": questions,
        "question_count_detected": len(questions),
        "warnings": list(dict.fromkeys(warnings)),
        "extraction_note": "Extracted content is a draft. Review all question text and options before creating an exam. Correct answers are not inferred when the PDF does not provide an answer key.",
    }
