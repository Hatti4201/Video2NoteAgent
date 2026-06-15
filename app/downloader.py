from pathlib import Path
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.utils import VideoNoteError, ensure_output_dir


SUPPORTED_LANGUAGE_PREFIXES = ("en", "zh")
NO_SUBTITLES_MESSAGE = "No English or Chinese subtitles were found for this video."
YOUTUBE_COOKIES_FILE_ENV = "YOUTUBE_COOKIES_FILE"


class NoSubtitleError(VideoNoteError):
    """Raised when a valid YouTube video has no supported subtitles."""


def validate_youtube_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if parsed.scheme not in {"http", "https"}:
        return False

    if host == "youtu.be":
        return bool(parsed.path.strip("/"))

    if host in {"youtube.com", "m.youtube.com"}:
        return parsed.path == "/watch" and "v=" in parsed.query

    return False


def _youtube_dl_options(extra_options: dict | None = None) -> dict:
    options = {
        "quiet": True,
        "noplaylist": True,
        "js_runtimes": {"node": {}},
    }
    if extra_options:
        options.update(extra_options)

    cookies_file = os.environ.get(YOUTUBE_COOKIES_FILE_ENV, "").strip()
    if cookies_file:
        cookies_path = Path(cookies_file)
        if not cookies_path.exists():
            raise VideoNoteError(
                f"{YOUTUBE_COOKIES_FILE_ENV} is set but the file does not exist: {cookies_file}"
            )
        options["cookiefile"] = str(cookies_path)

    return options


def get_video_info(url: str) -> dict:
    if not validate_youtube_url(url):
        raise VideoNoteError("Invalid YouTube URL. Provide a valid youtube.com/watch or youtu.be URL.")

    try:
        with YoutubeDL(
            _youtube_dl_options({
                "skip_download": True,
                "ignore_no_formats_error": True,
            })
        ) as ydl:
            return ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise VideoNoteError(f"Could not read video information: {exc}") from exc


def _language_rank(language: str) -> tuple[int, str]:
    lower = language.lower()
    if lower.startswith("en"):
        return (0, language)
    if lower.startswith("zh"):
        return (1, language)
    return (2, language)


def _find_supported_subtitle(info: dict) -> tuple[str, dict, bool]:
    subtitle_sets = [
        (info.get("subtitles") or {}, False),
        (info.get("automatic_captions") or {}, True),
    ]

    for subtitles, is_automatic in subtitle_sets:
        supported_languages = sorted(
            (
                language
                for language in subtitles
                if language.lower().startswith(SUPPORTED_LANGUAGE_PREFIXES)
            ),
            key=_language_rank,
        )

        for language in supported_languages:
            formats = subtitles.get(language) or []
            vtt_format = next((item for item in formats if item.get("ext") == "vtt"), None)
            if vtt_format and vtt_format.get("url"):
                return language, vtt_format, is_automatic

    raise NoSubtitleError(NO_SUBTITLES_MESSAGE)


def download_subtitle(url: str, output_path: Path | None = None) -> dict:
    info = get_video_info(url)
    language, subtitle, is_automatic = _find_supported_subtitle(info)

    output_dir = ensure_output_dir()
    output_path = output_path or output_dir / "raw_subtitle.vtt"

    request = Request(subtitle["url"], headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=30) as response:
            subtitle_text = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise VideoNoteError(f"Could not download subtitles: {exc}") from exc

    output_path.write_text(subtitle_text, encoding="utf-8")

    return {
        "title": info.get("title") or "Untitled Video",
        "url": info.get("webpage_url") or url,
        "source": "youtube",
        "upload_date": info.get("upload_date"),
        "author": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration") or "",
        "language": language,
        "tags": info.get("tags") or [],
        "processing_method": "youtube_subtitle_auto" if is_automatic else "youtube_subtitle",
        "subtitle_path": output_path,
        "is_automatic": is_automatic,
    }


def download_youtube_audio(url: str, output_dir: Path) -> dict:
    info = get_video_info(url)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "youtube_audio.%(ext)s")

    options = _youtube_dl_options({
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }
        ],
    })

    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])
    except DownloadError as exc:
        raise VideoNoteError(f"Could not download YouTube audio for ASR: {exc}") from exc

    audio_path = output_dir / "youtube_audio.mp3"
    if not audio_path.exists():
        candidates = sorted(
            path for path in output_dir.glob("youtube_audio.*")
            if path.is_file() and not path.name.endswith(".part")
        )
        if not candidates:
            raise VideoNoteError("Could not find downloaded YouTube audio for ASR.")
        audio_path = candidates[0]

    return {
        "title": info.get("title") or "Untitled Video",
        "url": info.get("webpage_url") or url,
        "source": "youtube_asr",
        "upload_date": info.get("upload_date"),
        "author": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration") or "",
        "language": "",
        "tags": info.get("tags") or [],
        "processing_method": "doubao_asr",
        "audio_path": audio_path,
    }
