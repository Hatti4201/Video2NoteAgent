#!/usr/bin/env python
"""Reformat plain-text transcripts into readable markdown notes using an LLM."""
from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm import generate_reformatted_transcript
from app.utils import VideoNoteError, load_env_file
from scripts.reformat_local_transcripts_with_llm import (
    build_empty_transcript_document,
    unique_output_path,
    write_reformatted_markdown,
)

_EPISODE_RE = re.compile(r"- (P\d+)【([^】]+)】")


def extract_title(txt_path: Path) -> str:
    match = _EPISODE_RE.search(txt_path.stem)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return txt_path.stem


def reformat_txt_file(txt_path: Path, output_dir: Path, overwrite: bool = False) -> Path:
    title = extract_title(txt_path)
    target = unique_output_path(output_dir, txt_path.with_suffix(".md"), overwrite=overwrite)

    transcript = txt_path.read_text(encoding="utf-8").strip()
    print(f"Reformatting: {txt_path.name}")
    content = build_empty_transcript_document(title) if not transcript else generate_reformatted_transcript(title, transcript)
    write_reformatted_markdown(target, title, str(txt_path), content)
    return target


def should_skip(output_dir: Path, txt_path: Path, overwrite: bool) -> bool:
    return not overwrite and (output_dir / txt_path.with_suffix(".md").name).exists()


def run_batch(
    input_path: Path,
    output_dir: Path,
    overwrite: bool = False,
    workers: int = 1,
) -> int:
    load_env_file()
    input_path = input_path.expanduser()

    if input_path.is_file():
        txt_files = [input_path]
    elif input_path.is_dir():
        txt_files = sorted(f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() == ".txt")
    else:
        raise VideoNoteError(f"Input path does not exist: {input_path}")

    if not txt_files:
        raise VideoNoteError(f"No .txt files found in {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    pending = [f for f in txt_files if not should_skip(output_dir, f, overwrite)]
    skipped = len(txt_files) - len(pending)

    print(f"Found {len(txt_files)} .txt file(s).")
    if skipped:
        print(f"Skipping {skipped} file(s) with existing output.")
    if not pending:
        print("Done.")
        return 0

    failures = 0
    workers = max(1, workers)
    if workers == 1:
        for index, txt_path in enumerate(pending, start=1):
            print(f"[{index}/{len(pending)}] {txt_path.name}")
            try:
                out = reformat_txt_file(txt_path, output_dir, overwrite=overwrite)
                print(f"  -> Created {out.name}")
            except VideoNoteError as exc:
                failures += 1
                print(f"  ERROR: {exc}", file=sys.stderr)
    else:
        print(f"Processing with {workers} worker(s).")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(reformat_txt_file, f, output_dir, overwrite): f for f in pending}
            done = 0
            for future in as_completed(futures):
                txt_path = futures[future]
                done += 1
                try:
                    out = future.result()
                    print(f"[{done}/{len(pending)}] Created {out.name}")
                except VideoNoteError as exc:
                    failures += 1
                    print(f"Error processing {txt_path.name}: {exc}", file=sys.stderr)

    if failures:
        print(f"\nDone with {failures} failure(s).", file=sys.stderr)
        return 1
    print(f"\nDone. {len(pending)} file(s) written to {output_dir}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reformat plain-text transcripts into readable markdown notes.")
    parser.add_argument("input_path", help="A .txt file or a directory containing .txt transcript files.")
    parser.add_argument("-o", "--output-dir", required=True, help="Directory for generated .md files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("-j", "--workers", type=int, default=3, help="Concurrent workers. Default: 3.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return run_batch(
            input_path=Path(args.input_path),
            output_dir=Path(args.output_dir),
            overwrite=args.overwrite,
            workers=args.workers,
        )
    except VideoNoteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
