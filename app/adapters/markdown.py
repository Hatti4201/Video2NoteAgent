from pathlib import Path

from app.adapters.base import KnowledgeAssets, PublishResult


class MarkdownAdapter:
    name = "local_markdown"

    def publish(self, output_dir: Path, metadata: dict, assets: KnowledgeAssets) -> PublishResult:
        return PublishResult(
            adapter_name=self.name,
            success=True,
            message=f"Local markdown assets available in {output_dir}",
        )
