import fitz
import pytest

from app.core.config import settings
from app.services import pdf_exam_parser
from app.services.pdf_exam_parser import (
    OCRUnavailableError,
    _native_text_is_usable,
    parse_exam_pdf,
)


def test_pdf_upload_limit_is_separate_from_avatar_limit():
    assert settings.max_pdf_upload_mb >= 1
    assert settings.max_upload_bytes <= 307200


def test_native_text_helper_accepts_question_and_option_blocks():
    text = """পদার্থবিজ্ঞান ১ম পত্র — অধ্যায় ৪
সেট ১
1. একটি নমুনা প্রশ্ন কী?
ক. প্রথম উত্তর
খ. দ্বিতীয় উত্তর
গ. তৃতীয় উত্তর
ঘ. চতুর্থ উত্তর
"""
    assert _native_text_is_usable(text)


def test_blank_scanned_pdf_text_requires_ocr(monkeypatch):
    doc = fitz.open()
    doc.new_page()
    raw = doc.tobytes()
    doc.close()
    monkeypatch.setattr(pdf_exam_parser, "_tesseract_ready", lambda: False)
    with pytest.raises(OCRUnavailableError, match="OCR_SPACE_API_KEY"):
        parse_exam_pdf(raw, "blank-scan.pdf")


def test_supplied_hsc_biology_pdf_uses_native_text_and_detects_all_50_questions():
    fixture = __import__("pathlib").Path(__file__).parent / "fixtures" / "hsc_biology_50q.pdf"
    result = parse_exam_pdf(fixture.read_bytes(), fixture.name)

    assert result["ocr_used"] is False
    assert result["ocr_engine"] == "embedded-text"
    assert result["metadata"]["declared_question_count"] == 50
    assert result["question_count_detected"] == 50
    assert [question["number"] for question in result["questions"]] == list(range(1, 51))
    assert all(len(question["options"]) == 4 for question in result["questions"])
    assert not result["warnings"]


def test_scanned_pdf_returns_actionable_error_without_cloud_ocr(monkeypatch):
    doc = fitz.open()
    doc.new_page()
    raw = doc.tobytes()
    doc.close()
    monkeypatch.setattr(pdf_exam_parser, "_tesseract_ready", lambda: False)
    with pytest.raises(OCRUnavailableError, match="OCR_SPACE_API_KEY"):
        parse_exam_pdf(raw, "scan.pdf")


def test_supplied_two_column_chemistry_pdf_uses_native_text_and_detects_100_questions():
    fixture = __import__("pathlib").Path(__file__).parent / "fixtures" / "chemistry_two_column_100q.pdf"
    result = parse_exam_pdf(fixture.read_bytes(), fixture.name)

    assert result["ocr_used"] is False
    assert result["question_count_detected"] == 100
    assert [question["number"] for question in result["questions"]] == list(range(1, 101))
    assert sum(len(question["options"]) == 4 for question in result["questions"]) >= 99
