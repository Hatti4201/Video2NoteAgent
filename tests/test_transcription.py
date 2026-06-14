import json

import pytest

from app import transcription
from app.transcription import DoubaoASRConfig
from app.utils import VideoNoteError


class FakeResponse:
    def __init__(self, headers: dict, payload: dict | None = None):
        self.headers = headers
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        if self.payload is None:
            return b""
        return json.dumps(self.payload).encode("utf-8")


def make_config() -> DoubaoASRConfig:
    return DoubaoASRConfig(
        app_id="app-id",
        access_token="access-token",
        resource_id="volc.seedasr.auc",
        submit_url="https://asr.example/submit",
        query_url="https://asr.example/query",
        language="zh-CN",
        audio_format="mp3",
        enable_itn=True,
        enable_punc=True,
        enable_ddc=True,
        show_utterances=True,
    )


def test_get_doubao_asr_config_requires_app_id_and_access_token(monkeypatch):
    monkeypatch.delenv("DOUBAO_ASR_APP_ID", raising=False)
    monkeypatch.delenv("DOUBAO_ASR_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("VOLCENGINE_ACCESS_KEY_ID", "tos-ak")
    monkeypatch.setenv("VOLCENGINE_SECRET_ACCESS_KEY", "tos-sk")

    with pytest.raises(VideoNoteError, match="Doubao Speech ASR requires"):
        transcription.get_doubao_asr_config()


def test_get_doubao_asr_config_reads_doubao_env(monkeypatch):
    monkeypatch.setenv("DOUBAO_ASR_APP_ID", "2614672586")
    monkeypatch.setenv("DOUBAO_ASR_ACCESS_TOKEN", "access-token")
    monkeypatch.setenv("DOUBAO_ASR_RESOURCE_ID", "volc.seedasr.auc")

    config = transcription.get_doubao_asr_config()

    assert config.app_id == "2614672586"
    assert config.access_token == "access-token"
    assert config.resource_id == "volc.seedasr.auc"


def test_transcribe_audio_url_submits_and_queries_with_old_console_headers(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if request.full_url == "https://asr.example/submit":
            return FakeResponse(
                {
                    "X-Api-Status-Code": "20000000",
                    "X-Api-Message": "OK",
                    "X-Tt-Logid": "submit-logid",
                }
            )
        return FakeResponse(
            {
                "X-Api-Status-Code": "20000000",
                "X-Api-Message": "OK",
                "X-Tt-Logid": "query-logid",
            },
            {
                "result": {
                    "text": "这是识别结果。",
                }
            },
        )

    monkeypatch.setattr(transcription, "urlopen", fake_urlopen)
    monkeypatch.setattr(transcription, "uuid4", lambda: "task-id")

    transcript = transcription.transcribe_audio_url(
        "https://audio.example/sample.mp3",
        config=make_config(),
        poll_interval_seconds=0,
    )

    submit_request = requests[0][0]
    query_request = requests[1][0]
    submit_payload = json.loads(submit_request.data.decode("utf-8"))

    assert transcript == "这是识别结果。"
    assert submit_request.headers["X-api-app-key"] == "app-id"
    assert submit_request.headers["X-api-access-key"] == "access-token"
    assert submit_request.headers["X-api-resource-id"] == "volc.seedasr.auc"
    assert submit_request.headers["X-api-request-id"] == "task-id"
    assert submit_request.headers["X-api-sequence"] == "-1"
    assert "X-api-key" not in submit_request.headers
    assert query_request.headers["X-api-request-id"] == "task-id"
    assert query_request.headers["X-api-app-key"] == "app-id"
    assert query_request.headers["X-api-access-key"] == "access-token"
    assert "X-api-sequence" not in query_request.headers
    assert submit_payload["audio"] == {
        "format": "mp3",
        "url": "https://audio.example/sample.mp3",
        "language": "zh-CN",
    }
    assert submit_payload["request"]["model_name"] == "bigmodel"
    assert submit_payload["request"]["enable_itn"] is True
    assert submit_payload["request"]["enable_punc"] is True
    assert submit_payload["request"]["enable_ddc"] is True
    assert submit_payload["request"]["show_utterances"] is True


def test_transcribe_audio_url_polls_until_success(monkeypatch):
    responses = [
        FakeResponse({"X-Api-Status-Code": "20000000", "X-Api-Message": "OK"}),
        FakeResponse({"X-Api-Status-Code": "20000001", "X-Api-Message": "processing"}, {}),
        FakeResponse(
            {"X-Api-Status-Code": "20000000", "X-Api-Message": "OK"},
            {"result": {"text": "final transcript"}},
        ),
    ]
    sleeps = []

    monkeypatch.setattr(transcription, "urlopen", lambda request, timeout: responses.pop(0))
    monkeypatch.setattr(transcription.time, "sleep", lambda seconds: sleeps.append(seconds))

    transcript = transcription.transcribe_audio_url(
        "https://audio.example/sample.mp3",
        config=make_config(),
        poll_interval_seconds=3,
    )

    assert transcript == "final transcript"
    assert sleeps == [3]


def test_transcribe_audio_url_rejects_non_public_url():
    with pytest.raises(VideoNoteError, match="public http"):
        transcription.transcribe_audio_url("file:///tmp/sample.mp3", config=make_config())


def test_query_result_reports_failed_status(monkeypatch):
    monkeypatch.setattr(
        transcription,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {"X-Api-Status-Code": "45000001", "X-Api-Message": "invalid params"},
            {},
        ),
    )

    with pytest.raises(VideoNoteError, match="45000001"):
        transcription.query_volcengine_asr_result(
            "task-id",
            make_config(),
            poll_interval_seconds=0,
            max_query_attempts=1,
        )


def test_submit_failure_reports_status_message_and_logid(monkeypatch):
    monkeypatch.setattr(
        transcription,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "X-Api-Status-Code": "45000001",
                "X-Api-Message": "invalid params",
                "X-Tt-Logid": "submit-logid",
            }
        ),
    )

    with pytest.raises(VideoNoteError, match="45000001.*invalid params.*submit-logid"):
        transcription.submit_volcengine_asr_task(
            "https://audio.example/sample.mp3",
            "task-id",
            make_config(),
        )


