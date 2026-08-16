#!/usr/bin/env python
"""Batch edit plain-text course transcripts into readable markdown notes."""
from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm import generate_reformatted_transcript
from app.utils import VideoNoteError, load_env_file


DEFAULT_INPUT_DIR = Path("input/transcripts")
DEFAULT_OUTPUT_DIR = Path("output/黑马Java+AI-edited")
DEFAULT_PREFIX = "黑马Java+AI"
LESSON_RE = re.compile(r"- P(?P<part>\d+)【(?P<title>[^】]+)】")
LEADING_NUMBER_RE = re.compile(r"^\s*\d+\s*[.．、-]\s*")
FILENAME_UNSAFE_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass(frozen=True)
class TranscriptFile:
    path: Path
    sequence: int
    title: str

    def output_base_name(self, prefix: str = DEFAULT_PREFIX) -> str:
        title = sanitize_filename_part(self.title)
        return f"{sanitize_filename_part(prefix)}-{self.sequence}.{title}"


def sanitize_filename_part(value: str, max_length: int = 120) -> str:
    cleaned = FILENAME_UNSAFE_RE.sub("-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:max_length].strip(" .-_") or "未命名"


def extract_transcript_file(path: Path) -> TranscriptFile:
    match = LESSON_RE.search(path.stem)
    if not match:
        return TranscriptFile(path=path, sequence=0, title=path.stem)

    title = LEADING_NUMBER_RE.sub("", match.group("title")).strip()
    return TranscriptFile(
        path=path,
        sequence=int(match.group("part")),
        title=title or match.group("title").strip(),
    )


def find_txt_files(input_path: Path) -> list[TranscriptFile]:
    path = input_path.expanduser()
    if path.is_file():
        if path.suffix.lower() != ".txt":
            raise VideoNoteError(f"Input file is not a .txt transcript: {path}")
        return [extract_transcript_file(path)]
    if not path.exists():
        raise VideoNoteError(f"Input path does not exist: {path}")
    if not path.is_dir():
        raise VideoNoteError(f"Input path is not a file or directory: {path}")

    files = [
        extract_transcript_file(item)
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() == ".txt"
    ]
    return sorted(files, key=lambda item: (item.sequence or 10**9, item.path.name))


def output_path(
    output_dir: Path,
    transcript_file: TranscriptFile,
    prefix: str = DEFAULT_PREFIX,
) -> Path:
    base_name = transcript_file.output_base_name(prefix)
    return output_dir / f"{base_name}.md"


def should_skip(
    output_dir: Path,
    transcript_file: TranscriptFile,
    overwrite: bool,
    prefix: str = DEFAULT_PREFIX,
) -> bool:
    if overwrite:
        return False
    return output_path(output_dir, transcript_file, prefix=prefix).exists()


def process_one(
    transcript_file: TranscriptFile,
    output_dir: Path,
    overwrite: bool = False,
    prefix: str = DEFAULT_PREFIX,
) -> Path:
    target_path = output_path(output_dir, transcript_file, prefix=prefix)
    if not overwrite and target_path.exists():
        return target_path

    transcript = transcript_file.path.read_text(encoding="utf-8").strip()
    if not transcript:
        raise VideoNoteError(f"Transcript is empty: {transcript_file.path}")

    content = generate_reformatted_transcript(transcript_file.title, transcript)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(f"{content.strip()}\n", encoding="utf-8")
    return target_path


def run_batch(
    input_path: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    workers: int = 1,
    limit: int | None = None,
    prefix: str = DEFAULT_PREFIX,
) -> int:
    load_env_file()
    files = find_txt_files(input_path)
    if not files:
        raise VideoNoteError(f"No .txt files found in {input_path}")
    if limit is not None:
        files = files[: max(0, limit)]

    pending = [item for item in files if not should_skip(output_dir, item, overwrite, prefix=prefix)]
    skipped = len(files) - len(pending)
    failures = 0

    print(f"Found {len(files)} .txt transcript file(s).")
    if skipped:
        print(f"Skipping {skipped} file(s) with existing output.")
    if not pending:
        print("Done.")
        return 0

    workers = max(1, workers)
    if workers == 1:
        for index, item in enumerate(pending, start=1):
            print(f"[{index}/{len(pending)}] {item.path.name}")
            try:
                target_path = process_one(item, output_dir, overwrite=overwrite, prefix=prefix)
                print(f"  -> Created {target_path.name}")
            except VideoNoteError as exc:
                failures += 1
                print(f"  ERROR: {exc}", file=sys.stderr)
    else:
        print(f"Processing with {workers} worker(s).")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_one, item, output_dir, overwrite, prefix): item
                for item in pending
            }
            completed = 0
            for future in as_completed(futures):
                item = futures[future]
                completed += 1
                try:
                    target_path = future.result()
                    print(f"[{completed}/{len(pending)}] Created {target_path.name}")
                except VideoNoteError as exc:
                    failures += 1
                    print(f"Error processing {item.path.name}: {exc}", file=sys.stderr)

    if failures:
        print(f"\nDone with {failures} failure(s).", file=sys.stderr)
        return 1

    print(f"\nDone. {len(pending)} markdown file(s) written to {output_dir}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch edit .txt transcripts into markdown files with edited text, outline, and key takeaways."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(DEFAULT_INPUT_DIR),
        help=f"A .txt file or folder containing .txt transcripts. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for generated markdown files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("-j", "--workers", type=int, default=1, help="Concurrent workers. Default: 1.")
    parser.add_argument("--limit", type=int, help="Process only the first N files after lesson sorting.")
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Filename prefix before the lesson number. Default: {DEFAULT_PREFIX}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return run_batch(
            input_path=Path(args.input_path),
            output_dir=Path(args.output_dir),
            overwrite=args.overwrite,
            workers=args.workers,
            limit=args.limit,
            prefix=args.prefix,
        )
    except VideoNoteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
