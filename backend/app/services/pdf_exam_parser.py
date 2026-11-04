"""Layout-aware PDF exam extraction for Bengali/English question papers.

The parser handles two-column papers, Bengali option labels (ক/খ/গ/ঘ),
question numbers split onto their own OCR line, and PDFs whose embedded
Unicode text layer is unreliable. Local Tesseract is preferred. FastAPI Cloud
can use OCR.Space Engine 3 when Tesseract or Bengali language data is absent.
Correct answers are never inferred.
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from io import BytesIO
from typing import Any

import fitz
import pytesseract
import httpx
from PIL import Image

BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
QUESTION_WITH_BODY_RE = re.compile(
    r"^\s*(?P<number>[০-৯0-9]{1,3})\s*[.।)]\s*(?P<body>\S.*)$"
)
QUESTION_NUMBER_ONLY_RE = re.compile(r"^\s*(?P<number>[০-৯0-9]{1,3})\s*[.।)]?\s*$")
# Parenthesized Bengali labels are the normal form in Bangladeshi exam papers.
# The generic one/two-character label also catches common OCR confusions such as
# (A), (1), (*) and (|). Chemical state labels like H2O(g) are not matched
# because the opening parenthesis is not preceded by whitespace.
OPTION_MARKER_RE = re.compile(
    r"(?<!\S)[(（\[]\s*(?P<label>[^\s()（）\[\]]{1,2})\s*[)）\]]\s*"
)
OPTION_BARE_MARKER_RE = re.compile(r"^\s*(?:[€£@])?\s*(?P<label>[কখগঘ](?:ে)?|[A-Da-d1-4])\s*[)৷।.]\s*", re.IGNORECASE)
# Digital Bengali PDFs often use ক. খ. গ. ঘ. rather than parenthesized labels.
# This also handles OCR output where two or more options share one text line.
OPTION_INLINE_BARE_RE = re.compile(r"(?<!\S)(?P<label>[কখগঘ](?:ে)?|[A-Da-d1-4])\s*[).৷।]\s*", re.IGNORECASE)


class OCRUnavailableError(RuntimeError):
    """No Bengali-capable OCR engine is configured for this deployment."""


class OCRServiceError(RuntimeError):
    """The configured external OCR provider failed."""


def _clean(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "")
    value = value.replace("\x0c", " ").replace("\u200b", "").replace("\ufeff", "")
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

    # Search the whole header, not just the second line: OCR can split the
    # university title and the set label across separate lines.
    set_match = re.search(r"(?:সেট|\bset)\s*([০-৯0-9A-Za-z]+)", text, re.IGNORECASE)
    set_name = None
    if set_match:
        token = _ascii_digits(set_match.group(1))
        set_name = f"সেট {set_match.group(1)}" if "সেট" in set_match.group(0) else f"Set {set_match.group(1)}"

    exam_title = second or None
    if exam_title and set_match:
        exam_title = re.split(r"(?:সেট|\bset)\s*", exam_title, maxsplit=1, flags=re.IGNORECASE)[0].strip(" _—–-:")
    if exam_title:
        exam_title = exam_title.replace("বিশৃবিদ্যালয়", "বিশ্ববিদ্যালয়").replace("বিশৃবিদ্যালয়", "বিশ্ববিদ্যালয়")

    count_match = re.search(
        r"(?:মোট\s*প্রশ্ন|total\s+questions|no\.?\s+of\s+questions)\s*[:：]?\s*(?P<count>[০-৯0-9]+)"
        r"|(?P<count2>[০-৯0-9]+)\s*টি\s*(?:বহুনির্বাচনি\s*)?প্রশ্ন",
        text,
        re.IGNORECASE,
    )
    count_token = (count_match.group("count") or count_match.group("count2")) if count_match else None
    duration_match = re.search(r"(?:সময়|সময়|time)\s*[:：]?\s*([০-৯0-9]+)\s*(?:মিনিট|minutes?|mins?)", text, re.IGNORECASE)
    marks_match = re.search(r"(?:পূর্ণমান|মোট\s*নম্বর|মোট\s*মার্ক|full\s+marks|total\s+marks|maximum\s+marks)\s*[:：]?\s*([০-৯0-9]+)", text, re.IGNORECASE)

    return {
        "subject": subject or None,
        "chapter": chapter or None,
        "exam_title": exam_title or None,
        "set_name": set_name,
        "declared_question_count": int(_ascii_digits(count_token)) if count_token else None,
        "duration_minutes": int(_ascii_digits(duration_match.group(1))) if duration_match else None,
        "total_marks": float(_ascii_digits(marks_match.group(1))) if marks_match else None,
    }


def _question_marker(line: str) -> tuple[int, str | None] | None:
    match = QUESTION_WITH_BODY_RE.match(line)
    if match:
        number = int(_ascii_digits(match.group("number")))
        body = _clean(match.group("body"))
        return number, body or None
    match = QUESTION_NUMBER_ONLY_RE.match(line)
    if match:
        return int(_ascii_digits(match.group("number"))), None
    return None


def _option_segments(line: str) -> list[str]:
    """Split option text whether labels are parenthesized or written inline as ক. / খ)."""
    line = _clean(line)
    if not line:
        return []

    matches = list(OPTION_MARKER_RE.finditer(line))
    if matches:
        # Multiple parenthesized labels indicate an inline options row.
        if len(matches) == 1 and line[:matches[0].start()].strip():
            return []
        values: list[str] = []
        for index, marker in enumerate(matches):
            start = marker.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            value = _clean(line[start:end]).strip(" ,;|")
            values.append(value)
        return values

    bare_matches = list(OPTION_INLINE_BARE_RE.finditer(line))
    if bare_matches:
        # Do not treat a label embedded in a sentence as an option. A single
        # bare marker is valid only at the start; multiple markers are valid
        # when the line begins with the first marker.
        if line[:bare_matches[0].start()].strip():
            return []
        values = []
        for index, marker in enumerate(bare_matches):
            start = marker.end()
            end = bare_matches[index + 1].start() if index + 1 < len(bare_matches) else len(line)
            values.append(_clean(line[start:end]).strip(" ,;|"))
        return values

    bare = OPTION_BARE_MARKER_RE.match(line)
    if bare:
        value = _clean(line[bare.end():]).strip(" ,;|")
        return [value] if value else [""]
    return []


def _is_question_like_continuation(line: str) -> bool:
    if len(line) < 12:
        return False
    return bool(re.search(r"[?？]|কোনটি|কোন\s|কত\??|কী\??|কেন\??|বিক্রিয়ায়|বিক্রিয়ায়", line, re.IGNORECASE))


def _parse_column_candidates(text: str) -> list[dict[str, Any]]:
    """Parse one column's OCR text into question candidates before numbering."""
    candidates: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_number: int | None = None
    option_mode = False

    def start(number: int | None, body: str | None = None) -> None:
        nonlocal current, option_mode
        current = {"raw_number": number, "prompt_lines": [body] if body else [], "options": []}
        option_mode = False

    def flush() -> None:
        nonlocal current, option_mode
        if current is not None:
            prompt = _clean(" ".join(current["prompt_lines"]))
            options = [_clean(x) for x in current["options"] if _clean(x)]
            # A stray OCR token such as "৯২৮" followed by one detached option
            # is not a usable question block. Drop it rather than shifting all
            # subsequent question numbers.
            if len(prompt) >= 3:
                candidates.append({"raw_number": current["raw_number"], "prompt": prompt, "options": options})
        current = None
        option_mode = False

    lines = [_clean(line) for line in text.splitlines()]
    for line in lines:
        if not line:
            continue

        marker = _question_marker(line)
        if marker:
            flush()
            number, body = marker
            if body is None:
                pending_number = number
            else:
                start(number, body)
                pending_number = None
            continue

        if pending_number is not None:
            # A number was OCR'd on its own line; the next non-option line is
            # the question stem. This is common with Bengali numerals.
            segments = _option_segments(line)
            if segments:
                start(pending_number, None)
                pending_number = None
            else:
                start(pending_number, line)
                pending_number = None
                continue

        segments = _option_segments(line)
        if segments:
            if current is None:
                # Ignore detached options until a question stem/number appears.
                continue
            option_mode = True
            for segment in segments:
                if len(current["options"]) < 4:
                    current["options"].append(segment)
                elif current["options"]:
                    current["options"][-1] = _clean(current["options"][-1] + " " + segment)
            continue

        if current is None:
            continue

        if option_mode and current["options"]:
            if len(current["options"]) >= 4 and _is_question_like_continuation(line):
                # Rescue a question number/stem that OCR missed after the
                # previous question's four options.
                flush()
                start(None, line)
            else:
                current["options"][-1] = _clean(current["options"][-1] + " " + line)
        else:
            current["prompt_lines"].append(line)

    flush()
    return candidates


