import json
import os
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.downloader import validate_youtube_url
from app.utils import VideoNoteError


TELEGRAM_API_BASE_URL = "https://api.telegram.org"
TELEGRAM_TIMEOUT = 30
POLL_INTERVAL_SECONDS = 2


class TelegramError(Exception):
    """Readable Telegram adapter error."""


@dataclass(frozen=True)
class TelegramJob:
    chat_id: int
    user_id: int
    url: str


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    print(f"[{timestamp}] telegram: {message}", flush=True)


def format_process_result_message(result) -> str:
    output_dir = Path(getattr(result, "output_dir", result))
    publish_results = list(getattr(result, "publish_results", []))
    lines = [
        "Done.",
        "",
        f"Local output: {output_dir}",
    ]

    if publish_results:
        lines.extend(["", "Published destinations:"])
        for publish_result in publish_results:
            if publish_result.success:
                destination = publish_result.url or publish_result.message
                lines.append(f"- {publish_result.adapter_name}: {destination}")
            else:
                lines.append(f"- {publish_result.adapter_name}: failed - {publish_result.message}")

    return "\n".join(lines)


def get_telegram_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot.")
    return token


def get_allowed_user_ids() -> set[int]:
    raw_value = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not raw_value:
        raise TelegramError("TELEGRAM_ALLOWED_USER_IDS is required to run the Telegram bot.")

    try:
        return {
            int(value.strip())
            for value in raw_value.split(",")
            if value.strip()
        }
    except ValueError as exc:
        raise TelegramError("TELEGRAM_ALLOWED_USER_IDS must be a comma-separated list of integers.") from exc


class TelegramBot:
    def __init__(
        self,
        token: str,
        allowed_user_ids: set[int],
        process_url,
        api_base_url: str = TELEGRAM_API_BASE_URL,
    ):
        self.token = token
        self.allowed_user_ids = allowed_user_ids
        self.process_url = process_url
        self.api_base_url = api_base_url.rstrip("/")
        self.jobs: Queue[TelegramJob] = Queue()
        self.current_job: TelegramJob | None = None
        self.worker_thread: threading.Thread | None = None

    @classmethod
    def from_env(cls, process_url):
        return cls(
            token=get_telegram_bot_token(),
            allowed_user_ids=get_allowed_user_ids(),
            process_url=process_url,
        )

    def poll_forever(self) -> None:
        offset = None
        self.start_worker()
        log(
            "polling started "
            f"allowed_users={len(self.allowed_user_ids)} "
            f"api_base_url={self.api_base_url}"
        )

        while True:
            try:
                log(f"polling getUpdates offset={offset}")
                updates = self.get_updates(offset)
                log(f"received updates count={len(updates)}")
            except TelegramError as exc:
                log(f"polling error: {exc}")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            for update in updates:
                update_id = update.get("update_id")
                log(f"handling update_id={update_id}")
                if isinstance(update_id, int):
                    offset = update_id + 1

                try:
                    self.handle_update(update)
                except TelegramError as exc:
                    log(f"update_id={update_id} telegram error: {exc}")
                except Exception as exc:
                    log(f"update_id={update_id} unexpected error: {type(exc).__name__}: {exc}")
            time.sleep(POLL_INTERVAL_SECONDS)

    def start_worker(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="telegram-video-worker",
            daemon=True,
        )
        self.worker_thread.start()
        log("worker started")

    def _worker_loop(self) -> None:
        while True:
            self.process_next_job(block=True)

    def process_next_job(self, block: bool = False) -> bool:
        try:
            job = self.jobs.get(block=block)
        except Empty:
            return False

        self.current_job = job
        log(f"worker picked job user_id={job.user_id} queue_remaining={self.jobs.qsize()}")

        try:
            self.process_job(job)
        finally:
            self.current_job = None
            self.jobs.task_done()

        return True

    def process_job(self, job: TelegramJob) -> None:
        self._safe_send_message(job.chat_id, f"Started processing:\n{job.url}")

        try:
            log("starting video processing")
            result = self.process_url(job.url)
            output_dir = Path(getattr(result, "output_dir", result))
            log(f"video processing completed output_dir={output_dir}")
        except VideoNoteError as exc:
            log(f"video processing error: {exc}")
            self._safe_send_message(job.chat_id, f"Failed:\n{exc}")
            return
        except Exception as exc:
            log(f"unexpected processing error: {type(exc).__name__}: {exc}")
            self._safe_send_message(job.chat_id, f"Unexpected error:\n{exc}")
            return

        self._safe_send_message(job.chat_id, format_process_result_message(result))
        log("done message sent")

    def _safe_send_message(self, chat_id: int, text: str) -> None:
        try:
            self.send_message(chat_id, text)
        except TelegramError as exc:
            log(f"send_message failed chat_id={chat_id}: {exc}")

    def get_updates(self, offset: int | None = None) -> list[dict]:
        params = {"timeout": TELEGRAM_TIMEOUT}
        if offset is not None:
            params["offset"] = offset

        result = self._request("getUpdates", params=params)
        updates = result.get("result")
        if not isinstance(updates, list):
            raise TelegramError("Telegram getUpdates returned an invalid response.")
        return updates

    def send_message(self, chat_id: int, text: str) -> dict:
        return self._request(
            "sendMessage",
            payload={
                "chat_id": chat_id,
                "text": text[:4000],
            },
        )

    def handle_update(self, update: dict) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        user = message.get("from") or {}
        chat_id = chat.get("id")
        user_id = user.get("id")
        text = str(message.get("text") or "").strip()

        if not chat_id or not user_id:
            log("ignored update without chat_id or user_id")
            return

        log(
            "message received "
            f"chat_id={chat_id} user_id={user_id} "
            f"text_length={len(text)}"
        )

        if int(user_id) not in self.allowed_user_ids:
            log(f"unauthorized user_id={user_id}")
            self.send_message(int(chat_id), "Unauthorized user.")
            return

        if not validate_youtube_url(text):
            log(f"invalid url from user_id={user_id}")
            self.send_message(int(chat_id), "Send a valid YouTube URL.")
            return

        log(f"accepted YouTube URL from user_id={user_id}")
        position = self.jobs.qsize() + (1 if self.current_job else 0) + 1
        self.jobs.put(TelegramJob(chat_id=int(chat_id), user_id=int(user_id), url=text))
        log(f"queued job user_id={user_id} position={position} queue_size={self.jobs.qsize()}")
        self.send_message(int(chat_id), f"Added to queue.\nPosition: {position}")

    def _request(self, method: str, params: dict | None = None, payload: dict | None = None) -> dict:
        url = f"{self.api_base_url}/bot{self.token}/{method}"
        if params:
            url = f"{url}?{urlencode(params)}"

        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, method="POST" if payload is not None else "GET", headers=headers)
        log(f"request method={method} http_method={request.get_method()} has_payload={payload is not None}")

        try:
            with urlopen(request, timeout=TELEGRAM_TIMEOUT + 5) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TelegramError(f"Telegram API failed with HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise TelegramError(f"Telegram API is unavailable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise TelegramError("Telegram API returned invalid JSON.") from exc

        if not result.get("ok"):
            raise TelegramError(f"Telegram API returned an error: {result}")

        log(f"request method={method} ok")
        return result
