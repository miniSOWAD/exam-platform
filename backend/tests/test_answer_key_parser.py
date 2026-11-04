import fitz
import pytest

from app.services.answer_key_parser import parse_answer_key_text, extract_answer_key_file


def test_parse_inline_bengali_digits_and_option_letters():
    parsed = parse_answer_key_text("১.ক ২.খ ৩.গ ৪.ঘ")
    assert [item["question_number"] for item in parsed] == [1, 2, 3, 4]
    assert [item["option_indices"] for item in parsed] == [[0], [1], [2], [3]]
    assert [item["option_labels"] for item in parsed] == [["ক"], ["খ"], ["গ"], ["ঘ"]]


def test_parse_parenthesis_and_line_by_line_formats():
    parsed = parse_answer_key_text("১)ক\n২)খ\n3)C\n4)D")
    assert [item["question_number"] for item in parsed] == [1, 2, 3, 4]
    assert [item["option_indices"] for item in parsed] == [[0], [1], [2], [3]]


def test_parse_english_digits_and_option_labels_with_spaces():
    parsed = parse_answer_key_text("1. A, 2. B; 3 - C | 4 D")
    assert [item["option_indices"] for item in parsed] == [[0], [1], [2], [3]]


def test_repeated_question_number_keeps_multiple_distinct_answers_for_multiple_mcq():
    parsed = parse_answer_key_text("1.A 1.C 2.B")
    assert parsed[0]["question_number"] == 1
    assert parsed[0]["option_indices"] == [0, 2]


def test_duplicate_identical_answer_is_deduplicated():
    parsed = parse_answer_key_text("1.A 1.A 2.B")
    assert parsed[0]["option_indices"] == [0]


def test_txt_upload_is_read_without_ocr():
    result = extract_answer_key_file(b"1. A\n2. B", "answers.txt")
    assert result["source_type"] == "txt"
    assert result["ocr_used"] is False
    assert result["entries"][1]["option_indices"] == [1]


def test_native_text_pdf_upload_is_read_without_ocr():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "1. A  2. B  3. C  4. D")
    raw = document.tobytes()
    document.close()

    result = extract_answer_key_file(raw, "answers.pdf")
    assert result["source_type"] == "pdf"
    assert result["ocr_used"] is False
    assert len(result["entries"]) == 4


def test_no_answer_tokens_returns_actionable_error():
    with pytest.raises(ValueError, match="No answer entries"):
        extract_answer_key_file(b"This is not an answer key", "answers.txt")


def test_scanned_pdf_uses_local_ocr_when_available(monkeypatch):
    from app.services import answer_key_parser

    document = fitz.open()
    document.new_page()
    raw = document.tobytes()
    document.close()

    monkeypatch.setattr(answer_key_parser, "_tesseract_ready", lambda: True)
    monkeypatch.setattr(answer_key_parser, "_render", lambda page, rect, dpi: object())
    monkeypatch.setattr(answer_key_parser, "_ocr_tesseract", lambda image, psm: "1. A 2. B")

    result = answer_key_parser.extract_answer_key_file(raw, "scanned-answers.pdf")
    assert result["ocr_used"] is True
    assert result["ocr_engine"] == "tesseract-ben+eng"
    assert len(result["entries"]) == 2