def _normalise_candidate_numbers(candidates: list[dict[str, Any]], expected_start: int, declared_count: int | None) -> list[dict[str, Any]]:
    if not candidates:
        return []
    # A column normally contains 6-8 questions. A marker far outside this
    # local window is much more likely to be OCR noise than a real number.
    upper = expected_start + 12
    raw_numbers = [c.get("raw_number") for c in candidates]
    valid = [n if isinstance(n, int) and expected_start <= n <= upper else None for n in raw_numbers]
    result: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates):
        number = valid[index]
        previous = next((valid[j] for j in range(index - 1, -1, -1) if valid[j] is not None), None)
        following = next((valid[j] for j in range(index + 1, len(valid)) if valid[j] is not None), None)

        if number is None:
            # Recover a number that OCR omitted only when the surrounding
            # recognized numbers leave exactly one slot for this candidate.
            if previous is not None and following is not None and following == previous + 2:
                number = previous + 1
            elif previous is None and following == expected_start + 1:
                number = expected_start
            elif previous is not None and following is None and index == len(candidates) - 1:
                number = previous + 1
            elif previous is None and following is None and len(candidates) == 1:
                number = expected_start
            else:
                # Do not invent a sequential question for an unanchored OCR
                # fragment; that can duplicate the preceding question and
                # shift every later number.
                continue
        elif previous is not None and following is not None and following == previous + 2 and number != previous + 1:
            # Typical Bengali OCR confusion: e.g. ১১ is read as ৯৯ between ১০ and ১২.
            number = previous + 1

        if result and number <= result[-1]["number"]:
            # Drop duplicate/out-of-order OCR fragments instead of renumbering
            # them into a new, incorrect question.
            continue

        result.append({"number": number, "prompt": candidate.get("prompt", ""), "options": candidate.get("options", [])})
    return result


