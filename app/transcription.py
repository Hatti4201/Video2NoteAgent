import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from app.storage.tos import TosConfig, delete_audio_from_tos, upload_audio_to_tos
from app.utils import VideoNoteError


DEFAULT_DOUBAO_RESOURCE_ID = "volc.seedasr.auc"
DEFAULT_DOUBAO_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
DEFAULT_DOUBAO_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
DEFAULT_DOUBAO_LANGUAGE = "zh-CN"
DEFAULT_DOUBAO_AUDIO_FORMAT = "mp3"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_POLL_INTERVAL_SECONDS = 2
DEFAULT_MAX_QUERY_ATTEMPTS = 150

DOUBAO_STATUS_SUCCESS = "20000000"
DOUBAO_STATUS_PROCESSING = {"20000001", "20000002"}


@dataclass(frozen=True)
class DoubaoASRConfig:
    app_id: str
    access_token: str
    resource_id: str
    submit_url: str
    query_url: str
    language: str
    audio_format: str
    enable_itn: bool
    enable_punc: bool
    enable_ddc: bool
    show_utterances: bool


VolcengineASRConfig = DoubaoASRConfig


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_transcription_provider() -> str:
    return os.environ.get("TRANSCRIPTION_PROVIDER", "").strip().lower()


def get_doubao_asr_config() -> DoubaoASRConfig:
    app_id = os.environ.get("DOUBAO_ASR_APP_ID", "").strip()
    access_token = os.environ.get("DOUBAO_ASR_ACCESS_TOKEN", "").strip()

    if not app_id or not access_token:
        raise VideoNoteError(
            "Doubao Speech ASR requires DOUBAO_ASR_APP_ID and DOUBAO_ASR_ACCESS_TOKEN. "
            "Do not use TOS IAM AK/SK for Doubao Speech ASR."
        )

    return DoubaoASRConfig(
        app_id=app_id,
        access_token=access_token,
        resource_id=os.environ.get("DOUBAO_ASR_RESOURCE_ID", DEFAULT_DOUBAO_RESOURCE_ID),
        submit_url=os.environ.get("DOUBAO_ASR_SUBMIT_URL", DEFAULT_DOUBAO_SUBMIT_URL),
        query_url=os.environ.get("DOUBAO_ASR_QUERY_URL", DEFAULT_DOUBAO_QUERY_URL),
        language=os.environ.get("DOUBAO_ASR_LANGUAGE", DEFAULT_DOUBAO_LANGUAGE),
        audio_format=os.environ.get("DOUBAO_ASR_AUDIO_FORMAT", DEFAULT_DOUBAO_AUDIO_FORMAT),
        enable_itn=_env_bool("DOUBAO_ASR_ENABLE_ITN", True),
        enable_punc=_env_bool("DOUBAO_ASR_ENABLE_PUNC", True),
        enable_ddc=_env_bool("DOUBAO_ASR_ENABLE_DDC", True),
        show_utterances=_env_bool("DOUBAO_ASR_SHOW_UTTERANCES", True),
    )


def get_volcengine_asr_config() -> DoubaoASRConfig:
    return get_doubao_asr_config()


