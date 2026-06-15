import json
from urllib.error import URLError

from app.adapters import publish_output
from app.adapters.base import AdapterError, load_assets
from app.adapters.feishu import FeishuAdapter
from app.adapters.markdown import MarkdownAdapter
from app.adapters.notion import NotionAdapter
from app.adapters.obsidian import ObsidianAdapter


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def write_output_files(output_dir):
    output_dir.mkdir()
    (output_dir / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Sample Video",
                "url": "https://example.com/video",
                "source": "youtube",
                "author": "Sample Author",
                "duration": "123",
                "language": "en",
                "tags": ["sample"],
                "status": "Processed",
                "created_at": "2026-01-02T03:04:05+00:00",
                "summary": "Sample summary.",
                "processing_method": "youtube_subtitle",
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "01_raw_transcript.txt").write_text("Raw transcript", encoding="utf-8")
    (output_dir / "02_formatted_transcript.md").write_text("# Formatted", encoding="utf-8")
    (output_dir / "03_cleaned_content.md").write_text("Cleaned content", encoding="utf-8")
    (output_dir / "04_notes_outline.md").write_text("# Sample Video\n\n## Summary", encoding="utf-8")


def test_load_assets_reads_required_output_files(tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)

    assets = load_assets(output_dir)

    assert assets.metadata["title"] == "Sample Video"
    assert assets.raw_transcript == "Raw transcript"
    assert assets.notes_outline.startswith("# Sample Video")


