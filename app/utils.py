from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


OUTPUT_DIR = Path("output")
FOLDER_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YTDLP_DATE_RE = re.compile(r"^\d{8}$")
CJK_RE = re.compile(r"[\u3400-\u9fff]")


class VideoNoteError(Exception):
    """Readable application error for expected failures."""


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_folder_part(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return safe[:80].strip("-") or "untitled-video"


def output_folder_date(value: str | None = None) -> str:
    if value and FOLDER_DATE_RE.match(value):
        return value
    if value and YTDLP_DATE_RE.match(value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return datetime.now(timezone.utc).date().isoformat()


def create_video_output_dir(title: str, video_date: str | None = None) -> Path:
    output_root = ensure_output_dir()
    base_name = f"{output_folder_date(video_date)}-{safe_folder_part(title)}"
    output_dir = output_root / base_name
    counter = 2

    while output_dir.exists():
        output_dir = output_root / f"{base_name}-{counter}"
        counter += 1

    output_dir.mkdir(parents=True)
    return output_dir


def write_metadata(
    output_dir: Path,
    title: str,
    url: str,
    source: str,
    created_at: str,
    author: str = "",
    duration: str = "",
    language: str = "",
    tags: list[str] | None = None,
    status: str = "Processed",
    summary: str = "",
    processing_method: str = "",
) -> None:
    metadata = {
        "title": title or "",
        "url": url or "",
        "source": source or "",
        "author": author or "",
        "duration": str(duration or ""),
        "language": language or "",
        "tags": tags or [],
        "status": status or "Processed",
        "created_at": created_at or "",
        "summary": summary or "",
        "processing_method": processing_method or "",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def detect_content_language(text: str) -> str:
    compact = "".join(ch for ch in text if not ch.isspace())
    if not compact:
        return "english"

    cjk_count = len(CJK_RE.findall(compact))
    if cjk_count >= 5 or cjk_count / max(len(compact), 1) >= 0.15:
        return "chinese"

    return "english"


def load_env_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip('"').strip("'")
