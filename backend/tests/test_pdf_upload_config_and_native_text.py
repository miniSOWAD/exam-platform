import fitz
import pytest

from app.core.config import settings
from app.services import pdf_exam_parser
from app.services.pdf_exam_parser import (
    PDFOCRUnavailableError,
    _native_text_is_usable,
    parse_exam_pdf,
)


def test_pdf_upload_limit_is_separate_from_avatar_limit():
    assert settings.max_pdf_upload_mb >= 1
    assert settings.max_upload_bytes <= 307200


def test_bengali_native_text_with_question_markers_does_not_force_ocr():
    text = """পদার্থবিজ্ঞান ১ম পত্র — অধ্যায় ৪
সেট ১
১. একটি নমুনা প্রশ্ন কী?
A. প্রথম উত্তর
B. দ্বিতীয় উত্তর
C. তৃতীয় উত্তর
D. চতুর্থ উত্তর
"""
    assert _native_text_is_usable(text)


def test_blank_scanned_pdf_text_requires_ocr():
    assert not _native_text_is_usable("\n\n\x0c")


def test_digital_pdf_uses_native_text_without_ocr():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((40, 40), "Physics chapter 4 set 1\n1. What is force?\nA. Push\nB. Pull\nC. Mass\nD. Power", fontsize=11)
    raw = doc.tobytes()
    doc.close()
    result = parse_exam_pdf(raw, "sample.pdf")
    assert result["ocr_used"] is False
    assert result["question_count_detected"] == 1


def test_scanned_pdf_returns_actionable_error_without_cloud_ocr(monkeypatch):
    doc = fitz.open()
    doc.new_page()
    raw = doc.tobytes()
    doc.close()
    monkeypatch.setattr(pdf_exam_parser.shutil, "which", lambda _: None)
    monkeypatch.setattr(pdf_exam_parser, "_local_tesseract_ready", lambda: False)
    with pytest.raises(PDFOCRUnavailableError, match="OCR_SPACE_API_KEY"):
        parse_exam_pdf(raw, "scan.pdf")