def _candidate_quality(question: dict[str, Any]) -> float:
    prompt = question.get("prompt", "")
    options = question.get("options", [])
    all_text = prompt + " " + " ".join(options)
    bengali_count = len(BENGALI_RE.findall(all_text))
    alnum_count = sum(ch.isalnum() for ch in all_text)
    return len(prompt) + min(len(options), 4) * 35 + bengali_count * 0.35 + min(alnum_count, 300) * 0.05


def _merge_candidate_sets(candidate_sets: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for candidates in candidate_sets:
        for candidate in candidates:
            number = candidate["number"]
            existing = merged.get(number)
            if existing is None:
                merged[number] = candidate
                continue
            best = candidate if _candidate_quality(candidate) > _candidate_quality(existing) else existing
            other = existing if best is candidate else candidate
            best_options = best.get("options", [])
            other_options = other.get("options", [])
            # Preserve option order. When one OCR pass found more options, use
            # that complete list; index-by-index merging can shift B/C/D when
            # the other pass missed option B.
            if len(other_options) > len(best_options):
                best_options = other_options
            elif len(other_options) == len(best_options):
                best_options = [
                    a if len(a) >= len(b) else b
                    for a, b in zip(best_options, other_options)
                ]
            prompt = best.get("prompt", "")
            if len(other.get("prompt", "")) > len(prompt):
                prompt = other["prompt"]
            merged[number] = {"number": number, "prompt": prompt, "options": best_options[:4]}
    return [merged[number] for number in sorted(merged)]


def _column_rectangles(page: fitz.Page) -> list[fitz.Rect]:
    width, height = page.rect.width, page.rect.height
    divider_x = None
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "re":
                rect = item[1]
                if rect.height > height * 0.08 and rect.width < 4 and abs(rect.x0 - width / 2) < width * 0.12:
                    divider_x = (rect.x0 + rect.x1) / 2
                    break
            elif item[0] == "l":
                a, b = item[1], item[2]
                if abs(a.x - b.x) < 2 and abs(a.y - b.y) > height * 0.08 and abs(a.x - width / 2) < width * 0.12:
                    divider_x = a.x
                    break
        if divider_x is not None:
            break

    if divider_x is None:
        return [fitz.Rect(22, 22, width - 22, height - 28)]
    return [
        fitz.Rect(22, 22, divider_x - 5, height - 28),
        fitz.Rect(divider_x + 5, 22, width - 22, height - 28),
    ]



def _native_page_texts(document: fitz.Document) -> tuple[list[str], str]:
    """Extract the embedded text layer in visual reading order, excluding page furniture.

    The first page's header is returned separately for metadata. Pages with a
    genuine two-column text layout are split using text-block x positions, even
    when the PDF has no visible divider line.
    """
    page_texts: list[str] = []
    metadata_text = ""

    for page_index, page in enumerate(document):
        page_height = page.rect.height
        page_width = page.rect.width
        blocks = [
            block for block in page.get_text("blocks")
            if len(block) > 6 and block[6] == 0
            and block[1] > 35 and block[3] < page_height - 38
        ]

        question_blocks = []
        for block in blocks:
            nonempty = [_clean(line) for line in block[4].splitlines() if _clean(line)]
            if nonempty and _question_marker(nonempty[0]):
                question_blocks.append(block)

        if question_blocks:
            first_question_y = min(block[1] for block in question_blocks)
            content_top = max(35, first_question_y - 3)
            content_bottom = page_height - 38
        else:
            # Keep a conservative fallback for PDFs whose question number is
            # separated from the stem in a way that cannot be located by blocks.
            first_question_y = None
            content_top = 40
            content_bottom = page_height - 38

        if page_index == 0 and first_question_y is not None:
            header_rect = fitz.Rect(18, 40, page_width - 18, max(41, first_question_y - 4))
            metadata_text = page.get_text("text", clip=header_rect, sort=True)

        content_blocks = [
            block for block in blocks
            if block[1] >= content_top and block[3] <= content_bottom
        ]

        # Start with an explicit vector divider when the PDF contains one.
        columns = _column_rectangles(page)
        if len(columns) == 1 and len(content_blocks) >= 8:
            # Detect an unruled two-column layout from a clear gap between the
            # left and right text-block origins. Single-column indents are only
            # a few points apart and will not pass this threshold.
            x_values = sorted(block[0] for block in content_blocks)
            gaps = [(x_values[i + 1] - x_values[i], x_values[i], x_values[i + 1])
                    for i in range(len(x_values) - 1)]
            if gaps:
                gap, left_edge, right_edge = max(gaps, key=lambda item: item[0])
                left_count = sum(1 for block in content_blocks if block[0] <= left_edge)
                right_count = sum(1 for block in content_blocks if block[0] >= right_edge)
                if gap >= page_width * 0.12 and left_count >= 3 and right_count >= 3:
                    divider_x = (left_edge + right_edge) / 2
                    columns = [
                        fitz.Rect(18, content_top, divider_x - 5, content_bottom),
                        fitz.Rect(divider_x + 5, content_top, page_width - 18, content_bottom),
                    ]

        if len(columns) == 1:
            columns = [fitz.Rect(18, content_top, page_width - 18, content_bottom)]
        else:
            columns = [
                fitz.Rect(rect.x0, content_top, rect.x1, content_bottom)
                for rect in columns
            ]

        for rect in columns:
            text = page.get_text("text", clip=rect, sort=True)
            # Remove a footer if it falls inside a page with an unusual crop.
            kept_lines = [
                line for line in text.splitlines()
                if not re.search(r"(?:পৃষ্ঠা|page)\s*[০-৯0-9]+\s*$", _clean(line), re.IGNORECASE)
            ]
            cleaned = "\n".join(kept_lines).strip()
            if cleaned:
                page_texts.append(cleaned)

    return page_texts, metadata_text


def _native_text_is_usable(text: str) -> bool:
    """Return true when an embedded text sample contains parseable question blocks."""
    candidates = _parse_column_candidates(text or "")
    return any(
        len(candidate.get("prompt", "")) >= 8
        and (len(candidate.get("options", [])) >= 2 or len(candidate.get("prompt", "")) >= 30)
        for candidate in candidates
    )


def _native_questions_are_usable(questions: list[dict[str, Any]], declared_count: int | None) -> bool:
    """Reject damaged embedded text layers, but accept clean MCQ and short-answer PDFs."""
    if not questions:
        return False
    valid = [question for question in questions if len(question.get("prompt", "").strip()) >= 8]
    if not valid:
        return False
    if declared_count:
        minimum = max(1, int(declared_count * 0.60))
        if len(valid) < minimum:
            return False
    with_options = sum(1 for question in valid if len(question.get("options", [])) >= 2)
    short_answers = sum(1 for question in valid if not question.get("options"))
    return with_options >= max(1, int(len(valid) * 0.50)) or short_answers == len(valid)

def _render(page: fitz.Page, rect: fitz.Rect, dpi: int) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=rect, alpha=False)
    return Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")