def validate_audio_url(audio_url: str) -> None:
    parsed = urlparse(audio_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VideoNoteError("Doubao Speech ASR requires a public http(s) audio URL.")


def transcribe_audio_url(
    audio_url: str,
    config: DoubaoASRConfig | None = None,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    max_query_attempts: int = DEFAULT_MAX_QUERY_ATTEMPTS,
) -> str:
    validate_audio_url(audio_url)
    config = config or get_doubao_asr_config()
    task_id = str(uuid4())

    submit_doubao_asr_task(audio_url, task_id, config)
    return query_doubao_asr_result(
        task_id,
        config,
        poll_interval_seconds=poll_interval_seconds,
        max_query_attempts=max_query_attempts,
    )


def transcribe_audio_file_via_tos(
    file_path: str | Path,
    config: DoubaoASRConfig | None = None,
    tos_config: TosConfig | None = None,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    max_query_attempts: int = DEFAULT_MAX_QUERY_ATTEMPTS,
) -> str:
    upload = upload_audio_to_tos(file_path, tos_config)
    try:
        return transcribe_audio_url(
            upload.url,
            config=config,
            poll_interval_seconds=poll_interval_seconds,
            max_query_attempts=max_query_attempts,
        )
    finally:
        try:
            delete_audio_from_tos(upload.key, tos_config)
        except VideoNoteError as exc:
            print(f"Warning: {exc}", file=sys.stderr)


def submit_doubao_asr_task(
    audio_url: str,
    task_id: str,
    config: DoubaoASRConfig,
) -> None:
    payload = {
        "user": {
            "uid": "video-note-agent",
        },
        "audio": {
            "format": config.audio_format,
            "url": audio_url,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": config.enable_itn,
            "enable_punc": config.enable_punc,
            "enable_ddc": config.enable_ddc,
            "show_utterances": config.show_utterances,
        },
    }
    if config.language:
        payload["audio"]["language"] = config.language

    headers, _ = _post_volcengine_json(config.submit_url, payload, task_id, config, include_sequence=True)
    status_code = headers.get("X-Api-Status-Code")
    message = headers.get("X-Api-Message", "")
    logid = headers.get("X-Tt-Logid", "")
    if status_code != DOUBAO_STATUS_SUCCESS:
        raise VideoNoteError(
            f"Doubao Speech ASR submit failed with status {status_code}: {message}; logid={logid}"
        )
    if logid:
        print(f"Doubao Speech ASR submit logid={logid}", file=sys.stderr)


def query_doubao_asr_result(
    task_id: str,
    config: DoubaoASRConfig,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    max_query_attempts: int = DEFAULT_MAX_QUERY_ATTEMPTS,
) -> str:
    for attempt in range(max_query_attempts):
        headers, body = _post_volcengine_json(config.query_url, {}, task_id, config)
        status_code = headers.get("X-Api-Status-Code")
        message = headers.get("X-Api-Message", "")
        logid = headers.get("X-Tt-Logid", "")
        if logid:
            print(f"Doubao Speech ASR query logid={logid}", file=sys.stderr)

        if status_code == DOUBAO_STATUS_SUCCESS:
            text = _extract_transcript_text(body)
            if not text:
                raise VideoNoteError(f"Doubao Speech ASR returned an empty transcript; logid={logid}")
            return text

        if status_code in DOUBAO_STATUS_PROCESSING:
            if attempt < max_query_attempts - 1:
                time.sleep(poll_interval_seconds)
                continue
            raise VideoNoteError("Doubao Speech ASR timed out waiting for transcript result.")

        raise VideoNoteError(
            f"Doubao Speech ASR query failed with status {status_code}: {message}; logid={logid}"
        )

    raise VideoNoteError("Doubao Speech ASR timed out waiting for transcript result.")


def submit_volcengine_asr_task(
    audio_url: str,
    task_id: str,
    config: DoubaoASRConfig,
) -> None:
    submit_doubao_asr_task(audio_url, task_id, config)


def query_volcengine_asr_result(
    task_id: str,
    config: DoubaoASRConfig,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    max_query_attempts: int = DEFAULT_MAX_QUERY_ATTEMPTS,
) -> str:
    return query_doubao_asr_result(
        task_id,
        config,
        poll_interval_seconds=poll_interval_seconds,
        max_query_attempts=max_query_attempts,
    )


def _extract_transcript_text(body: dict) -> str:
    result = body.get("result")
    if isinstance(result, dict):
        return str(result.get("text") or "").strip()
    if isinstance(result, list):
        return "\n".join(str(item.get("text") or "").strip() for item in result if item.get("text")).strip()
    return ""


def _volcengine_headers(
    task_id: str,
    config: DoubaoASRConfig,
    include_sequence: bool = False,
) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Api-Resource-Id": config.resource_id,
        "X-Api-Request-Id": task_id,
        "X-Api-App-Key": config.app_id,
        "X-Api-Access-Key": config.access_token,
    }
    if include_sequence:
        headers["X-Api-Sequence"] = "-1"
    return headers


def _post_volcengine_json(
    url: str,
    payload: dict,
    task_id: str,
    config: DoubaoASRConfig,
    include_sequence: bool = False,
) -> tuple[dict, dict]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=_volcengine_headers(task_id, config, include_sequence),
    )

    try:
        with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            headers = dict(response.headers.items())
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoNoteError(f"Doubao Speech ASR request failed with HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise VideoNoteError(f"Doubao Speech ASR is unavailable: {exc}") from exc

    if not raw_body:
        return headers, {}

    try:
        return headers, json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise VideoNoteError("Doubao Speech ASR returned invalid JSON.") from exc
