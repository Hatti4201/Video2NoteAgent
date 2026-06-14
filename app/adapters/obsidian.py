import os
import shlex
from pathlib import Path

from app.adapters.base import AdapterError, KnowledgeAssets, PublishResult
from app.utils import safe_folder_part


DEFAULT_OBSIDIAN_FOLDER = "Video Notes"


def parse_vault_path(value: str) -> Path:
    parts = shlex.split(value)
    normalized = parts[0] if len(parts) == 1 else value
    return Path(normalized).expanduser()


class ObsidianAdapter:
    name = "obsidian"

    def __init__(self, vault_path: Path, folder: str = DEFAULT_OBSIDIAN_FOLDER):
        self.vault_path = vault_path
        self.folder = folder.strip("/") or DEFAULT_OBSIDIAN_FOLDER

    @classmethod
    def from_env(cls):
        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            return None

        return cls(
            vault_path=parse_vault_path(vault_path),
            folder=os.environ.get("OBSIDIAN_FOLDER", DEFAULT_OBSIDIAN_FOLDER),
        )

    def publish(self, output_dir: Path, metadata: dict, assets: KnowledgeAssets) -> PublishResult:
        if not self.vault_path.exists():
            raise AdapterError(f"Obsidian vault path does not exist: {self.vault_path}")
        if not self.vault_path.is_dir():
            raise AdapterError(f"Obsidian vault path is not a directory: {self.vault_path}")

        target_dir = self.vault_path / self.folder
        target_dir.mkdir(parents=True, exist_ok=True)

        title = str(metadata.get("title") or output_dir.name)
        target_path = self._available_path(target_dir, safe_folder_part(title))
        target_path.write_text(self._build_markdown(metadata, assets), encoding="utf-8")

        return PublishResult(
            adapter_name=self.name,
            success=True,
            message=f"Published to Obsidian: {target_path}",
            url=str(target_path),
        )

    def _available_path(self, target_dir: Path, base_name: str) -> Path:
        target_path = target_dir / f"{base_name}.md"
        counter = 2

        while target_path.exists():
            target_path = target_dir / f"{base_name}-{counter}.md"
            counter += 1

        return target_path

    def _build_markdown(self, metadata: dict, assets: KnowledgeAssets) -> str:
        title = str(metadata.get("title") or "Untitled Video")
        source = str(metadata.get("url") or "")
        created_at = str(metadata.get("created_at") or "")

        return "\n".join(
            [
                "---",
                f"title: {title}",
                f"source: {source}",
                f"created_at: {created_at}",
                "---",
                "",
                assets.notes_outline.strip(),
                "",
            ]
        )
