from pathlib import Path
import re

from app.utils import collapse_whitespace, write_text_file


TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_vtt(vtt_text: str) -> str:
    lines: list[str] = []
    previous = ""

    for raw_line in vtt_text.splitlines():
        line = raw_line.strip()

        if not line:
            continue
        if line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if TIMESTAMP_RE.match(line):
            continue
        if line.isdigit():
            continue

        cleaned = HTML_TAG_RE.sub("", line).replace("&amp;", "&")
        cleaned = collapse_whitespace(cleaned)
        if cleaned and cleaned != previous:
            lines.append(cleaned)
            previous = cleaned

    return "\n".join(lines).strip()


def generate_transcript(subtitle_path: Path, output_path: Path | None = None) -> str:
    transcript = parse_vtt(subtitle_path.read_text(encoding="utf-8"))
    output_path = output_path or Path("output/transcript.txt")
    write_text_file(output_path, transcript + "\n")
    return transcript


def format_transcript_markdown(title: str, transcript: str, output_path: Path | None = None) -> str:
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    paragraphs = [
        " ".join(lines[index : index + 3])
        for index in range(0, len(lines), 3)
    ]

    markdown = "\n\n".join(
        [
            f"# {title}",
            "",
            "## Formatted Transcript",
            "",
            *paragraphs,
            "",
        ]
    )

    if output_path:
        write_text_file(output_path, markdown)

    return markdown
