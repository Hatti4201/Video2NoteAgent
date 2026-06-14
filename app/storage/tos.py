import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.utils import VideoNoteError


DEFAULT_TOS_BUCKET = "nika-mnemo"
DEFAULT_TOS_REGION = "cn-beijing"
DEFAULT_TOS_ENDPOINT = "tos-cn-beijing.volces.com"
DEFAULT_PRESIGNED_EXPIRES_SECONDS = 3600


@dataclass(frozen=True)
class TosConfig:
    access_key_id: str
    secret_access_key: str
    bucket: str
    region: str
    endpoint: str
    presigned_expires_seconds: int = DEFAULT_PRESIGNED_EXPIRES_SECONDS


@dataclass(frozen=True)
class TosUpload:
    bucket: str
    key: str
    url: str


def get_tos_config() -> TosConfig:
    access_key_id = os.environ.get("VOLCENGINE_ACCESS_KEY_ID", "").strip()
    secret_access_key = os.environ.get("VOLCENGINE_SECRET_ACCESS_KEY", "").strip()
    if not access_key_id or not secret_access_key:
        raise VideoNoteError(
            "TOS upload requires VOLCENGINE_ACCESS_KEY_ID and VOLCENGINE_SECRET_ACCESS_KEY."
        )

    return TosConfig(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        bucket=os.environ.get("TOS_BUCKET", DEFAULT_TOS_BUCKET).strip() or DEFAULT_TOS_BUCKET,
        region=os.environ.get("TOS_REGION", DEFAULT_TOS_REGION).strip() or DEFAULT_TOS_REGION,
        endpoint=os.environ.get("TOS_ENDPOINT", DEFAULT_TOS_ENDPOINT).strip() or DEFAULT_TOS_ENDPOINT,
    )


def upload_audio_to_tos(file_path: str | Path, config: TosConfig | None = None) -> TosUpload:
    audio_path = Path(file_path).expanduser()
    if not audio_path.exists():
        raise VideoNoteError(f"Audio file does not exist: {audio_path}")
    if not audio_path.is_file():
        raise VideoNoteError(f"Audio path is not a file: {audio_path}")

    config = config or get_tos_config()
    key = build_audio_object_key(audio_path)
    client = create_tos_client(config)

    try:
        client.put_object_from_file(config.bucket, key, str(audio_path))
    except Exception as exc:
        raise VideoNoteError(f"TOS audio upload failed: {exc}") from exc

    try:
        url = create_presigned_get_url(client, config, key)
    except Exception as exc:
        raise VideoNoteError(f"TOS presigned URL generation failed: {exc}") from exc

    return TosUpload(bucket=config.bucket, key=key, url=url)


def delete_audio_from_tos(key: str, config: TosConfig | None = None) -> None:
    config = config or get_tos_config()
    client = create_tos_client(config)

    try:
        client.delete_object(config.bucket, key)
    except Exception as exc:
        raise VideoNoteError(f"TOS audio delete failed: {exc}") from exc


def build_audio_object_key(file_path: Path) -> str:
    suffix = file_path.suffix.lower().lstrip(".") or "audio"
    date_part = datetime.now(timezone.utc).date().isoformat()
    return f"audio/{date_part}/{uuid4()}.{suffix}"


def create_tos_client(config: TosConfig):
    try:
        import tos
    except ImportError as exc:
        raise VideoNoteError(
            "Volcengine TOS SDK is not installed. Install dependencies from requirements.txt."
        ) from exc

    return tos.TosClientV2(
        config.access_key_id,
        config.secret_access_key,
        config.endpoint,
        config.region,
    )


def create_presigned_get_url(client, config: TosConfig, key: str) -> str:
    try:
        import tos
    except ImportError as exc:
        raise VideoNoteError(
            "Volcengine TOS SDK is not installed. Install dependencies from requirements.txt."
        ) from exc

    result = client.pre_signed_url(
        tos.HttpMethodType.Http_Method_Get,
        config.bucket,
        key,
        expires=config.presigned_expires_seconds,
    )
    url = getattr(result, "signed_url", None) or getattr(result, "url", None) or str(result)
    if not url:
        raise VideoNoteError("TOS presigned URL generation returned an empty URL.")
    return url
