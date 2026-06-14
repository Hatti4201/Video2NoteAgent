from pathlib import Path

from app.utils import VideoNoteError, collapse_whitespace


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
DEFAULT_WHISPER_MODEL = "base"


def is_supported_video_path(value: str) -> bool:
    return Path(value).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def validate_local_video_path(value: str) -> Path:
    video_path = Path(value).expanduser()

    if video_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        raise VideoNoteError(f"Unsupported local video file type. Supported extensions: {supported}.")

    if not video_path.exists():
        raise VideoNoteError(f"Local video file does not exist: {video_path}")

    if not video_path.is_file():
        raise VideoNoteError(f"Local video path is not a file: {video_path}")

    return video_path


def get_local_video_info(video_path: Path) -> dict:
    return {
        "title": video_path.stem or "Untitled Video",
        "url": str(video_path),
        "source": "local_video",
        "upload_date": None,
        "author": "",
        "duration": "",
        "language": "",
        "tags": [],
        "processing_method": "local_whisper",
    }


def transcribe_local_video(video_path: Path, model_name: str = DEFAULT_WHISPER_MODEL) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VideoNoteError(
            "Local video transcription requires faster-whisper. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(str(video_path))
        transcript_lines = [
            collapse_whitespace(segment.text)
            for segment in segments
            if collapse_whitespace(segment.text)
        ]
    except Exception as exc:
        raise VideoNoteError(f"Could not transcribe local video: {exc}") from exc

    return "\n".join(transcript_lines).strip()