def test_query_failure_reports_status_message_and_logid(monkeypatch):
    monkeypatch.setattr(
        transcription,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "X-Api-Status-Code": "55000031",
                "X-Api-Message": "busy",
                "X-Tt-Logid": "query-logid",
            },
            {},
        ),
    )

    with pytest.raises(VideoNoteError, match="55000031.*busy.*query-logid"):
        transcription.query_volcengine_asr_result(
            "task-id",
            make_config(),
            poll_interval_seconds=0,
            max_query_attempts=1,
        )


def test_transcribe_audio_file_via_tos_deletes_object_without_breaking_result(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake audio")
    calls = []

    monkeypatch.setattr(
        transcription,
        "upload_audio_to_tos",
        lambda path, config=None: type(
            "Upload",
            (),
            {
                "bucket": "nika-mnemo",
                "key": "audio/2026-06-11/sample.mp3",
                "url": "https://signed.example/sample.mp3",
            },
        )(),
    )
    monkeypatch.setattr(
        transcription,
        "transcribe_audio_url",
        lambda url, config=None, poll_interval_seconds=5, max_query_attempts=120: calls.append(url)
        or "transcript text",
    )

    def fake_delete(key, config=None):
        calls.append(key)
        raise VideoNoteError("TOS audio delete failed")

    monkeypatch.setattr(transcription, "delete_audio_from_tos", fake_delete)

    transcript = transcription.transcribe_audio_file_via_tos(
        audio_path,
        config=make_config(),
        poll_interval_seconds=0,
    )

    assert transcript == "transcript text"
    assert calls == [
        "https://signed.example/sample.mp3",
        "audio/2026-06-11/sample.mp3",
    ]
