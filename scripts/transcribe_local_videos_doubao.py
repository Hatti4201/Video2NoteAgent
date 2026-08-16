#!/usr/bin/env python
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.local_video import SUPPORTED_VIDEO_EXTENSIONS, validate_local_video_path
from app.transcription import (
    DoubaoASRConfig,
    get_doubao_asr_config,
    get_local_whisper_api_config,
    get_transcription_provider,
    transcribe_audio_file_via_local_whisper_api,
    transcribe_audio_file_via_tos,
)
from app.utils import VideoNoteError, load_env_file


DEFAULT_OUTPUT_DIR = Path("output/local_raw_transcripts")


def find_video_files(input_path: Path, recursive: bool = False) -> list[Path]:
    path = input_path.expanduser()
    if path.is_file():
        return [validate_local_video_path(str(path))]
    if not path.exists():
        raise VideoNoteError(f"Input path does not exist: {path}")
    if not path.is_dir():
        raise VideoNoteError(f"Input path is not a file or directory: {path}")

    iterator = path.rglob("*") if recursive else path.iterdir()
    videos = [
        item
        for item in iterator
        if item.is_file() and item.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    ]
    return sorted(videos)


def run_ffmpeg(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise VideoNoteError("ffmpeg is required to extract audio from local videos.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        if len(detail) > 800:
            detail = detail[-800:]
        raise VideoNoteError(detail or "ffmpeg audio extraction failed.") from exc


def extract_audio_for_asr(video_path: Path, temp_dir: Path) -> Path:
    aac_path = temp_dir / "audio.aac"
    aac_copy_command = [
        "ffmpeg",
        "-y",
        "-err_detect",
        "ignore_err",
        "-fflags",
        "+discardcorrupt",
        "-i",
        str(video_path),
        "-vn",
        "-c:a",
        "copy",
        str(aac_path),
    ]
    try:
        run_ffmpeg(aac_copy_command)
        return aac_path
    except VideoNoteError:
        return extract_audio_as_mp3(video_path, temp_dir)


def extract_audio_as_mp3(video_path: Path, temp_dir: Path) -> Path:
    mp3_path = temp_dir / "audio.mp3"
    mp3_command = [
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
        str(mp3_path),
    ]
    run_ffmpeg(mp3_command)
    return mp3_path


def extract_audio_for_local_whisper_api(video_path: Path, temp_dir: Path) -> Path:
    return extract_audio_as_mp3(video_path, temp_dir)


def transcribe_with_silence_handling(audio_path: Path, audio_config: DoubaoASRConfig) -> tuple[str, bool]:
    provider = get_transcription_provider()
    if provider in {"local_whisper", "local_whisper_api", "local-whisper", "local-whisper-api"}:
        transcript = transcribe_audio_file_via_local_whisper_api(audio_path, config=get_local_whisper_api_config())
        return transcript, not transcript.strip()

    try:
        return transcribe_audio_file_via_tos(audio_path, config=audio_config), False
    except VideoNoteError as exc:
        if "Normal silence audio" in str(exc) or "no valid speech" in str(exc).lower():
            print("Doubao returned silence; writing an empty transcript file.", file=sys.stderr)
            return "", True
        raise


def unique_markdown_path(output_dir: Path, video_path: Path, overwrite: bool = False) -> Path:
    target = output_dir / f"{video_path.stem}.md"
    if overwrite or not target.exists():
        return target

    counter = 2
    while True:
        candidate = output_dir / f"{video_path.stem}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


def write_raw_transcript_markdown(output_path: Path, video_path: Path, transcript: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    title = video_path.stem or "Untitled Video"
    body = transcript.strip()
    output_path.write_text(
        f"# {title}\n\n"
        f"Source: `{video_path}`\n\n"
        "## Raw Transcript\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


def transcribe_video_to_markdown(video_path: Path, output_dir: Path, overwrite: bool = False) -> Path:
    target = unique_markdown_path(output_dir, video_path, overwrite=overwrite)
    with TemporaryDirectory(prefix="video-note-agent-doubao-") as temp_dir:
        temp_path = Path(temp_dir)
        print(f"Extracting audio: {video_path}")
        provider = get_transcription_provider()
        if provider in {"local_whisper", "local_whisper_api", "local-whisper", "local-whisper-api"}:
            audio_path = extract_audio_for_local_whisper_api(video_path, temp_path)
            print("Transcribing with local Whisper API...")
            transcript = transcribe_audio_file_via_local_whisper_api(audio_path, config=get_local_whisper_api_config())
            silence_detected = not transcript.strip()
        else:
            audio_path = extract_audio_for_asr(video_path, temp_path)
            print("Transcribing with Doubao Speech ASR...")
            audio_config = replace(get_doubao_asr_config(), audio_format=audio_path.suffix.lstrip("."))
            try:
                transcript, silence_detected = transcribe_with_silence_handling(audio_path, audio_config)
            except VideoNoteError as exc:
                if audio_path.suffix.lower() == ".aac" and "Invalid audio format" in str(exc):
                    print("Doubao rejected AAC audio; retrying with MP3.", file=sys.stderr)
                    audio_path = extract_audio_as_mp3(video_path, temp_path)
                    audio_config = replace(get_doubao_asr_config(), audio_format="mp3")
                    transcript, silence_detected = transcribe_with_silence_handling(audio_path, audio_config)
                else:
                    raise
            if not transcript.strip() and not silence_detected:
                raise VideoNoteError(f"Doubao Speech ASR returned an empty transcript for {video_path}")

    write_raw_transcript_markdown(target, video_path, transcript)
    return target


def should_skip_existing(output_dir: Path, video_path: Path, overwrite: bool) -> bool:
    return not overwrite and (output_dir / f"{video_path.stem}.md").exists()


def process_one_video(video_path: Path, output_dir: Path, overwrite: bool = False) -> Path:
    return transcribe_video_to_markdown(video_path, output_dir, overwrite=overwrite)


def run_batch(
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    recursive: bool = False,
    overwrite: bool = False,
    workers: int = 1,
) -> int:
    load_env_file()
    videos = find_video_files(input_path, recursive=recursive)
    if not videos:
        raise VideoNoteError(f"No supported video files found in {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    pending_videos = [video for video in videos if not should_skip_existing(output_dir, video, overwrite)]
    skipped = len(videos) - len(pending_videos)
    failures = 0
    print(f"Found {len(videos)} video file(s).")
    if skipped:
        print(f"Skipping {skipped} video(s) with existing output.")

    if not pending_videos:
        print("Done.")
        return 0

    workers = max(1, workers)
    if workers == 1:
        for index, video_path in enumerate(pending_videos, start=1):
            print(f"[{index}/{len(pending_videos)}] {video_path}")
            try:
                output_path = transcribe_video_to_markdown(video_path, output_dir, overwrite=overwrite)
                print(f"Created {output_path}")
            except VideoNoteError as exc:
                failures += 1
                print(f"Error: {exc}", file=sys.stderr)
    else:
        print(f"Processing with {workers} worker(s).")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_one_video, video_path, output_dir, overwrite): video_path
                for video_path in pending_videos
            }
            completed = 0
            for future in as_completed(futures):
                video_path = futures[future]
                completed += 1
                try:
                    output_path = future.result()
                    print(f"[{completed}/{len(pending_videos)}] Created {output_path}")
                except VideoNoteError as exc:
                    failures += 1
                    print(f"Error processing {video_path}: {exc}", file=sys.stderr)

    return 1 if failures else 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate raw transcript Markdown files from local videos using Doubao Speech ASR."
    )
    parser.add_argument("input_path", help="A local .mp4/.mov/.mkv file or a folder containing videos.")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for generated .md files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Scan folders recursively.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing transcript .md with the same video filename.",
    )
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent videos to process. Default: 1.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return run_batch(
            Path(args.input_path),
            output_dir=Path(args.output_dir),
            recursive=args.recursive,
            overwrite=args.overwrite,
            workers=args.workers,
        )
    except VideoNoteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