def _tesseract_ready() -> bool:
    if not shutil.which("tesseract"):
        return False
    try:
        languages = set(pytesseract.get_languages(config=""))
        return "ben" in languages and "eng" in languages
    except Exception:
        return False


def _ocr_tesseract(image: Image.Image, psm: int) -> str:
    try:
        return pytesseract.image_to_string(image, lang="ben+eng", config=f"--oem 1 --psm {psm}")
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as exc:
        raise OCRUnavailableError(
            "Local Tesseract OCR could not process this PDF. Install the Bengali and English language data, "
            "or configure OCR_SPACE_API_KEY for scanned PDFs."
        ) from exc


def _prepend_missing_first_question(text: str, page: fitz.Page, rect: fitz.Rect, expected_start: int, dpi: int) -> str:
    existing = [_question_marker(_clean(line)) for line in text.splitlines()]
    if any(marker and marker[0] == expected_start for marker in existing):
        return text
    # OCR engines sometimes skip the first stem at the top of a column while
    # still reading its four options. Re-read a narrow top strip to recover it.
    strip = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y0 + 95, rect.y1))
    if strip.height < 20:
        return text
    top_text = _ocr_tesseract(_render(page, strip, max(dpi, 300)), 11)
    for line in top_text.splitlines():
        marker = _question_marker(_clean(line))
        if marker and marker[0] == expected_start:
            return line + "\n" + text
    return text


