import json
import os
import socket
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.adapters.base import AdapterError, KnowledgeAssets, PublishResult


NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
NOTION_TIMEOUT = 30


class NotionAdapter:
    name = "notion"

    def __init__(self, token: str, parent_page_id: str | None = None, database_id: str | None = None):
        self.token = token
        self.parent_page_id = parent_page_id
        self.database_id = database_id

    @classmethod
    def from_env(cls):
        token = os.environ.get("NOTION_TOKEN")
        database_id = os.environ.get("NOTION_DATABASE_ID")
        parent_page_id = os.environ.get("NOTION_PARENT_PAGE_ID")
        if not token or not (database_id or parent_page_id):
            return None
        return cls(token=token, parent_page_id=parent_page_id, database_id=database_id)

    def publish(self, output_dir: Path, metadata: dict, assets: KnowledgeAssets) -> PublishResult:
        title = str(metadata.get("title") or output_dir.name)
        if self.database_id:
            response = self._create_database_page(title, metadata, assets)
        else:
            markdown = self._build_markdown(metadata, assets)
            response = self._create_parent_page(title, markdown)
        url = response.get("url")

        return PublishResult(
            adapter_name=self.name,
            success=True,
            message="Published to Notion.",
            url=str(url) if url else None,
        )

    def _build_markdown(self, metadata: dict, assets: KnowledgeAssets) -> str:
        source = metadata.get("url") or ""
        return "\n\n".join(
            [
                assets.notes_outline.strip(),
                "## Cleaned Content",
                assets.cleaned_content.strip(),
                "## Source",
                str(source),
            ]
        ).strip()

    def _create_database_page(self, title: str, metadata: dict, assets: KnowledgeAssets) -> dict:
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": self._database_properties(title, metadata),
            "children": self._page_children(metadata, assets),
        }
        return self._post_page(payload)

    def _create_parent_page(self, title: str, markdown: str) -> dict:
        if not self.parent_page_id:
            raise AdapterError("NOTION_PARENT_PAGE_ID is required when NOTION_DATABASE_ID is not configured.")
        payload = {
            "parent": {"page_id": self.parent_page_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title[:2000],
                            }
                        }
                    ]
                }
            },
            "markdown": markdown,
        }
        return self._post_page(payload)

    def _database_properties(self, title: str, metadata: dict) -> dict:
        return {
            "Title": {"title": [{"text": {"content": title[:2000]}}]},
            "URL": {"url": str(metadata.get("url") or None) if metadata.get("url") else None},
            "Source": {"rich_text": self._rich_text(str(metadata.get("source") or ""))},
            "Author": {"rich_text": self._rich_text(str(metadata.get("author") or ""))},
            "Tags": {
                "multi_select": [
                    {"name": str(tag)[:100]}
                    for tag in metadata.get("tags", [])
                    if str(tag).strip()
                ]
            },
            "Duration": {"rich_text": self._rich_text(str(metadata.get("duration") or ""))},
            "Language": {"rich_text": self._rich_text(str(metadata.get("language") or ""))},
            "Status": {"select": {"name": str(metadata.get("status") or "Processed")}},
            "Created At": {"date": {"start": str(metadata.get("created_at") or "")} if metadata.get("created_at") else None},
            "Summary": {"rich_text": self._rich_text(str(metadata.get("summary") or ""))},
            "Processing Method": {"rich_text": self._rich_text(str(metadata.get("processing_method") or ""))},
        }

    def _page_children(self, metadata: dict, assets: KnowledgeAssets) -> list[dict]:
        sections = [
            ("Summary", str(metadata.get("summary") or "")),
            ("Key Topics", self._extract_section(assets.notes_outline, ["# Key Takeaways", "## Key Takeaways"])),
            ("Action Items", self._extract_section(assets.notes_outline, ["# Action Items", "## Action Items"])),
            ("Formatted Transcript", assets.formatted_transcript),
            ("Cleaned Content", assets.cleaned_content),
            ("Notes Outline", assets.notes_outline),
        ]
        children: list[dict] = []
        for heading, content in sections:
            children.append(self._heading_block(heading))
            for chunk in self._chunks(content.strip() or "No content."):
                children.append(self._paragraph_block(chunk))
        return children[:100]

    def _extract_section(self, markdown: str, headings: list[str]) -> str:
        lines = markdown.splitlines()
        in_section = False
        collected: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped in headings:
                in_section = True
                continue
            if in_section and stripped.startswith("#"):
                break
            if in_section:
                collected.append(line)
        return "\n".join(collected).strip()

    def _heading_block(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": self._rich_text(text)},
        }

    def _paragraph_block(self, text: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": self._rich_text(text)},
        }

    def _rich_text(self, text: str) -> list[dict]:
        if not text:
            return []
        return [{"type": "text", "text": {"content": text[:2000]}}]

    def _chunks(self, text: str, size: int = 1800) -> list[str]:
        return [text[index : index + size] for index in range(0, len(text), size)] or [""]

    def _post_page(self, payload: dict) -> dict:
        request = Request(
            f"{NOTION_API_BASE_URL}/pages",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_VERSION,
            },
        )

        try:
            with urlopen(request, timeout=NOTION_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AdapterError(f"Notion API failed with HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise AdapterError(f"Notion is unavailable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AdapterError("Notion returned invalid JSON.") from exc
