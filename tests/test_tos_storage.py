from pathlib import Path
from types import SimpleNamespace

import pytest

from app.storage import tos
from app.storage.tos import TosConfig
from app.utils import VideoNoteError


class FakeClient:
    def __init__(self):
        self.uploads = []
        self.deletes = []

    def put_object_from_file(self, bucket, key, file_path):
        self.uploads.append((bucket, key, file_path))

    def pre_signed_url(self, method, bucket, key, expires):
        return SimpleNamespace(signed_url=f"https://signed.example/{bucket}/{key}?expires={expires}")

    def delete_object(self, bucket, key):
        self.deletes.append((bucket, key))


def make_config() -> TosConfig:
    return TosConfig(
        access_key_id="ak",
        secret_access_key="sk",
        bucket="nika-mnemo",
        region="cn-beijing",
        endpoint="tos-cn-beijing.volces.com",
    )


def test_get_tos_config_requires_credentials(monkeypatch):
    monkeypatch.delenv("VOLCENGINE_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("VOLCENGINE_SECRET_ACCESS_KEY", raising=False)

    with pytest.raises(VideoNoteError, match="TOS upload requires"):
        tos.get_tos_config()


def test_upload_audio_to_tos_uses_audio_key_and_presigned_url(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake audio")
    fake_client = FakeClient()

    monkeypatch.setattr(tos, "create_tos_client", lambda config: fake_client)
    monkeypatch.setattr(
        tos,
        "create_presigned_get_url",
        lambda client, config, key: (
            f"https://signed.example/{config.bucket}/{key}"
            f"?expires={config.presigned_expires_seconds}"
        ),
    )
    monkeypatch.setattr(tos, "uuid4", lambda: "audio-uuid")

    result = tos.upload_audio_to_tos(audio_path, make_config())

    assert result.bucket == "nika-mnemo"
    assert result.key.startswith("audio/")
    assert result.key.endswith("/audio-uuid.mp3")
    assert result.url.startswith("https://signed.example/nika-mnemo/audio/")
    assert fake_client.uploads == [("nika-mnemo", result.key, str(audio_path))]


def test_upload_audio_to_tos_reports_missing_file(tmp_path):
    with pytest.raises(VideoNoteError, match="does not exist"):
        tos.upload_audio_to_tos(tmp_path / "missing.mp3", make_config())


def test_delete_audio_from_tos_deletes_key(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(tos, "create_tos_client", lambda config: fake_client)

    tos.delete_audio_from_tos("audio/2026-06-11/sample.mp3", make_config())

    assert fake_client.deletes == [("nika-mnemo", "audio/2026-06-11/sample.mp3")]
