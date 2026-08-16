from pathlib import Path

from app.utils import VideoNoteError
from scripts import reformat_local_transcripts_with_llm as helper


RAW_MARKDOWN = """# Sample Lesson

Source: `/videos/sample.mp4`

## Raw Transcript

uh hello everybody welcome back to class this is the main idea and you should practice it.
"""


def test_parse_raw_transcript_markdown_extracts_title_source_and_transcript(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text(RAW_MARKDOWN, encoding="utf-8")

    title, source, transcript = helper.parse_raw_transcript_markdown(path)

    assert title == "Sample Lesson"
    assert source == "/videos/sample.mp4"
    assert "you should practice it" in transcript


def test_write_reformatted_markdown_preserves_title_and_source(tmp_path):
    output_path = tmp_path / "sample.md"

    helper.write_reformatted_markdown(
        output_path,
        "Sample Lesson",
        "/videos/sample.mp4",
        "# Edited Transcript\n\nCleaned text.\n\n# Outline\n\n1. Topic\n\n# Key Takeaways\n\n- Point",
    )

    assert output_path.read_text(encoding="utf-8") == (
        "# Sample Lesson\n\n"
        "Source: `/videos/sample.mp4`\n\n"
        "# Edited Transcript\n\nCleaned text.\n\n# Outline\n\n1. Topic\n\n# Key Takeaways\n\n- Point\n"
    )


def test_reformat_markdown_file_uses_llm_output(monkeypatch, tmp_path):
    source_path = tmp_path / "sample.md"
    source_path.write_text(RAW_MARKDOWN, encoding="utf-8")
    calls = []

    def fake_generate(title, transcript):
        calls.append((title, transcript))
        return "# Edited Transcript\n\nCleaned text.\n\n# Outline\n\n1. Topic\n\n# Key Takeaways\n\n- Point"

    monkeypatch.setattr(helper, "generate_reformatted_transcript", fake_generate)

    output_path = helper.reformat_markdown_file(source_path, tmp_path / "output")

    assert calls == [
        (
            "Sample Lesson",
            "uh hello everybody welcome back to class this is the main idea and you should practice it.",
        )
    ]
    assert output_path == tmp_path / "output" / "sample.md"
    assert "# Outline" in output_path.read_text(encoding="utf-8")


def test_reformat_markdown_file_uses_empty_transcript_document(monkeypatch, tmp_path):
    source_path = tmp_path / "sample.md"
    source_path.write_text(
        "# Sample Lesson\n\nSource: `/videos/sample.mp4`\n\n## Raw Transcript\n\n",
        encoding="utf-8",
    )
    calls = []

    def fake_generate(title, transcript):
        calls.append((title, transcript))
        return "should not be used"

    monkeypatch.setattr(helper, "generate_reformatted_transcript", fake_generate)

    output_path = helper.reformat_markdown_file(source_path, tmp_path / "output")

    assert calls == []
    assert "No speech was detected" in output_path.read_text(encoding="utf-8")


def test_run_batch_skips_existing_outputs(monkeypatch, tmp_path):
    source_a = tmp_path / "a.md"
    source_b = tmp_path / "b.md"
    source_a.write_text(RAW_MARKDOWN.replace("Sample Lesson", "A"), encoding="utf-8")
    source_b.write_text(RAW_MARKDOWN.replace("Sample Lesson", "B"), encoding="utf-8")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "a.md").write_text("done", encoding="utf-8")

    called = []

    def fake_find_markdown_files(input_path, recursive=False):
        return [source_a, source_b]

    def fake_process_one_file(markdown_path, output_dir, overwrite=False):
        called.append(markdown_path.name)
        return output_dir / markdown_path.name

    monkeypatch.setattr(helper, "find_markdown_files", fake_find_markdown_files)
    monkeypatch.setattr(helper, "process_one_file", fake_process_one_file)

    result = helper.run_batch(tmp_path, output_dir=tmp_path / "output", workers=2)

    assert result == 0
    assert called == ["b.md"]


def test_parse_raw_transcript_markdown_rejects_non_raw_file(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("# Sample\n\nNo raw transcript here.\n", encoding="utf-8")

    try:
        helper.parse_raw_transcript_markdown(path)
    except VideoNoteError as exc:
        assert "raw transcript" in str(exc)
    else:
        raise AssertionError("Expected VideoNoteError")
