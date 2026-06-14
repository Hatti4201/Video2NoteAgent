import json

from app import utils


def test_safe_folder_part_removes_unsafe_characters():
    assert utils.safe_folder_part("My Video: Notes / Part 1!") == "my-video-notes-part-1"


def test_create_video_output_dir_uses_date_title_and_avoids_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)

    first = utils.create_video_output_dir("Sample Video", "20260102")
    second = utils.create_video_output_dir("Sample Video", "20260102")

    assert first == tmp_path / "2026-01-02-sample-video"
    assert second == tmp_path / "2026-01-02-sample-video-2"
    assert first.exists()
    assert second.exists()


def test_write_metadata_writes_required_fields(tmp_path):
    utils.write_metadata(
        output_dir=tmp_path,
        title="Sample Title",
        url="https://youtu.be/example",
        source="youtube",
        created_at="2026-01-02T03:04:05+00:00",
        author="Sample Author",
        duration="123",
        language="en",
        tags=["learning", "video"],
        summary="Short summary.",
        processing_method="youtube_subtitle",
    )

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))

    assert metadata == {
        "title": "Sample Title",
        "url": "https://youtu.be/example",
        "source": "youtube",
        "author": "Sample Author",
        "duration": "123",
        "language": "en",
        "tags": ["learning", "video"],
        "status": "Processed",
        "created_at": "2026-01-02T03:04:05+00:00",
        "summary": "Short summary.",
        "processing_method": "youtube_subtitle",
    }


def test_detect_content_language_detects_chinese():
    assert utils.detect_content_language("这是一个中文视频的逐字稿，讨论如何整理知识。") == "chinese"


def test_detect_content_language_defaults_to_english():
    assert utils.detect_content_language("This is an English transcript about knowledge work.") == "english"
