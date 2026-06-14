from pathlib import Path

from app.adapters.base import AdapterError, KnowledgeAssets, PublishResult, load_assets
from app.adapters.feishu import FeishuAdapter
from app.adapters.markdown import MarkdownAdapter
from app.adapters.notion import NotionAdapter
from app.adapters.obsidian import ObsidianAdapter


def enabled_adapters() -> list:
    adapters = [MarkdownAdapter()]
    notion_adapter = NotionAdapter.from_env()
    if notion_adapter:
        adapters.append(notion_adapter)
    obsidian_adapter = ObsidianAdapter.from_env()
    if obsidian_adapter:
        adapters.append(obsidian_adapter)
    feishu_adapter = FeishuAdapter.from_env()
    if feishu_adapter:
        adapters.append(feishu_adapter)
    return adapters


def publish_output(output_dir: Path) -> list[PublishResult]:
    assets = load_assets(output_dir)
    results: list[PublishResult] = []

    for adapter in enabled_adapters():
        try:
            results.append(adapter.publish(output_dir, assets.metadata, assets))
        except AdapterError as exc:
            results.append(
                PublishResult(
                    adapter_name=adapter.name,
                    success=False,
                    message=str(exc),
                )
            )

    return results
