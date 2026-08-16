#!/usr/bin/env python
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm import generate_reformatted_transcript
from app.utils import VideoNoteError, detect_content_language, load_env_file


DEFAULT_INPUT_DIR = Path("output/local_raw_transcripts")
DEFAULT_OUTPUT_DIR = Path("output/local_reformatted_transcripts")
RAW_TRANSCRIPT_MARKER = "## Raw Transcript"
SOURCE_RE = re.compile(r"^Source:\s*`(?P<source>.+?)`\s*$", re.MULTILINE)


def find_markdown_files(input_path: Path, recursive: bool = False) -> list[Path]:
    path = input_path.expanduser()
    if path.is_file():
        if path.suffix.lower() != ".md":
            raise VideoNoteError(f"Input file is not a markdown file: {path}")
        return [path]
    if not path.exists():
        raise VideoNoteError(f"Input path does not exist: {path}")
    if not path.is_dir():
        raise VideoNoteError(f"Input path is not a file or directory: {path}")

    iterator = path.rglob("*.md") if recursive else path.iterdir()
    files = [
        item
        for item in iterator
        if item.is_file() and item.suffix.lower() == ".md"
    ]
    return sorted(files)


def parse_raw_transcript_markdown(markdown_path: Path) -> tuple[str, str, str]:
    markdown = markdown_path.read_text(encoding="utf-8")
    if RAW_TRANSCRIPT_MARKER not in markdown:
        raise VideoNoteError(f"Input markdown does not look like a raw transcript file: {markdown_path}")

    title = markdown_path.stem
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip() or title

    source_match = SOURCE_RE.search(markdown)
    source = source_match.group("source").strip() if source_match else ""

    transcript = markdown.split(RAW_TRANSCRIPT_MARKER, 1)[1].strip()

    return title, source, transcript


def unique_output_path(output_dir: Path, markdown_path: Path, overwrite: bool = False) -> Path:
    target = output_dir / markdown_path.name
    if overwrite or not target.exists():
        return target

    counter = 2
    while True:
        candidate = output_dir / f"{markdown_path.stem}-{counter}{markdown_path.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def write_reformatted_markdown(output_path: Path, title: str, source: str, content: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_value = source or ""
    output_path.write_text(
        f"# {title}\n\n"
        f"Source: `{source_value}`\n\n"
        f"{content.strip()}\n",
        encoding="utf-8",
    )


def build_empty_transcript_document(title: str) -> str:
    language = detect_content_language(title)
    if language == "chinese":
        return (
            "# 编辑后文本\n\n"
            "未检测到可用语音内容。\n\n"
            "# 大纲\n\n"
            "- 源音频中没有检测到可用的口语内容。\n\n"
            "# 关键要点\n\n"
            "- 该录音似乎没有可用语音。\n"
        )

    return (
        "# Edited Transcript\n\n"
        "No speech was detected in the source audio.\n\n"
        "# Outline\n\n"
        "- No spoken content was detected.\n\n"
        "# Key Takeaways\n\n"
        "- The recording appears to contain no usable speech.\n"
    )


def reformat_markdown_file(markdown_path: Path, output_dir: Path, overwrite: bool = False) -> Path:
    title, source, transcript = parse_raw_transcript_markdown(markdown_path)
    target = unique_output_path(output_dir, markdown_path, overwrite=overwrite)

    print(f"Reformatting: {markdown_path}")
    reformatted = build_empty_transcript_document(title) if not transcript.strip() else generate_reformatted_transcript(title, transcript)
    write_reformatted_markdown(target, title, source, reformatted)
    return target


def should_skip_existing(output_dir: Path, markdown_path: Path, overwrite: bool) -> bool:
    return not overwrite and (output_dir / markdown_path.name).exists()


def process_one_file(markdown_path: Path, output_dir: Path, overwrite: bool = False) -> Path:
    return reformat_markdown_file(markdown_path, output_dir, overwrite=overwrite)


def run_batch(
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    recursive: bool = False,
    overwrite: bool = False,
    workers: int = 1,
) -> int:
    load_env_file()
    files = find_markdown_files(input_path, recursive=recursive)
    if not files:
        raise VideoNoteError(f"No markdown files found in {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    pending_files = [path for path in files if not should_skip_existing(output_dir, path, overwrite)]
    skipped = len(files) - len(pending_files)
    failures = 0

    print(f"Found {len(files)} markdown file(s).")
    if skipped:
        print(f"Skipping {skipped} file(s) with existing output.")

    if not pending_files:
        print("Done.")
        return 0

    workers = max(1, workers)
    if workers == 1:
        for index, markdown_path in enumerate(pending_files, start=1):
            print(f"[{index}/{len(pending_files)}] {markdown_path}")
            try:
                output_path = reformat_markdown_file(markdown_path, output_dir, overwrite=overwrite)
                print(f"Created {output_path}")
            except VideoNoteError as exc:
                failures += 1
                print(f"Error: {exc}", file=sys.stderr)
    else:
        print(f"Processing with {workers} worker(s).")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_one_file, markdown_path, output_dir, overwrite): markdown_path
                for markdown_path in pending_files
            }
            completed = 0
            for future in as_completed(futures):
                markdown_path = futures[future]
                completed += 1
                try:
                    output_path = future.result()
                    print(f"[{completed}/{len(pending_files)}] Created {output_path}")
                except VideoNoteError as exc:
                    failures += 1
                    print(f"Error processing {markdown_path}: {exc}", file=sys.stderr)

    return 1 if failures else 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite raw transcript Markdown files into readable notes using an LLM."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(DEFAULT_INPUT_DIR),
        help=f"A raw transcript .md file or a folder containing raw transcript files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for generated reformatted .md files. Default: {DEFAULT_OUTPUT_DIR}",
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
        help="Overwrite an existing reformatted .md with the same filename.",
    )
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent files to process. Default: 1.",
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
