from pathlib import Path

from app.transcript import format_transcript_markdown, generate_transcript, parse_vtt


SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
Hello <c>world</c>.

00:00:02.000 --> 00:00:04.000
Hello <c>world</c>.

00:00:04.000 --> 00:00:06.000
This is a transcript line.
"""


def test_parse_vtt_removes_metadata_timestamps_and_duplicate_lines():
    assert parse_vtt(SAMPLE_VTT) == "Hello world.\nThis is a transcript line."


def test_generate_transcript_writes_plain_text(tmp_path):
    subtitle_path = tmp_path / "sample.vtt"
    output_path = tmp_path / "transcript.txt"
    subtitle_path.write_text(SAMPLE_VTT, encoding="utf-8")

    transcript = generate_transcript(Path(subtitle_path), output_path)

    assert transcript == "Hello world.\nThis is a transcript line."
    assert output_path.read_text(encoding="utf-8") == transcript + "\n"


def test_format_transcript_markdown_writes_basic_paragraphs(tmp_path):
    output_path = tmp_path / "formatted.md"
    markdown = format_transcript_markdown(
        "Sample Title",
        "Line one.\nLine two.\nLine three.\nLine four.",
        output_path,
    )

    assert "# Sample Title" in markdown
    assert "## Formatted Transcript" in markdown
    assert "Line one. Line two. Line three." in markdown
    assert "Line four." in markdown
    assert output_path.read_text(encoding="utf-8") == markdown