def _ocr_local_columns(document: fitz.Document, dpi: int, declared_count: int | None) -> tuple[list[str], str]:
    page_texts: list[str] = []
    expected_start = 1
    for page_index, page in enumerate(document):
        columns = _column_rectangles(page)
        # Metadata is read from the first-page header separately; question
        # crops start lower to avoid mixing the header with the two columns.
        for column_index, rect in enumerate(columns):
            y0 = 90 if page_index == 0 else 25
            if page_index == 0 and len(columns) == 2 and column_index == 1:
                y0 = 90
            question_rect = fitz.Rect(rect.x0, max(rect.y0, y0), rect.x1, rect.y1)
            image = _render(page, question_rect, dpi)
            text11 = _ocr_tesseract(image, 11)
            text11 = _prepend_missing_first_question(text11, page, question_rect, expected_start, dpi)
            candidates11 = _normalise_candidate_numbers(_parse_column_candidates(text11), expected_start, declared_count)

            raw_numbers = [c.get("raw_number") for c in _parse_column_candidates(text11)]
            raw_candidates = _parse_column_candidates(text11)
            damaged_implicit_stem = any(
                candidate.get("raw_number") is None
                and re.match(r"^\s*[0-9০-৯]{2,4}[,.)]", candidate.get("prompt", ""))
                for candidate in raw_candidates
            )
            sequence_problem = (
                not candidates11
                or any(len(q.get("options", [])) < 4 for q in candidates11)
                or any(not q.get("prompt") for q in candidates11)
                or damaged_implicit_stem
                or any(isinstance(n, int) and (n < expected_start or n > expected_start + 12) for n in raw_numbers)
                or any(isinstance(a, int) and isinstance(b, int) and b > a + 1 for a, b in zip(raw_numbers, raw_numbers[1:]))
            )
            candidate_sets = [candidates11]
            if sequence_problem:
                text3 = _ocr_tesseract(image, 3)
                text3 = _prepend_missing_first_question(text3, page, question_rect, expected_start, dpi)
                candidates3 = _normalise_candidate_numbers(_parse_column_candidates(text3), expected_start, declared_count)
                candidate_sets.append(candidates3)

            merged = _merge_candidate_sets(candidate_sets)
            if any(len(q.get("options", [])) < 4 for q in merged):
                # A third segmentation pass is reserved for incomplete blocks;
                # it costs extra CPU only on columns where options are missing.
                text6 = _ocr_tesseract(_render(page, question_rect, max(dpi, 280)), 6)
                text6 = _prepend_missing_first_question(text6, page, question_rect, expected_start, dpi)
                candidates6 = _normalise_candidate_numbers(_parse_column_candidates(text6), expected_start, declared_count)
                candidate_sets.append(candidates6)
                merged = _merge_candidate_sets(candidate_sets)
            if merged:
                page_texts.append("\n".join(
                    [f"{q['number']}. {q['prompt']}\n" + "\n".join(f"({chr(0x0995 + i)}) {opt}" for i, opt in enumerate(q['options'])) for q in merged]
                ))
                expected_start = max(expected_start, max(q["number"] for q in merged) + 1)
            else:
                page_texts.append("")
    return page_texts, "tesseract-ben+eng"


