from pathlib import Path

import pytest

from app.local_video import (
    get_local_video_info,
    is_supported_video_path,
    validate_local_video_path,
)
from app.utils import VideoNoteError


def test_is_supported_video_path_accepts_phase_2_extensions():
    assert is_supported_video_path("lesson.mp4")
    assert is_supported_video_path("lesson.MOV")
    assert is_supported_video_path("lesson.mkv")


def test_is_supported_video_path_rejects_other_extensions():
    assert not is_supported_video_path("lesson.txt")
    assert not is_supported_video_path("https://www.youtube.com/watch?v=example")


def test_validate_local_video_path_returns_existing_supported_file(tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"fake video")

    assert validate_local_video_path(str(video_path)) == video_path


def test_validate_local_video_path_rejects_missing_file(tmp_path):
    with pytest.raises(VideoNoteError, match="does not exist"):
        validate_local_video_path(str(tmp_path / "missing.mp4"))


def test_validate_local_video_path_rejects_unsupported_extension(tmp_path):
    text_path = tmp_path / "sample.txt"
    text_path.write_text("not a video", encoding="utf-8")

    with pytest.raises(VideoNoteError, match="Unsupported local video file type"):
        validate_local_video_path(str(text_path))


def test_get_local_video_info_uses_filename_metadata(tmp_path):
    video_path = Path(tmp_path / "Sample Lesson.mp4")
    video_path.write_bytes(b"fake video")

    assert get_local_video_info(video_path) == {
        "title": "Sample Lesson",
        "url": str(video_path),
        "source": "local_video",
        "upload_date": None,
        "author": "",
        "duration": "",
        "language": "",
        "tags": [],
        "processing_method": "local_whisper",
    }
