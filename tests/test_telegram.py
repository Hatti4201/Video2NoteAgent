from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.base import PublishResult
from app.input_adapters.telegram import (
    TelegramBot,
    TelegramError,
    format_process_result_message,
    get_allowed_user_ids,
    get_telegram_bot_token,
)
from app.utils import VideoNoteError


def make_update(user_id=123, chat_id=456, text="https://www.youtube.com/watch?v=example"):
    return {
        "update_id": 1,
        "message": {
            "from": {"id": user_id},
            "chat": {"id": chat_id},
            "text": text,
        },
    }


def test_get_telegram_bot_token_requires_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(TelegramError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_bot_token()


def test_get_allowed_user_ids_parses_comma_separated_ids(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")

    assert get_allowed_user_ids() == {123, 456}


def test_get_allowed_user_ids_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "abc")

    with pytest.raises(TelegramError, match="comma-separated list of integers"):
        get_allowed_user_ids()


def test_handle_update_rejects_unauthorized_user():
    sent_messages = []
    bot = TelegramBot("token", {123}, lambda url: Path("output"))
    bot.send_message = lambda chat_id, text: sent_messages.append((chat_id, text))

    bot.handle_update(make_update(user_id=999))

    assert sent_messages == [(456, "Unauthorized user.")]


def test_handle_update_rejects_invalid_url():
    sent_messages = []
    bot = TelegramBot("token", {123}, lambda url: Path("output"))
    bot.send_message = lambda chat_id, text: sent_messages.append((chat_id, text))

    bot.handle_update(make_update(text="hello"))

    assert sent_messages == [(456, "Send a valid YouTube URL.")]


def test_handle_update_processes_youtube_url():
    sent_messages = []
    processed_urls = []

    def fake_process_url(url):
        processed_urls.append(url)
        return Path("output/sample")

    bot = TelegramBot("token", {123}, fake_process_url)
    bot.send_message = lambda chat_id, text: sent_messages.append((chat_id, text))

    bot.handle_update(make_update())
    bot.process_next_job()

    assert processed_urls == ["https://www.youtube.com/watch?v=example"]
    assert sent_messages == [
        (456, "Added to queue.\nPosition: 1"),
        (456, "Started processing:\nhttps://www.youtube.com/watch?v=example"),
        (456, "Done.\n\nLocal output: output/sample"),
    ]


def test_handle_update_sends_publish_links():
    sent_messages = []
    processed_urls = []

    def fake_process_url(url):
        processed_urls.append(url)
        return SimpleNamespace(
            output_dir=Path("output/sample"),
            publish_results=[
                PublishResult("local_markdown", True, "Local assets", None),
                PublishResult("notion", True, "Published", "https://notion.example/page"),
                PublishResult("feishu", True, "Published", "https://feishu.example/doc"),
                PublishResult("obsidian", True, "Published", "/vault/Video Notes/sample.md"),
            ],
        )

    bot = TelegramBot("token", {123}, fake_process_url)
    bot.send_message = lambda chat_id, text: sent_messages.append((chat_id, text))

    bot.handle_update(make_update())
    bot.process_next_job()

    assert processed_urls == ["https://www.youtube.com/watch?v=example"]
    assert sent_messages[0] == (456, "Added to queue.\nPosition: 1")
    assert sent_messages[1] == (
        456,
        "Started processing:\nhttps://www.youtube.com/watch?v=example",
    )
    assert "Local output: output/sample" in sent_messages[2][1]
    assert "- notion: https://notion.example/page" in sent_messages[2][1]
    assert "- feishu: https://feishu.example/doc" in sent_messages[2][1]
    assert "- obsidian: /vault/Video Notes/sample.md" in sent_messages[2][1]


def test_format_process_result_message_includes_adapter_failures():
    message = format_process_result_message(
        SimpleNamespace(
            output_dir=Path("output/sample"),
            publish_results=[
                PublishResult("notion", False, "Notion is unavailable.", None),
            ],
        )
    )

    assert "Local output: output/sample" in message
    assert "- notion: failed - Notion is unavailable." in message


def test_handle_update_reports_processing_error():
    sent_messages = []

    def fake_process_url(url):
        raise VideoNoteError("No subtitles found.")

    bot = TelegramBot("token", {123}, fake_process_url)
    bot.send_message = lambda chat_id, text: sent_messages.append((chat_id, text))

    bot.handle_update(make_update())
    bot.process_next_job()

    assert sent_messages == [
        (456, "Added to queue.\nPosition: 1"),
        (456, "Started processing:\nhttps://www.youtube.com/watch?v=example"),
        (456, "Failed:\nNo subtitles found."),
    ]


def test_handle_update_queues_multiple_urls_fifo():
    sent_messages = []
    processed_urls = []

    def fake_process_url(url):
        processed_urls.append(url)
        return Path(f"output/{len(processed_urls)}")

    bot = TelegramBot("token", {123}, fake_process_url)
    bot.send_message = lambda chat_id, text: sent_messages.append((chat_id, text))

    bot.handle_update(make_update(text="https://www.youtube.com/watch?v=first"))
    bot.handle_update(make_update(text="https://www.youtube.com/watch?v=second"))

    assert sent_messages == [
        (456, "Added to queue.\nPosition: 1"),
        (456, "Added to queue.\nPosition: 2"),
    ]

    bot.process_next_job()
    bot.process_next_job()

    assert processed_urls == [
        "https://www.youtube.com/watch?v=first",
        "https://www.youtube.com/watch?v=second",
    ]
    assert "Local output: output/1" in sent_messages[3][1]
    assert "Local output: output/2" in sent_messages[5][1]


def test_poll_forever_continues_after_polling_error(monkeypatch):
    sleeps = []
    calls = []
    bot = TelegramBot("token", {123}, lambda url: Path("output"))

    def fake_get_updates(offset):
        calls.append(offset)
        if len(calls) == 1:
            raise TelegramError("temporary failure")
        raise KeyboardInterrupt

    monkeypatch.setattr(bot, "get_updates", fake_get_updates)
    monkeypatch.setattr("app.input_adapters.telegram.time.sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(KeyboardInterrupt):
        bot.poll_forever()

    assert len(calls) == 2
    assert sleeps == [2]