def _make_page_composite(page: fitz.Page, page_index: int, dpi: int) -> Image.Image:
    columns = _column_rectangles(page)
    images: list[Image.Image] = []
    if page_index == 0:
        header_rect = fitz.Rect(18, 12, page.rect.width - 18, min(130, page.rect.height))
        images.append(_render(page, header_rect, dpi))
    for column_index, rect in enumerate(columns):
        y0 = 90 if page_index == 0 else 25
        if page_index == 0 and len(columns) == 2 and column_index == 1:
            y0 = 90
        images.append(_render(page, fitz.Rect(rect.x0, max(rect.y0, y0), rect.x1, rect.y1), dpi))
    width = max(image.width for image in images)
    gap = max(32, int(dpi * 0.12))
    height = sum(image.height for image in images) + gap * (len(images) - 1)
    composite = Image.new("RGB", (width, height), "white")
    y = 0
    for image in images:
        composite.paste(image, (0, y))
        y += image.height + gap
    return composite


def _ocr_space_image(client: httpx.Client, image: Image.Image, api_key: str, engine: int) -> str:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=84, optimize=True)
    files = {"file": ("exam-page.jpg", buffer.getvalue(), "image/jpeg")}
    data = {
        "language": "auto",
        "OCREngine": str(engine),
        "isOverlayRequired": "false",
        "scale": "true",
        "filetype": "JPG",
    }
    try:
        response = client.post(
            "https://api.ocr.space/parse/image",
            headers={"apikey": api_key},
            data=data,
            files=files,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise OCRServiceError(
            f"OCR.Space rejected the page (HTTP {status}). Check the API key, account quota, and image-size limit."
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise OCRServiceError(
            f"Could not reach or read the OCR.Space response ({type(exc).__name__}). Check outbound network access and OCR configuration."
        ) from exc

    if payload.get("IsErroredOnProcessing"):
        errors = payload.get("ErrorMessage") or payload.get("ErrorDetails") or "OCR provider could not process this page."
        if isinstance(errors, list):
            errors = "; ".join(str(item) for item in errors)
        raise OCRServiceError(str(errors))
    parsed = payload.get("ParsedResults") or []
    text = "\n".join(item.get("ParsedText", "") for item in parsed)
    if not text.strip():
        raise OCRServiceError("OCR provider returned no readable text for a page.")
    return text


def _ocr_remote_columns(document: fitz.Document, dpi: int, api_key: str, engine: int, timeout: int) -> tuple[list[str], str]:
    page_texts: list[str] = []
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=20)) as client:
        for page_index, page in enumerate(document):
            composite = _make_page_composite(page, page_index, dpi)
            page_texts.append(_ocr_space_image(client, composite, api_key, engine))
    return page_texts, f"ocr.space-engine-{engine}"


