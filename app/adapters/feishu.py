import json
import os
import socket
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.adapters.base import AdapterError, KnowledgeAssets, PublishResult


FEISHU_API_BASE_URL = "https://open.feishu.cn/open-apis"
FEISHU_TIMEOUT = 30
FEISHU_DOC_BASE_URL = "https://www.feishu.cn/docx"
MAX_BLOCK_TEXT_LENGTH = 1800


class FeishuAdapter:
    name = "feishu"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        parent_folder_token: str,
        bitable_app_token: str | None = None,
        bitable_table_id: str | None = None,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.parent_folder_token = parent_folder_token
        self.bitable_app_token = bitable_app_token
        self.bitable_table_id = bitable_table_id

    @classmethod
    def from_env(cls):
        app_id = os.environ.get("FEISHU_APP_ID")
        app_secret = os.environ.get("FEISHU_APP_SECRET")
        parent_folder_token = os.environ.get("FEISHU_VIDEO_NOTES_FOLDER_TOKEN") or os.environ.get("FEISHU_PARENT_FOLDER_TOKEN")
        if not app_id or not app_secret or not parent_folder_token:
            return None

        return cls(
            app_id=app_id,
            app_secret=app_secret,
            parent_folder_token=parent_folder_token,
            bitable_app_token=os.environ.get("FEISHU_BITABLE_APP_TOKEN") or os.environ.get("FEISHU_VIDEO_DATABASE_ID"),
            bitable_table_id=os.environ.get("FEISHU_BITABLE_TABLE_ID"),
        )

    def publish(self, output_dir: Path, metadata: dict, assets: KnowledgeAssets) -> PublishResult:
        title = str(metadata.get("title") or output_dir.name)
        token = self._get_tenant_access_token()
        document_id = self._create_document(token, title)
        doc_url = f"{FEISHU_DOC_BASE_URL}/{document_id}"
        self._append_blocks(token, document_id, self._build_blocks(metadata, assets))
        if self.bitable_app_token and self.bitable_table_id:
            self._create_bitable_record(token, metadata, doc_url)

        return PublishResult(
            adapter_name=self.name,
            success=True,
            message="Published to Feishu.",
            url=doc_url,
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

    def _get_tenant_access_token(self) -> str:
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        response = self._request_json(
            "/auth/v3/tenant_access_token/internal",
            payload=payload,
            method="POST",
        )
        token = response.get("tenant_access_token")
        if not token:
            raise AdapterError("Feishu did not return a tenant access token.")
        return str(token)

    def _create_document(self, token: str, title: str) -> str:
        payload = {
            "folder_token": self.parent_folder_token,
            "title": title[:2000],
        }
        response = self._request_json(
            "/docx/v1/documents",
            payload=payload,
            method="POST",
            token=token,
        )
        document = response.get("data", {}).get("document", {})
        document_id = document.get("document_id") or response.get("data", {}).get("document_id")
        if not document_id:
            raise AdapterError("Feishu did not return a document ID.")
        return str(document_id)

    def _append_blocks(self, token: str, document_id: str, blocks: list[dict]) -> None:
        if not blocks:
            blocks = [self._paragraph_block("No generated content.")]

        for offset in range(0, len(blocks), 50):
            self._request_json(
                f"/docx/v1/documents/{document_id}/blocks/{document_id}/children",
                payload={"children": blocks[offset : offset + 50]},
                method="POST",
                token=token,
            )

    def _build_blocks(self, metadata: dict, assets: KnowledgeAssets) -> list[dict]:
        blocks = [
            self._heading_block(1, str(metadata.get("title") or "Untitled Video")),
            self._paragraph_block(f"URL: {metadata.get('url') or ''}"),
            self._paragraph_block(f"Source: {metadata.get('source') or ''}"),
            self._paragraph_block(f"Author: {metadata.get('author') or ''}"),
            self._paragraph_block(f"Duration: {metadata.get('duration') or ''}"),
            self._paragraph_block(f"Language: {metadata.get('language') or ''}"),
            self._paragraph_block(f"Status: {metadata.get('status') or 'Processed'}"),
            self._paragraph_block(f"Created At: {metadata.get('created_at') or ''}"),
            self._paragraph_block(f"Processing Method: {metadata.get('processing_method') or ''}"),
        ]
        tags = ", ".join(str(tag) for tag in metadata.get("tags", []) if str(tag).strip())
        if tags:
            blocks.append(self._paragraph_block(f"Tags: {tags}"))

        for heading, content in [
            ("Summary", str(metadata.get("summary") or "")),
            ("Notes Outline", assets.notes_outline),
            ("Cleaned Content", assets.cleaned_content),
            ("Formatted Transcript", assets.formatted_transcript),
        ]:
            blocks.append(self._heading_block(1, heading))
            blocks.extend(self._markdown_to_blocks(content.strip() or "No content."))

        return blocks

    def _markdown_to_blocks(self, markdown: str) -> list[dict]:
        blocks: list[dict] = []
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("### "):
                blocks.append(self._heading_block(3, line[4:].strip()))
            elif line.startswith("## "):
                blocks.append(self._heading_block(2, line[3:].strip()))
            elif line.startswith("# "):
                blocks.append(self._heading_block(1, line[2:].strip()))
            elif line.startswith(("- ", "* ")):
                blocks.append(self._bullet_block(line[2:].strip()))
            elif self._is_numbered_list_item(line):
                blocks.append(self._numbered_block(line.split(".", 1)[1].strip()))
            else:
                for chunk in self._split_text(line):
                    blocks.append(self._paragraph_block(chunk))
        return blocks

    def _is_numbered_list_item(self, line: str) -> bool:
        prefix, dot, rest = line.partition(".")
        return bool(dot and prefix.isdigit() and rest.strip())

    def _heading_block(self, level: int, content: str) -> dict:
        block_type = {1: 3, 2: 4, 3: 5}.get(level, 3)
        return self._text_block(block_type, content)

    def _paragraph_block(self, content: str) -> dict:
        return self._text_block(2, content)

    def _bullet_block(self, content: str) -> dict:
        return self._text_block(12, content)

    def _numbered_block(self, content: str) -> dict:
        return self._text_block(13, content)

    def _text_block(self, block_type: int, content: str) -> dict:
        return {
            "block_type": block_type,
            "text": {
                "elements": [
                    {
                        "text_run": {
                            "content": content,
                            "text_element_style": {},
                        }
                    }
                ],
                "style": {},
            },
        }

    def _split_markdown_for_blocks(self, markdown: str) -> list[str]:
        return self._split_text(markdown)

    def _split_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        for paragraph in text.split("\n\n"):
            paragraph_text = paragraph.strip()
            if not paragraph_text:
                continue

            while len(paragraph_text) > MAX_BLOCK_TEXT_LENGTH:
                chunks.append(paragraph_text[:MAX_BLOCK_TEXT_LENGTH])
                paragraph_text = paragraph_text[MAX_BLOCK_TEXT_LENGTH:]
            chunks.append(paragraph_text)

        return chunks

    def _create_bitable_record(self, token: str, metadata: dict, doc_url: str) -> None:
        if not self.bitable_app_token or not self.bitable_table_id:
            return

        fields = {
            "Title": str(metadata.get("title") or ""),
            "URL": str(metadata.get("url") or ""),
            "Source": str(metadata.get("source") or ""),
            "Author": str(metadata.get("author") or ""),
            "Tags": ", ".join(str(tag) for tag in metadata.get("tags", []) if str(tag).strip()),
            "Duration": str(metadata.get("duration") or ""),
            "Language": str(metadata.get("language") or ""),
            "Status": str(metadata.get("status") or "Processed"),
            "Created At": str(metadata.get("created_at") or ""),
            "Summary": str(metadata.get("summary") or ""),
            "Processing Method": str(metadata.get("processing_method") or ""),
            "Doc URL": doc_url,
        }
        self._request_json(
            f"/bitable/v1/apps/{self.bitable_app_token}/tables/{self.bitable_table_id}/records",
            payload={"fields": fields},
            method="POST",
            token=token,
        )

    def _request_json(
        self,
        path: str,
        payload: dict,
        method: str,
        token: str | None = None,
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = Request(
            f"{FEISHU_API_BASE_URL}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method=method,
            headers=headers,
        )

        try:
            with urlopen(request, timeout=FEISHU_TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AdapterError(f"Feishu API failed with HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise AdapterError(f"Feishu is unavailable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AdapterError("Feishu returned invalid JSON.") from exc

        code = data.get("code", 0)
        if code != 0:
            message = data.get("msg") or data.get("message") or "unknown error"
            raise AdapterError(f"Feishu API failed with code {code}: {message}")

        return data
