import json
import os
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.utils import VideoNoteError, detect_content_language


DEFAULT_OLLAMA_BASE_URL = "http://100.111.104.41:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_CONNECT_TIMEOUT = 5
DEFAULT_GENERATE_TIMEOUT = 120
DEFAULT_LLM_PROVIDER = "ollama"

OPENAI_BASE_URL = "https://api.openai.com/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
CLAUDE_BASE_URL = "https://api.anthropic.com/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_MODELS = {
    "ollama": DEFAULT_OLLAMA_MODEL,
    "openai": "gpt-5.4-mini",
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-3.5-flash",
    "deepseek": "deepseek-v4-flash",
    "qwen": "qwen-plus",
}

LANGUAGE_LABELS = {
    "english": "English",
    "chinese": "Chinese",
}

OUTPUT_HEADINGS = {
    "english": {
        "edited_transcript": "Edited Transcript",
        "executive_summary": "Executive Summary",
        "key_takeaways": "Key Takeaways",
        "structured_outline": "Structured Outline",
        "action_items": "Action Items",
    },
    "chinese": {
        "edited_transcript": "编辑后文本",
        "executive_summary": "执行摘要",
        "key_takeaways": "关键要点",
        "structured_outline": "结构化大纲",
        "action_items": "行动项",
    },
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None


def get_ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


def get_llm_provider() -> str:
    return os.environ.get("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()


def get_llm_model(provider: str) -> str:
    return os.environ.get("LLM_MODEL") or os.environ.get(f"{provider.upper()}_MODEL") or DEFAULT_MODELS[provider]


def get_llm_config() -> LLMConfig:
    provider = get_llm_provider()
    if provider not in DEFAULT_MODELS:
        supported = ", ".join(sorted(DEFAULT_MODELS))
        raise VideoNoteError(f"Unsupported LLM provider '{provider}'. Supported providers: {supported}.")

    if provider == "ollama":
        return LLMConfig(
            provider=provider,
            model=os.environ.get("LLM_MODEL") or get_ollama_model(),
            base_url=get_ollama_base_url(),
        )

    base_url = os.environ.get(f"{provider.upper()}_BASE_URL") or {
        "openai": OPENAI_BASE_URL,
        "claude": CLAUDE_BASE_URL,
        "gemini": GEMINI_BASE_URL,
        "deepseek": DEEPSEEK_BASE_URL,
        "qwen": QWEN_BASE_URL,
    }[provider]
    api_key = os.environ.get(f"{provider.upper()}_API_KEY")
    if provider == "claude":
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise VideoNoteError(f"{provider.upper()}_API_KEY is required for LLM provider '{provider}'.")

    return LLMConfig(
        provider=provider,
        model=get_llm_model(provider),
        base_url=base_url.rstrip("/"),
        api_key=api_key,
    )


def _read_json(url: str, timeout: int) -> dict:
    request = Request(url, method="GET", headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise VideoNoteError(f"Ollama request failed with HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise VideoNoteError(f"Ollama is unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VideoNoteError("Ollama returned invalid JSON.") from exc


def _post_json(
    url: str,
    payload: dict,
    timeout: int,
    headers: dict | None = None,
    provider_name: str = "Ollama",
) -> dict:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=request_headers,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoNoteError(f"{provider_name} request failed with HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise VideoNoteError(f"{provider_name} is unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VideoNoteError(f"{provider_name} returned invalid JSON.") from exc


def test_connection(base_url: str | None = None, timeout: int = DEFAULT_CONNECT_TIMEOUT) -> dict:
    return _read_json(f"{base_url or get_ollama_base_url()}/api/tags", timeout)


def generate_text(
    prompt: str,
    base_url: str | None = None,
    model: str | None = None,
    timeout: int = DEFAULT_GENERATE_TIMEOUT,
) -> str:
    payload = {
        "model": model or get_ollama_model(),
        "prompt": prompt,
        "stream": False,
    }
    result = _post_json(f"{base_url or get_ollama_base_url()}/api/generate", payload, timeout)
    text = str(result.get("response") or "").strip()

    if not text:
        raise VideoNoteError("Ollama returned an empty response.")

    return text


def _openai_compatible_generate(config: LLMConfig, prompt: str) -> str:
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
    }
    result = _post_json(
        f"{config.base_url}/chat/completions",
        payload,
        DEFAULT_GENERATE_TIMEOUT,
        headers={"Authorization": f"Bearer {config.api_key}"},
        provider_name=config.provider.upper(),
    )
    choices = result.get("choices") or []
    if not choices:
        raise VideoNoteError(f"{config.provider.upper()} returned no choices.")

    text = str(choices[0].get("message", {}).get("content") or "").strip()
    if not text:
        raise VideoNoteError(f"{config.provider.upper()} returned an empty response.")

    return text


def _claude_generate(config: LLMConfig, prompt: str) -> str:
    payload = {
        "model": config.model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    result = _post_json(
        f"{config.base_url}/messages",
        payload,
        DEFAULT_GENERATE_TIMEOUT,
        headers={
            "x-api-key": str(config.api_key),
            "anthropic-version": "2023-06-01",
        },
        provider_name="Claude",
    )
    parts = result.get("content") or []
    text = "\n".join(str(part.get("text") or "") for part in parts if part.get("type") == "text").strip()
    if not text:
        raise VideoNoteError("Claude returned an empty response.")

    return text


def _gemini_generate(config: LLMConfig, prompt: str) -> str:
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ]
    }
    model = quote(config.model, safe="")
    result = _post_json(
        f"{config.base_url}/models/{model}:generateContent?key={config.api_key}",
        payload,
        DEFAULT_GENERATE_TIMEOUT,
        provider_name="Gemini",
    )
    candidates = result.get("candidates") or []
    if not candidates:
        raise VideoNoteError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "\n".join(str(part.get("text") or "") for part in parts).strip()
    if not text:
        raise VideoNoteError("Gemini returned an empty response.")

    return text


def generate_provider_text(prompt: str, config: LLMConfig | None = None) -> str:
    config = config or get_llm_config()
    if config.provider == "ollama":
        return generate_text(prompt, base_url=config.base_url, model=config.model)
    if config.provider in {"openai", "deepseek", "qwen"}:
        return _openai_compatible_generate(config, prompt)
    if config.provider == "claude":
        return _claude_generate(config, prompt)
    if config.provider == "gemini":
        return _gemini_generate(config, prompt)

    raise VideoNoteError(f"Unsupported LLM provider '{config.provider}'.")


def cleaned_content_prompt(title: str, transcript: str) -> str:
    language = detect_content_language(transcript)
    language_label = LANGUAGE_LABELS[language]
    headings = OUTPUT_HEADINGS[language]

    return "\n".join(
        [
            "You are a professional transcript editor, knowledge distillation assistant, and content structuring specialist.",
            "",
            "Transform the raw transcript into a professionally edited transcript.",
            f"The transcript's primary language is {language_label}.",
            f"Write the entire output in {language_label}, including section headings.",
            "",
            "GENERAL RULES",
            "- Preserve the original meaning and substantive content.",
            "- Never add facts, opinions, examples, interpretations, or conclusions that are not present in the source material.",
            "- Remove filler words, verbal repetitions, speech disfluencies, false starts, and redundant phrasing.",
            "- Remove irrelevant greetings, sponsorships, calls to action, promotional content, and other non-substantive introductions when they are not part of the core discussion.",
            "- Convert spoken language into natural written language.",
            "- Merge fragmented spoken sentences into coherent paragraphs.",
            "- Preserve the original tone and viewpoint.",
            "- Maintain the original logical sequence of ideas.",
            "- Preserve speaker labels when available.",
            "- Preserve timestamps when practical.",
            "",
            "OUTPUT RULES",
            "- Output only the Edited Transcript.",
            "- Do not explain your editing process.",
            "- Do not include commentary, notes, or meta explanations.",
            "- Do not include any text outside the requested section.",
            "",
            f"# {headings['edited_transcript']}",
            "",
            f"Title: {title}",
            "",
            "Transcript:",
            transcript.strip(),
        ]
    )


def notes_outline_prompt(title: str, transcript: str) -> str:
    language = detect_content_language(transcript)
    language_label = LANGUAGE_LABELS[language]
    headings = OUTPUT_HEADINGS[language]

    return "\n".join(
        [
            "You are a professional transcript editor, knowledge distillation assistant, and content structuring specialist.",
            "",
            "Transform the raw transcript into clean, readable, structured knowledge while preserving the speaker's original meaning, arguments, examples, insights, and overall intent.",
            f"The transcript's primary language is {language_label}.",
            f"Write the entire output in {language_label}, including section headings.",
            "",
            "GENERAL RULES",
            "- Preserve the original meaning and substantive content.",
            "- Never add facts, opinions, examples, interpretations, or conclusions that are not present in the source material.",
            "- Remove filler words, verbal repetitions, speech disfluencies, false starts, and redundant phrasing.",
            "- Remove irrelevant greetings, sponsorships, calls to action, promotional content, and other non-substantive introductions when they are not part of the core discussion.",
            "- Convert spoken language into natural written language.",
            "- Preserve the original tone and viewpoint.",
            "- Maintain the original logical sequence of ideas.",
            "- When transcript quality is poor, infer punctuation, sentence boundaries, and paragraph breaks, but never invent content.",
            "",
            "DEFAULT OUTPUT",
            "Generate the following sections in this order:",
            f"# {headings['executive_summary']}",
            f"# {headings['key_takeaways']}",
            f"# {headings['structured_outline']}",
            f"# {headings['action_items']}",
            "",
            "Executive Summary:",
            "- 3-8 concise paragraphs.",
            "- Focus on what matters most.",
            "- Avoid unnecessary detail.",
            "",
            "Key Takeaways:",
            "- Use concise bullet points.",
            "- Avoid repetition.",
            "- Focus on transferable insights.",
            "",
            "Structured Outline:",
            "- Organize ideas hierarchically.",
            "- Use numbered sections when appropriate.",
            "- Preserve the speaker's logical flow.",
            "",
            "Action Items:",
            "- Use checkbox format.",
            "- Include only actions clearly implied or stated by the speaker.",
            "- Omit the Action Items section if there are no practical recommendations, tasks, habits, workflows, implementation steps, or actionable advice.",
            "",
            "OUTPUT RULES",
            "- Output only the requested result.",
            "- Do not explain your editing process.",
            "- Do not include commentary, notes, or meta explanations.",
            "- Do not include any text outside the requested sections.",
            "",
            "Transcript:",
            transcript.strip(),
        ]
    )


def generate_llm_documents(title: str, transcript: str) -> tuple[str, str]:
    config = get_llm_config()
    if config.provider == "ollama":
        test_connection(base_url=config.base_url)

    cleaned_content = generate_provider_text(cleaned_content_prompt(title, transcript), config)
    notes_outline = generate_provider_text(notes_outline_prompt(title, transcript), config)
    return cleaned_content, notes_outline
