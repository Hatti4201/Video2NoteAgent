import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path

from app.transcription import (
    get_local_whisper_api_config,
    get_transcription_provider,
    transcribe_audio_file_via_local_whisper_api,
)
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
    provider = get_transcription_provider()
    if provider in {"local_whisper", "local_whisper_api", "local-whisper", "local-whisper-api"}:
        return transcribe_local_video_with_api(video_path)

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


def transcribe_local_video_with_api(video_path: Path) -> str:
    with TemporaryDirectory(prefix="video-note-agent-local-whisper-") as temp_dir:
        temp_path = Path(temp_dir)
        audio_path = temp_path / "audio.mp3"
        command = [
            "ffmpeg",
            "-y",
            "-err_detect",
            "ignore_err",
            "-fflags",
            "+discardcorrupt",
            "-i",
            str(video_path),
            "-vn",
            "-af",
            "pan=mono|c0=c0",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            str(audio_path),
        ]

        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as exc:
            raise VideoNoteError("ffmpeg is required to extract audio from local videos.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            if len(detail) > 800:
                detail = detail[-800:]
            raise VideoNoteError(detail or "ffmpeg audio extraction failed.") from exc

        try:
            return transcribe_audio_file_via_local_whisper_api(audio_path, config=get_local_whisper_api_config())
        except VideoNoteError as exc:
            raise VideoNoteError(f"Could not transcribe local video with local Whisper API: {exc}") from exc