def test_markdown_adapter_reports_local_assets(tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    result = MarkdownAdapter().publish(output_dir, assets.metadata, assets)

    assert result.adapter_name == "local_markdown"
    assert result.success
    assert str(output_dir) in result.message


def test_notion_adapter_creates_parent_page_with_markdown(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse({"url": "https://notion.so/sample"})

    monkeypatch.setattr("app.adapters.notion.urlopen", fake_urlopen)

    result = NotionAdapter("secret-token", parent_page_id="parent-page-id").publish(
        output_dir,
        assets.metadata,
        assets,
    )

    request, timeout = requests[0]
    payload = json.loads(request.data.decode("utf-8"))

    assert result.success
    assert result.url == "https://notion.so/sample"
    assert request.full_url == "https://api.notion.com/v1/pages"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert request.headers["Notion-version"] == "2026-03-11"
    assert payload["parent"] == {"page_id": "parent-page-id"}
    assert payload["properties"]["title"]["title"][0]["text"]["content"] == "Sample Video"
    assert "# Sample Video" in payload["markdown"]
    assert "Cleaned content" in payload["markdown"]


def test_notion_adapter_creates_database_page_with_metadata(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse({"url": "https://notion.so/database-page"})

    monkeypatch.setattr("app.adapters.notion.urlopen", fake_urlopen)

    result = NotionAdapter("secret-token", database_id="database-id").publish(
        output_dir,
        assets.metadata,
        assets,
    )

    request, _ = requests[0]
    payload = json.loads(request.data.decode("utf-8"))

    assert result.success
    assert result.url == "https://notion.so/database-page"
    assert payload["parent"] == {"database_id": "database-id"}
    assert payload["properties"]["Title"]["title"][0]["text"]["content"] == "Sample Video"
    assert payload["properties"]["URL"]["url"] == "https://example.com/video"
    assert payload["properties"]["Source"]["rich_text"][0]["text"]["content"] == "youtube"
    assert payload["properties"]["Author"]["rich_text"][0]["text"]["content"] == "Sample Author"
    assert payload["properties"]["Tags"]["multi_select"] == [{"name": "sample"}]
    assert payload["properties"]["Status"]["select"]["name"] == "Processed"
    assert payload["properties"]["Processing Method"]["rich_text"][0]["text"]["content"] == "youtube_subtitle"
    assert payload["children"][0]["type"] == "heading_2"
    assert any(block.get("heading_2", {}).get("rich_text", [{}])[0].get("text", {}).get("content") == "Notes Outline" for block in payload["children"] if block["type"] == "heading_2")


def test_notion_adapter_raises_adapter_error_on_connection_failure(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("app.adapters.notion.urlopen", fake_urlopen)

    try:
        NotionAdapter("secret-token", parent_page_id="parent-page-id").publish(
            output_dir,
            assets.metadata,
            assets,
        )
    except AdapterError as exc:
        assert "Notion is unavailable" in str(exc)
    else:
        raise AssertionError("Expected AdapterError")


def test_publish_output_keeps_local_success_when_notion_fails(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    monkeypatch.setenv("NOTION_TOKEN", "secret-token")
    monkeypatch.setenv("NOTION_DATABASE_ID", "database-id")
    monkeypatch.delenv("NOTION_PARENT_PAGE_ID", raising=False)

    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("app.adapters.notion.urlopen", fake_urlopen)

    results = publish_output(output_dir)

    assert [result.adapter_name for result in results] == ["local_markdown", "notion"]
    assert results[0].success
    assert not results[1].success
    assert (output_dir / "04_notes_outline.md").exists()


def test_obsidian_adapter_from_env_is_disabled_without_vault(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    assert ObsidianAdapter.from_env() is None


def test_obsidian_adapter_from_env_accepts_shell_escaped_path(monkeypatch, tmp_path):
    vault_dir = tmp_path / "Mobile Documents" / "iCloud~md~obsidian" / "Vault"
    vault_dir.mkdir(parents=True)
    monkeypatch.setenv(
        "OBSIDIAN_VAULT_PATH",
        str(vault_dir).replace("Mobile Documents", "Mobile\\ Documents"),
    )

    adapter = ObsidianAdapter.from_env()

    assert adapter is not None
    assert adapter.vault_path == vault_dir


def test_obsidian_adapter_writes_note_to_vault_folder(tmp_path):
    output_dir = tmp_path / "sample"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    result = ObsidianAdapter(vault_dir, "Video Notes").publish(
        output_dir,
        assets.metadata,
        assets,
    )

    target_path = vault_dir / "Video Notes" / "sample-video.md"
    assert result.success
    assert result.url == str(target_path)
    assert target_path.exists()

    content = target_path.read_text(encoding="utf-8")
    assert "title: Sample Video" in content
    assert "source: https://example.com/video" in content
    assert "# Sample Video" in content


def test_obsidian_adapter_avoids_overwriting_existing_notes(tmp_path):
    output_dir = tmp_path / "sample"
    vault_dir = tmp_path / "vault"
    target_dir = vault_dir / "Video Notes"
    target_dir.mkdir(parents=True)
    (target_dir / "sample-video.md").write_text("Existing note", encoding="utf-8")
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    result = ObsidianAdapter(vault_dir).publish(output_dir, assets.metadata, assets)

    assert result.url == str(target_dir / "sample-video-2.md")
    assert (target_dir / "sample-video.md").read_text(encoding="utf-8") == "Existing note"
    assert (target_dir / "sample-video-2.md").exists()


def test_obsidian_adapter_reports_invalid_vault_path(tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    try:
        ObsidianAdapter(tmp_path / "missing-vault").publish(output_dir, assets.metadata, assets)
    except AdapterError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected AdapterError")


def test_publish_output_keeps_local_success_when_obsidian_fails(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_PARENT_PAGE_ID", raising=False)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path / "missing-vault"))

    results = publish_output(output_dir)

    assert [result.adapter_name for result in results] == ["local_markdown", "obsidian"]
    assert results[0].success
    assert not results[1].success
    assert (output_dir / "04_notes_outline.md").exists()


def test_feishu_adapter_from_env_is_disabled_without_configuration(monkeypatch):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    monkeypatch.delenv("FEISHU_PARENT_FOLDER_TOKEN", raising=False)

    assert FeishuAdapter.from_env() is None


def test_feishu_adapter_from_env_uses_video_folder_and_bitable(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "app-id")
    monkeypatch.setenv("FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("FEISHU_PARENT_FOLDER_TOKEN", "old-folder")
    monkeypatch.setenv("FEISHU_VIDEO_NOTES_FOLDER_TOKEN", "video-folder")
    monkeypatch.setenv("FEISHU_BITABLE_APP_TOKEN", "bitable-app")
    monkeypatch.setenv("FEISHU_BITABLE_TABLE_ID", "table-id")

    adapter = FeishuAdapter.from_env()

    assert adapter is not None
    assert adapter.parent_folder_token == "video-folder"
    assert adapter.bitable_app_token == "bitable-app"
    assert adapter.bitable_table_id == "table-id"


def test_feishu_adapter_creates_document_and_appends_blocks(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if request.full_url.endswith("/auth/v3/tenant_access_token/internal"):
            return FakeResponse({"code": 0, "tenant_access_token": "tenant-token"})
        if request.full_url.endswith("/docx/v1/documents"):
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "document": {
                            "document_id": "doc-token",
                        }
                    },
                }
            )
        if request.full_url.endswith("/docx/v1/documents/doc-token/blocks/doc-token/children"):
            return FakeResponse({"code": 0, "data": {}})
        raise AssertionError(f"Unexpected Feishu URL: {request.full_url}")

    monkeypatch.setattr("app.adapters.feishu.urlopen", fake_urlopen)

    result = FeishuAdapter("app-id", "app-secret", "folder-token").publish(
        output_dir,
        assets.metadata,
        assets,
    )

    token_request, _ = requests[0]
    create_request, _ = requests[1]
    append_request, _ = requests[2]
    token_payload = json.loads(token_request.data.decode("utf-8"))
    create_payload = json.loads(create_request.data.decode("utf-8"))
    append_payload = json.loads(append_request.data.decode("utf-8"))

    assert result.success
    assert result.url == "https://www.feishu.cn/docx/doc-token"
    assert token_payload == {"app_id": "app-id", "app_secret": "app-secret"}
    assert create_request.headers["Authorization"] == "Bearer tenant-token"
    assert create_payload == {"folder_token": "folder-token", "title": "Sample Video"}
    assert append_request.headers["Authorization"] == "Bearer tenant-token"
    assert append_payload["index"] == 0
    assert append_payload["children"][0]["block_type"] == 3
    assert append_payload["children"][0]["text"]["elements"][0]["text_run"]["content"] == "Sample Video"
    assert any(child["block_type"] == 4 for child in append_payload["children"])


def test_feishu_adapter_creates_bitable_record_when_configured(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if request.full_url.endswith("/auth/v3/tenant_access_token/internal"):
            return FakeResponse({"code": 0, "tenant_access_token": "tenant-token"})
        if request.full_url.endswith("/docx/v1/documents"):
            return FakeResponse({"code": 0, "data": {"document": {"document_id": "doc-token"}}})
        if request.full_url.endswith("/docx/v1/documents/doc-token/blocks/doc-token/children"):
            return FakeResponse({"code": 0, "data": {}})
        if request.full_url.endswith("/bitable/v1/apps/app-token/tables/table-id/records"):
            return FakeResponse({"code": 0, "data": {"record": {"record_id": "record-id"}}})
        raise AssertionError(f"Unexpected Feishu URL: {request.full_url}")

    monkeypatch.setattr("app.adapters.feishu.urlopen", fake_urlopen)

    result = FeishuAdapter(
        "app-id",
        "app-secret",
        "folder-token",
        bitable_app_token="app-token",
        bitable_table_id="table-id",
    ).publish(output_dir, assets.metadata, assets)

    bitable_request = requests[-1][0]
    bitable_payload = json.loads(bitable_request.data.decode("utf-8"))

    assert result.url == "https://www.feishu.cn/docx/doc-token"
    assert bitable_request.headers["Authorization"] == "Bearer tenant-token"
    assert bitable_payload["fields"]["Title"] == "Sample Video"
    assert bitable_payload["fields"]["URL"] == "https://example.com/video"
    assert bitable_payload["fields"]["Doc URL"] == "https://www.feishu.cn/docx/doc-token"
    assert bitable_payload["fields"]["Processing Method"] == "youtube_subtitle"


def test_feishu_adapter_raises_adapter_error_on_connection_failure(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("app.adapters.feishu.urlopen", fake_urlopen)

    try:
        FeishuAdapter("app-id", "app-secret", "folder-token").publish(
            output_dir,
            assets.metadata,
            assets,
        )
    except AdapterError as exc:
        assert "Feishu is unavailable" in str(exc)
    else:
        raise AssertionError("Expected AdapterError")


def test_feishu_adapter_raises_adapter_error_on_empty_token(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    assets = load_assets(output_dir)

    def fake_urlopen(request, timeout):
        return FakeResponse({"code": 0})

    monkeypatch.setattr("app.adapters.feishu.urlopen", fake_urlopen)

    try:
        FeishuAdapter("app-id", "app-secret", "folder-token").publish(
            output_dir,
            assets.metadata,
            assets,
        )
    except AdapterError as exc:
        assert "tenant access token" in str(exc)
    else:
        raise AssertionError("Expected AdapterError")


def test_publish_output_keeps_local_success_when_feishu_fails(monkeypatch, tmp_path):
    output_dir = tmp_path / "sample"
    write_output_files(output_dir)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_PARENT_PAGE_ID", raising=False)
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    monkeypatch.setenv("FEISHU_APP_ID", "app-id")
    monkeypatch.setenv("FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("FEISHU_PARENT_FOLDER_TOKEN", "folder-token")

    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("app.adapters.feishu.urlopen", fake_urlopen)

    results = publish_output(output_dir)

    assert [result.adapter_name for result in results] == ["local_markdown", "feishu"]
    assert results[0].success
    assert not results[1].success
    assert (output_dir / "04_notes_outline.md").exists()
