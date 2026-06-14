import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.adapters import publish_output
from app.adapters.base import PublishResult
from app.downloader import NoSubtitleError, download_subtitle, download_youtube_audio, validate_youtube_url
from app.input_adapters.telegram import TelegramBot, TelegramError
from app.local_video import (
    get_local_video_info,
    is_supported_video_path,
    transcribe_local_video,
    validate_local_video_path,
)
from app.llm import generate_llm_documents
from app.notes import generate_cleaned_content_fallback, generate_notes
from app.transcription import transcribe_audio_file_via_tos
from app.transcript import format_transcript_markdown, parse_vtt
from app.utils import (
    VideoNoteError,
    create_video_output_dir,
    current_timestamp,
    load_env_file,
    write_metadata,
)


OUTPUT_FILE_NAMES = [
    "metadata.json",
    "01_raw_transcript.txt",
    "02_formatted_transcript.md",
    "03_cleaned_content.md",
    "04_notes_outline.md",
]


@dataclass(frozen=True)
class ProcessResult:
    output_dir: Path
    publish_results: list[PublishResult]


def write_output_files(video_info: dict, transcript: str) -> ProcessResult:
    if not transcript:
        raise VideoNoteError("Transcript source did not contain usable transcript text.")

    title = video_info["title"]
    output_dir = create_video_output_dir(title, video_info.get("upload_date"))

    print("Writing raw transcript...")
    (output_dir / "01_raw_transcript.txt").write_text(transcript.strip() + "\n", encoding="utf-8")

    print("Generating formatted transcript...")
    format_transcript_markdown(title, transcript, output_dir / "02_formatted_transcript.md")

    try:
        print("Generating LLM content...")
        cleaned_content, notes_outline = generate_llm_documents(title, transcript)
        (output_dir / "03_cleaned_content.md").write_text(cleaned_content + "\n", encoding="utf-8")
        (output_dir / "04_notes_outline.md").write_text(notes_outline + "\n", encoding="utf-8")
    except VideoNoteError as exc:
        print(f"Warning: {exc} Using rule-based fallback.", file=sys.stderr)

        print("Generating rule-based fallback content...")
        generate_cleaned_content_fallback(title, transcript, output_dir / "03_cleaned_content.md")

        print("Generating notes outline...")
        generate_notes(title, transcript, output_dir / "04_notes_outline.md")
        notes_outline = (output_dir / "04_notes_outline.md").read_text(encoding="utf-8")

    write_metadata(
        output_dir=output_dir,
        title=title,
        url=video_info["url"],
        source=video_info["source"],
        created_at=current_timestamp(),
        author=str(video_info.get("author") or ""),
        duration=str(video_info.get("duration") or ""),
        language=str(video_info.get("language") or ""),
        tags=list(video_info.get("tags") or []),
        status="Processed",
        summary=extract_metadata_summary(notes_outline),
        processing_method=str(video_info.get("processing_method") or ""),
    )

    print("Publishing output adapters...")
    publish_results = publish_output(output_dir)
    for result in publish_results:
        if result.success:
            suffix = f" {result.url}" if result.url else ""
            print(f"Adapter {result.adapter_name}: {result.message}{suffix}")
        else:
            print(f"Warning: Adapter {result.adapter_name}: {result.message}", file=sys.stderr)

    return ProcessResult(output_dir=output_dir, publish_results=publish_results)


def extract_metadata_summary(notes_outline: str) -> str:
    lines = [line.strip() for line in notes_outline.splitlines()]
    summary_lines: list[str] = []
    in_summary = False

    for line in lines:
        if line == "# Executive Summary" or line == "## Summary":
            in_summary = True
            continue
        if in_summary and line.startswith("#"):
            break
        if in_summary and line:
            summary_lines.append(line)

    return " ".join(summary_lines).strip()


def process_youtube_url(url: str) -> ProcessResult:
    print("Reading video information...")
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        try:
            subtitle_info = download_subtitle(url, output_path=temp_path / "raw_subtitle.vtt")
            print(f"Downloaded subtitles ({subtitle_info['language']}).")

            print("Generating transcript...")
            transcript = parse_vtt(subtitle_info["subtitle_path"].read_text(encoding="utf-8"))
            video_info = subtitle_info
        except NoSubtitleError as exc:
            print(f"Warning: {exc} Falling back to Doubao Speech ASR.", file=sys.stderr)

            print("Downloading YouTube audio for ASR...")
            audio_info = download_youtube_audio(url, temp_path)

            print("Transcribing YouTube audio with Doubao Speech ASR...")
            transcript = transcribe_audio_file_via_tos(audio_info["audio_path"])
            video_info = audio_info

    return write_output_files(video_info, transcript)


def process_local_video(value: str) -> ProcessResult:
    print("Reading local video information...")
    video_path = validate_local_video_path(value)
    video_info = get_local_video_info(video_path)

    print("Transcribing local video...")
    transcript = transcribe_local_video(video_path)

    return write_output_files(video_info, transcript)


def run(input_value: str) -> None:
    if validate_youtube_url(input_value):
        result = process_youtube_url(input_value)
    elif is_supported_video_path(input_value):
        result = process_local_video(input_value)
    else:
        raise VideoNoteError(
            "Invalid input. Provide a valid YouTube URL or a local .mp4, .mov, or .mkv file."
        )

    print("Done.")
    output_dir = result.output_dir
    print(f"Created {output_dir}")
    for file_name in OUTPUT_FILE_NAMES:
        print(f"Created {output_dir / file_name}")


def main() -> int:
    load_env_file()

    if len(sys.argv) != 2:
        print("Usage: python main.py <youtube_url_or_local_video_path|telegram>", file=sys.stderr)
        return 1

    try:
        if sys.argv[1] == "telegram":
            TelegramBot.from_env(process_youtube_url).poll_forever()
        else:
            run(sys.argv[1])
    except VideoNoteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except TelegramError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Error: interrupted.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