def _structural_confidence(prompt: str, options: list[str]) -> float:
    """Estimate parse-structure completeness; this is not OCR character accuracy."""
    score = 0.25
    prompt_length = len(_clean(prompt))
    if prompt_length >= 12:
        score += 0.20
    elif prompt_length >= 6:
        score += 0.10

    option_count = len(options)
    if option_count == 4:
        score += 0.25
    elif option_count == 3:
        score += 0.18
    elif option_count == 2:
        score += 0.12
    elif option_count == 1:
        score += 0.06

    if options:
        nonempty = sum(1 for option in options if _clean(option))
        score += 0.10 * (nonempty / len(options))
        normalized = [re.sub(r"\s+", " ", _clean(option)).casefold() for option in options]
        if len(set(normalized)) == len(normalized):
            score += 0.05

    if _clean(prompt).endswith(("?", "？", "।")):
        score += 0.05
    return round(min(0.95, max(0.35, score)), 2)


def _parse_question_pages(page_texts: list[str], declared_count: int | None) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    expected_start = 1
    for text in page_texts:
        candidates = _normalise_candidate_numbers(_parse_column_candidates(text), expected_start, declared_count)
        for candidate in candidates:
            options = candidate.get("options", [])[:4]
            prompt = _clean(candidate.get("prompt", ""))
            if not prompt:
                continue
            kind = "mcq" if len(options) >= 2 else "short_answer"
            if len(options) == 2 and re.search(r"সত্য|মিথ্যা|true|false", " ".join(options), re.IGNORECASE):
                kind = "true_false"
            warnings: list[str] = []
            if len(options) == 0:
                warnings.append("No options detected. Confirm this is a short-answer question or repair the OCR text.")
            elif len(options) < 4 and kind == "mcq":
                warnings.append(f"Only {len(options)} options were detected; check whether an option was missed by OCR.")
            if len(prompt) < 12:
                warnings.append("Question text is unusually short; check the original PDF.")
            confidence = _structural_confidence(prompt, options)
            questions.append({
                "number": candidate["number"],
                "kind": kind,
                "prompt": prompt,
                "options": [{"key": chr(ord("A") + i), "text": value} for i, value in enumerate(options)],
                "answer_key": {},
                "marks": 1,
                "negative_marks": 0,
                "confidence": confidence,
                "needs_review": True,
                "answer_key_missing": True,
                "warnings": warnings,
            })
        if candidates:
            expected_start = max(expected_start, max(q["number"] for q in candidates) + 1)

    # Remove duplicate question numbers created by OCR overlaps. Keep the
    # candidate with the most complete stem/options.
    unique: dict[int, dict[str, Any]] = {}
    for question in questions:
        existing = unique.get(question["number"])
        score = len(question["prompt"]) + 40 * len(question["options"])
        old_score = len(existing["prompt"]) + 40 * len(existing["options"]) if existing else -1
        if score > old_score:
            unique[question["number"]] = question
    return [unique[n] for n in sorted(unique)]


