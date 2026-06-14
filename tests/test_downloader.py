from app.downloader import validate_youtube_url


def test_validate_youtube_url_accepts_watch_url():
    assert validate_youtube_url("https://www.youtube.com/watch?v=example")


def test_validate_youtube_url_accepts_short_url():
    assert validate_youtube_url("https://youtu.be/example")


def test_validate_youtube_url_rejects_invalid_input():
    assert not validate_youtube_url("hello-world")
    assert not validate_youtube_url("https://example.com/watch?v=example")
