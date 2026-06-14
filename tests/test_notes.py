from app.notes import (
    generate_action_items,
    generate_cleaned_content_fallback,
    generate_key_points,
    generate_notes,
    generate_summary,
)


TRANSCRIPT = (
    "This video explains how to take useful notes. "
    "You should capture the main idea. "
    "Avoid copying every sentence. "
    "Practice reviewing notes after watching."
)


def test_generate_summary_uses_initial_sentences():
    summary = generate_summary(TRANSCRIPT)
    assert "This video explains" in summary
    assert "You should capture" in summary


def test_generate_key_points_returns_at_least_three_points():
    assert len(generate_key_points("One sentence.")) == 3


def test_generate_action_items_extracts_actionable_sentences():
    actions = generate_action_items(TRANSCRIPT)
    assert actions == [
        "You should capture the main idea.",
        "Avoid copying every sentence.",
        "Practice reviewing notes after watching.",
    ]


def test_generate_notes_contains_required_sections(tmp_path):
    output_path = tmp_path / "notes.md"
    notes = generate_notes("Sample Title", TRANSCRIPT, output_path)

    assert "# Executive Summary" in notes
    assert "# Key Takeaways" in notes
    assert "# Structured Outline" in notes
    assert "# Action Items" in notes
    assert "- [ ] You should capture the main idea." in notes
    assert output_path.read_text(encoding="utf-8") == notes


def test_generate_cleaned_content_fallback_marks_rule_based_output(tmp_path):
    output_path = tmp_path / "cleaned.md"
    content = generate_cleaned_content_fallback("Sample Title", TRANSCRIPT, output_path)

    assert "# Edited Transcript" in content
    assert "## Sample Title" in content
    assert "Rule-based fallback" in content
    assert output_path.read_text(encoding="utf-8") == content


def test_generate_notes_uses_chinese_headings_for_chinese_transcript(tmp_path):
    output_path = tmp_path / "notes.md"
    notes = generate_notes(
        "中文标题",
        "这个视频解释如何整理笔记。你应该抓住主要观点。避免复制每一句话。",
        output_path,
    )

    assert "# 执行摘要" in notes
    assert "# 关键要点" in notes
    assert "# 结构化大纲" in notes
    assert "# 行动项" in notes


def test_cleaned_content_fallback_uses_chinese_heading_for_chinese_transcript(tmp_path):
    output_path = tmp_path / "cleaned.md"
    content = generate_cleaned_content_fallback(
        "中文标题",
        "这个视频解释如何整理笔记。你应该抓住主要观点。",
        output_path,
    )

    assert "# 编辑后文本" in content
    assert "规则回退" in content
