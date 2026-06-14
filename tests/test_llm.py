import json
from urllib.error import URLError

import pytest

from app import llm
from app.utils import VideoNoteError


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_generate_text_posts_to_ollama_generate(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse({"response": "Hello from Ollama."})

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    response = llm.generate_text(
        "Say hello.",
        base_url="http://ollama.example",
        model="qwen3:8b",
        timeout=10,
    )

    request, timeout = requests[0]
    payload = json.loads(request.data.decode("utf-8"))

    assert response == "Hello from Ollama."
    assert request.full_url == "http://ollama.example/api/generate"
    assert timeout == 10
    assert payload == {
        "model": "qwen3:8b",
        "prompt": "Say hello.",
        "stream": False,
    }


def test_test_connection_raises_readable_error_on_connection_failure(monkeypatch):
    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    with pytest.raises(VideoNoteError, match="Ollama is unavailable"):
        llm.test_connection(base_url="http://ollama.example")


def test_generate_text_rejects_empty_response(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"response": ""})

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    with pytest.raises(VideoNoteError, match="empty response"):
        llm.generate_text("Say hello.", base_url="http://ollama.example")


def test_get_llm_config_reads_qwen_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("LLM_MODEL", "qwen-plus")
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_BASE_URL", "https://qwen.example/compatible-mode/v1")

    config = llm.get_llm_config()

    assert config.provider == "qwen"
    assert config.model == "qwen-plus"
    assert config.api_key == "qwen-key"
    assert config.base_url == "https://qwen.example/compatible-mode/v1"


def test_qwen_generation_uses_openai_compatible_chat_completions(monkeypatch):
    requests = []
    config = llm.LLMConfig(
        provider="qwen",
        model="qwen-plus",
        base_url="https://qwen.example/compatible-mode/v1",
        api_key="qwen-key",
    )

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "Hello from Qwen.",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    response = llm.generate_provider_text("Say hello.", config)

    request, timeout = requests[0]
    payload = json.loads(request.data.decode("utf-8"))

    assert response == "Hello from Qwen."
    assert request.full_url == "https://qwen.example/compatible-mode/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer qwen-key"
    assert timeout == 120
    assert payload["model"] == "qwen-plus"
    assert payload["messages"] == [{"role": "user", "content": "Say hello."}]
    assert payload["stream"] is False


def test_qwen_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)

    with pytest.raises(VideoNoteError, match="QWEN_API_KEY"):
        llm.get_llm_config()


def test_generate_llm_documents_uses_selected_qwen_provider(monkeypatch):
    prompts = []
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("LLM_MODEL", "qwen-plus")
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_BASE_URL", "https://qwen.example/compatible-mode/v1")

    def fake_generate(prompt, config=None):
        prompts.append((prompt, config))
        return f"generated {len(prompts)}"

    monkeypatch.setattr(llm, "generate_provider_text", fake_generate)

    cleaned_content, notes_outline = llm.generate_llm_documents("Title", "Transcript")

    assert cleaned_content == "generated 1"
    assert notes_outline == "generated 2"
    assert prompts[0][1].provider == "qwen"
    assert "# Edited Transcript" in prompts[0][0]
    assert "# Executive Summary" in prompts[1][0]


def test_llm_prompts_use_chinese_headings_for_chinese_transcript():
    transcript = "这个视频解释如何整理笔记。你应该抓住主要观点。避免复制每一句话。"

    cleaned_prompt = llm.cleaned_content_prompt("中文标题", transcript)
    notes_prompt = llm.notes_outline_prompt("中文标题", transcript)

    assert "primary language is Chinese" in cleaned_prompt
    assert "Write the entire output in Chinese" in cleaned_prompt
    assert "# 编辑后文本" in cleaned_prompt
    assert "# 执行摘要" in notes_prompt
    assert "# 关键要点" in notes_prompt
    assert "# 结构化大纲" in notes_prompt
    assert "# 行动项" in notes_prompt
