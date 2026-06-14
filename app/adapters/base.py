from dataclasses import dataclass
import json
from pathlib import Path


REQUIRED_ASSET_FILES = [
    "01_raw_transcript.txt",
    "02_formatted_transcript.md",
    "03_cleaned_content.md",
    "04_notes_outline.md",
]


class AdapterError(Exception):
    """Readable adapter error for optional publishing failures."""


@dataclass(frozen=True)
class KnowledgeAssets:
    metadata: dict
    raw_transcript: str
    formatted_transcript: str
    cleaned_content: str
    notes_outline: str


@dataclass(frozen=True)
class PublishResult:
    adapter_name: str
    success: bool
    message: str
    url: str | None = None


def load_assets(output_dir: Path) -> KnowledgeAssets:
    metadata_path = output_dir / "metadata.json"
    if not metadata_path.exists():
        raise AdapterError(f"Missing metadata file: {metadata_path}")

    missing_files = [
        file_name
        for file_name in REQUIRED_ASSET_FILES
        if not (output_dir / file_name).exists()
    ]
    if missing_files:
        raise AdapterError(f"Missing output files: {', '.join(missing_files)}")

    return KnowledgeAssets(
        metadata=json.loads(metadata_path.read_text(encoding="utf-8")),
        raw_transcript=(output_dir / "01_raw_transcript.txt").read_text(encoding="utf-8"),
        formatted_transcript=(output_dir / "02_formatted_transcript.md").read_text(encoding="utf-8"),
        cleaned_content=(output_dir / "03_cleaned_content.md").read_text(encoding="utf-8"),
        notes_outline=(output_dir / "04_notes_outline.md").read_text(encoding="utf-8"),
    )
