from app.services.pdf_exam_parser import (
    _metadata,
    _option_segments,
    _option_segments,
    _parse_column_candidates,
    _normalise_candidate_numbers,
    _merge_candidate_sets,
)


def test_metadata_extracts_subject_chapter_set_and_duration():
    text = "পদার্থবিজ্ঞান ১ম পত্র — অধ্যায় ৪: নিউটনিয়ান বলবিদ্যা\nবিশ্ববিদ্যালয় ভর্তি পরীক্ষা মডেল টেস্ট — সেট ১\nমোট প্রশ্ন: ১০০ সময়: ৬০ মিনিট"
    data = _metadata(text)
    assert data["subject"] == "পদার্থবিজ্ঞান ১ম পত্র"
    assert data["chapter"] == "অধ্যায় ৪: নিউটনিয়ান বলবিদ্যা"
    assert data["set_name"] == "সেট ১"
    assert data["declared_question_count"] == 100
    assert data["duration_minutes"] == 60


def test_bengali_and_ocr_confused_option_markers_are_detected():
    assert _option_segments("(ক) প্রথম উত্তর") == ["প্রথম উত্তর"]
    assert _option_segments("€ক) প্রথম উত্তর") == ["প্রথম উত্তর"]
    assert _option_segments("খে) দ্বিতীয় উত্তর") == ["দ্বিতীয় উত্তর"]
    assert _option_segments("(*) 42") == ["42"]


def test_question_number_on_own_line_and_bengali_options_are_parsed():
    text = """
৪
কোন বিক্রিয়াটি সঠিক?
(ক) প্রথম উত্তর
(খ) দ্বিতীয় উত্তর
(গ) তৃতীয় উত্তর
(ঘ) চতুর্থ উত্তর
৫. পরের প্রশ্ন?
€ক) A
(খ) B
(গ) C
(ঘ) D
"""
    candidates = _parse_column_candidates(text)
    assert len(candidates) == 2
    assert candidates[0]["raw_number"] == 4
    assert candidates[0]["prompt"] == "কোন বিক্রিয়াটি সঠিক?"
    assert candidates[0]["options"] == ["প্রথম উত্তর", "দ্বিতীয় উত্তর", "তৃতীয় উত্তর", "চতুর্থ উত্তর"]
    assert candidates[1]["options"] == ["A", "B", "C", "D"]


def test_number_normalisation_repairs_ocr_99_between_10_and_12():
    candidates = [
        {"raw_number": 10, "prompt": "Q10?", "options": ["a", "b", "c", "d"]},
        {"raw_number": 99, "prompt": "Q11?", "options": ["a", "b", "c", "d"]},
        {"raw_number": 12, "prompt": "Q12?", "options": ["a", "b", "c", "d"]},
    ]
    normalized = _normalise_candidate_numbers(candidates, 10, 100)
    assert [item["number"] for item in normalized] == [10, 11, 12]


def test_merging_ocr_passes_preserves_full_option_order():
    first = [{"number": 48, "prompt": "Question?", "options": ["A", "C", "D"]}]
    second = [{"number": 48, "prompt": "Question?", "options": ["A", "B", "C", "D"]}]
    merged = _merge_candidate_sets([first, second])
    assert merged[0]["options"] == ["A", "B", "C", "D"]


def test_inline_bengali_option_labels_split_into_four_options():
    assert _option_segments("ক. প্রথম উত্তর খ. দ্বিতীয় উত্তর গ. তৃতীয় উত্তর ঘ. চতুর্থ উত্তর") == [
        "প্রথম উত্তর", "দ্বিতীয় উত্তর", "তৃতীয় উত্তর", "চতুর্থ উত্তর"
    ]


def test_inline_english_option_labels_split_into_four_options():
    assert _option_segments("A. First B. Second C. Third D. Fourth") == [
        "First", "Second", "Third", "Fourth"
    ]


def test_structure_score_reflects_option_completeness():
    from app.services.pdf_exam_parser import _structural_confidence

    prompt = "একটি পূর্ণাঙ্গ নমুনা প্রশ্ন কী?"
    score_four = _structural_confidence(prompt, ["এক", "দুই", "তিন", "চার"])
    score_three = _structural_confidence(prompt, ["এক", "দুই", "তিন"])
    score_two = _structural_confidence(prompt, ["এক", "দুই"])
    assert score_four > score_three > score_two