def parse_exam_pdf(
    raw: bytes,
    filename: str,
    max_pages: int = 30,
    dpi: int = 240,
    ocr_space_api_key: str = "",
    ocr_space_engine: int = 3,
    ocr_space_timeout_seconds: int = 90,
) -> dict[str, Any]:
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise ValueError("The uploaded file is not a readable PDF.") from exc

    try:
        if document.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported. Upload an unlocked PDF.")
        page_count = len(document)
        if page_count > max_pages:
            raise ValueError(f"This PDF has {page_count} pages; the current limit is {max_pages} pages.")

        native_page_texts, native_header = _native_page_texts(document)
        native_metadata = _metadata(native_header)
        native_questions = _parse_question_pages(native_page_texts, native_metadata["declared_question_count"])

        if _native_questions_are_usable(native_questions, native_metadata["declared_question_count"]):
            page_texts = native_page_texts
            metadata_text = native_header
            metadata = native_metadata
            questions = native_questions
            ocr_used = False
            ocr_engine = "embedded-text"
        else:
            ocr_used = True
            metadata_text = native_header
            if _tesseract_ready():
                # OCR the heading only when the embedded header is too sparse.
                if not metadata_text.strip():
                    header_rect = fitz.Rect(18, 12, document[0].rect.width - 18, min(150, document[0].rect.height))
                    metadata_text = _ocr_tesseract(_render(document[0], header_rect, max(dpi, 280)), 11)
                page_texts, ocr_engine = _ocr_local_columns(
                    document, dpi, native_metadata["declared_question_count"]
                )
            elif ocr_space_api_key:
                page_texts, ocr_engine = _ocr_remote_columns(
                    document, dpi, ocr_space_api_key, ocr_space_engine, ocr_space_timeout_seconds
                )
                if not metadata_text.strip():
                    metadata_text = page_texts[0] if page_texts else ""
            else:
                raise OCRUnavailableError(
                    "This PDF does not contain a usable question text layer, and Bengali OCR is not configured. "
                    "Install Tesseract with ben+eng language data or configure OCR_SPACE_API_KEY, then redeploy."
                )
            metadata = _metadata(metadata_text)
            questions = _parse_question_pages(page_texts, metadata["declared_question_count"])

        if ocr_used:
            for question in questions:
                question["confidence"] = round(max(0.35, question["confidence"] - 0.08), 2)
        if metadata["declared_question_count"] and metadata["declared_question_count"] != len(questions):
            for question in questions:
                question["confidence"] = round(max(0.35, question["confidence"] - 0.08), 2)
    finally:
        document.close()

    warnings: list[str] = []
    if ocr_used:
        warnings.append("OCR was used. Review Bengali wording, chemical formulas, subscripts, and symbols against the original PDF before publishing.")
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
    for question in questions:
        if question["confidence"] < 0.7:
            warnings.append(f"Question {question['number']} needs manual review.")

    return {
        "filename": filename,
        "pages": page_count,
        "ocr_used": ocr_used,
        "ocr_engine": ocr_engine,
        "metadata": metadata,
        "questions": questions,
        "question_count_detected": len(questions),
        "warnings": list(dict.fromkeys(warnings)),
        "extraction_note": "Extracted content is a draft. Review all question text and options against the original PDF before creating an exam. The structure score reflects question/option completeness, not a verified probability of character-level OCR accuracy. Correct answers are never inferred.",
    }

