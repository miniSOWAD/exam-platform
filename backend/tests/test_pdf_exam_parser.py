from app.services.pdf_exam_parser import _metadata, _parse_question_pages

def test_metadata_extracts_subject_chapter_set_and_duration():
    text = "পদার্থবিজ্ঞান ১ম পত্র — অধ্যায় ৪: নিউটনিয়ান বলবিদ্যা\nবিশ্ববিদ্যালয় ভর্তি পরীক্ষা মডেল টেস্ট — সেট ১\nমোট প্রশ্ন: ১০০ সময়: ৬০ মিনিট"
    data = _metadata(text)
    assert data["subject"] == "পদার্থবিজ্ঞান ১ম পত্র"
    assert data["chapter"] == "অধ্যায় ৪: নিউটনিয়ান বলবিদ্যা"
    assert data["set_name"] == "সেট ১"
    assert data["declared_question_count"] == 100
    assert data["duration_minutes"] == 60

def test_question_parser_keeps_options_and_does_not_invent_answers():
    pages = ["""১. একটি প্রশ্ন কী?
A. প্রথম
B. দ্বিতীয়
C. তৃতীয়
D. চতুর্থ
২. আরেকটি প্রশ্ন?
A. হ্যাঁ B. না C. হতে পারে D. কোনোটিই নয়"""]
    questions = _parse_question_pages(pages, 2)
    assert len(questions) == 2
    assert [q["key"] for q in questions[0]["options"]] == ["A", "B", "C", "D"]
    assert questions[0]["answer_key"] == {}
