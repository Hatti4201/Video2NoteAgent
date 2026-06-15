import pytest

import app.downloader as downloader
from app.downloader import validate_youtube_url
from app.utils import VideoNoteError


def test_validate_youtube_url_accepts_watch_url():
    assert validate_youtube_url("https://www.youtube.com/watch?v=example")


def test_validate_youtube_url_accepts_short_url():
    assert validate_youtube_url("https://youtu.be/example")


def test_validate_youtube_url_rejects_invalid_input():
    assert not validate_youtube_url("hello-world")
    assert not validate_youtube_url("https://example.com/watch?v=example")


def test_get_video_info_uses_configured_youtube_cookies(monkeypatch, tmp_path):
    cookies_file = tmp_path / "youtube_cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    captured_options = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured_options.update(options)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url, download=False):
            return {"title": "Cookie Video", "webpage_url": url}

    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookies_file))
    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)

    info = downloader.get_video_info("https://www.youtube.com/watch?v=example")

    assert info["title"] == "Cookie Video"
    assert captured_options["cookiefile"] == str(cookies_file)
    assert captured_options["js_runtimes"] == {"node": {}}
    assert captured_options["skip_download"] is True


def test_get_video_info_fails_when_configured_youtube_cookies_file_is_missing(
    monkeypatch, tmp_path
):
    missing_file = tmp_path / "missing_cookies.txt"

    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(missing_file))

    with pytest.raises(VideoNoteError, match="YOUTUBE_COOKIES_FILE is set"):
        downloader.get_video_info("https://www.youtube.com/watch?v=example")
