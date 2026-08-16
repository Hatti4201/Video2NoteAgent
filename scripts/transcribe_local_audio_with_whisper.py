#!/usr/bin/env python
"""Transcribe mp3 files in a directory using the local Whisper API server."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.transcription import LocalWhisperAPIConfig, transcribe_audio_file_via_local_whisper_api
from app.utils import VideoNoteError, load_env_file

DEFAULT_AUDIO_DIR = Path("output/local_audio")
DEFAULT_OUTPUT_DIR = Path("output/local_raw_transcripts")
DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_TRANSCRIBE_PATH = "/transcribe/path"
DEFAULT_MODEL = "whisper"
DEFAULT_TIMEOUT = 3600


def find_missing(audio_dir: Path, output_dir: Path) -> list[Path]:
    existing_stems = {p.stem for p in output_dir.glob("*.md")}
    all_mp3 = sorted(audio_dir.glob("*.mp3"))
    return [f for f in all_mp3 if f.stem not in existing_stems]


def write_markdown(output_path: Path, audio_path: Path, transcript: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    title = audio_path.stem or "Untitled"
    body = transcript.strip()
    output_path.write_text(
        f"# {title}\n\n"
        f"Source: `{audio_path}`\n\n"
        "## Raw Transcript\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


def run(
    audio_dir: Path,
    output_dir: Path,
    base_url: str,
    transcribe_path: str,
    model: str,
    timeout: int,
    overwrite: bool,
) -> int:
    load_env_file()
    output_dir.mkdir(parents=True, exist_ok=True)

    if overwrite:
        mp3_files = sorted(audio_dir.glob("*.mp3"))
    else:
        mp3_files = find_missing(audio_dir, output_dir)

    if not mp3_files:
        print("Nothing to transcribe — all mp3 files already have transcripts.")
        return 0

    print(f"Found {len(mp3_files)} mp3 file(s) to transcribe.")
    config = LocalWhisperAPIConfig(
        base_url=base_url.rstrip("/"),
        transcribe_path=transcribe_path if transcribe_path.startswith("/") else "/" + transcribe_path,
        model=model,
        language="",
        temperature="0",
        timeout_seconds=timeout,
        api_key=None,
    )

    failures = 0
    for index, mp3_path in enumerate(mp3_files, start=1):
        output_path = output_dir / f"{mp3_path.stem}.md"
        print(f"[{index}/{len(mp3_files)}] {mp3_path.name}")
        try:
            transcript = transcribe_audio_file_via_local_whisper_api(mp3_path.resolve(), config=config)
            write_markdown(output_path, mp3_path, transcript)
            print(f"  -> Created {output_path.name}")
        except VideoNoteError as exc:
            failures += 1
            print(f"  ERROR: {exc}", file=sys.stderr)

    if failures:
        print(f"\nDone with {failures} failure(s).", file=sys.stderr)
        return 1
    print(f"\nDone. {len(mp3_files)} transcript(s) written.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe mp3 files using local Whisper API.")
    parser.add_argument("--audio-dir", default=str(DEFAULT_AUDIO_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--transcribe-path", default=DEFAULT_TRANSCRIBE_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return run(
        audio_dir=Path(args.audio_dir),
        output_dir=Path(args.output_dir),
        base_url=args.base_url,
        transcribe_path=args.transcribe_path,
        model=args.model,
        timeout=args.timeout,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    raise SystemExit(main())
