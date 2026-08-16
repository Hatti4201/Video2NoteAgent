from pathlib import Path
import subprocess

import pytest

from app.transcription import LocalWhisperAPIConfig
from scripts import transcribe_local_videos_doubao as helper
from app.utils import VideoNoteError


def test_find_video_files_returns_supported_files_sorted(tmp_path):
    (tmp_path / "b.mp4").write_bytes(b"video")
    (tmp_path / "a.MOV").write_bytes(b"video")
    (tmp_path / "ignore.txt").write_text("no", encoding="utf-8")

    assert [path.name for path in helper.find_video_files(tmp_path)] == ["a.MOV", "b.mp4"]


def test_find_video_files_supports_recursive_scan(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "lesson.mkv").write_bytes(b"video")

    assert helper.find_video_files(tmp_path) == []
    assert [path.name for path in helper.find_video_files(tmp_path, recursive=True)] == ["lesson.mkv"]


def test_extract_audio_to_mp3_uses_ffmpeg_audio_settings(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, check, stdout, stderr, text):
        calls.append((command, check, stdout, stderr, text))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    video_path = tmp_path / "lesson.mp4"
    audio_path = helper.extract_audio_for_asr(video_path, tmp_path)

    command, check, stdout, stderr, text = calls[0]
    assert command == [
        "ffmpeg",
        "-y",
        "-err_detect",
        "ignore_err",
        "-fflags",
        "+discardcorrupt",
        "-i",
        str(video_path),
        "-vn",
        "-c:a",
        "copy",
        str(tmp_path / "audio.aac"),
    ]
    assert check is True
    assert stdout == subprocess.DEVNULL
    assert stderr == subprocess.PIPE
    assert text is True
    assert audio_path == tmp_path / "audio.aac"


def test_extract_audio_to_mp3_reports_ffmpeg_failure(monkeypatch, tmp_path):
    commands = []

    def fake_run(command, check, stdout, stderr, text):
        commands.append(command)
        if command[-1].endswith(".aac"):
            raise subprocess.CalledProcessError(1, command, stderr="aac copy failed")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    audio_path = helper.extract_audio_for_asr(tmp_path / "lesson.mp4", tmp_path)

    assert audio_path == tmp_path / "audio.mp3"
    assert len(commands) == 2


def test_write_raw_transcript_markdown(tmp_path):
    output_path = tmp_path / "lesson.md"
    video_path = tmp_path / "Lesson 01.mp4"

    helper.write_raw_transcript_markdown(output_path, video_path, "hello\nworld")

    assert output_path.read_text(encoding="utf-8") == (
        "# Lesson 01\n\n"
        f"Source: `{video_path}`\n\n"
        "## Raw Transcript\n\n"
        "hello\nworld\n"
    )


def test_unique_markdown_path_avoids_overwrite(tmp_path):
    video_path = tmp_path / "lesson.mp4"
    (tmp_path / "lesson.md").write_text("old", encoding="utf-8")

    assert helper.unique_markdown_path(tmp_path, video_path) == tmp_path / "lesson-2.md"
    assert helper.unique_markdown_path(tmp_path, video_path, overwrite=True) == tmp_path / "lesson.md"


def test_should_skip_existing_checks_expected_output_name(tmp_path):
    video_path = tmp_path / "lesson.mp4"
    (tmp_path / "lesson.md").write_text("done", encoding="utf-8")

    assert helper.should_skip_existing(tmp_path, video_path, overwrite=False)
    assert not helper.should_skip_existing(tmp_path, video_path, overwrite=True)


def test_transcribe_video_to_markdown_uses_existing_doubao_helper(monkeypatch, tmp_path):
    calls = []

    def fake_extract(video_path, temp_dir):
        calls.append(("extract", video_path, temp_dir.name))
        audio_path = temp_dir / "audio.aac"
        audio_path.write_bytes(b"audio")
        return audio_path

    def fake_transcribe(audio_path, config=None):
        calls.append(("transcribe", audio_path.name, config.audio_format if config else None))
        return "raw transcript"

    monkeypatch.setattr(helper, "extract_audio_for_asr", fake_extract)
    monkeypatch.setattr(helper, "transcribe_audio_file_via_tos", fake_transcribe)
    monkeypatch.setattr(
        helper,
        "get_doubao_asr_config",
        lambda: helper.DoubaoASRConfig(
            app_id="app",
            access_token="token",
            resource_id="res",
            submit_url="submit",
            query_url="query",
            language="zh-CN",
            audio_format="mp3",
            enable_itn=True,
            enable_punc=True,
            enable_ddc=True,
            show_utterances=True,
        ),
    )

    video_path = tmp_path / "lesson.mp4"
    video_path.write_bytes(b"video")
    output_path = helper.transcribe_video_to_markdown(video_path, tmp_path)

    assert output_path == tmp_path / "lesson.md"
    assert "raw transcript" in output_path.read_text(encoding="utf-8")
    assert calls[0][0] == "extract"
    assert calls[0][1] == video_path
    assert calls[0][2].startswith("video-note-agent-doubao-")
    assert calls[1] == ("transcribe", "audio.aac", "aac")


def test_transcribe_video_to_markdown_uses_mp3_for_local_whisper_api(monkeypatch, tmp_path):
    calls = []

    def fake_extract_mp3(video_path, temp_dir):
        calls.append(("extract_mp3", video_path, temp_dir.name))
        audio_path = temp_dir / "audio.mp3"
        audio_path.write_bytes(b"audio")
        return audio_path

    def fake_transcribe(audio_path, config=None):
        calls.append(("transcribe", audio_path.name, config.model if config else None))
        return "local whisper transcript"

    monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "local_whisper_api")
    monkeypatch.setattr(helper, "extract_audio_for_local_whisper_api", fake_extract_mp3)
    monkeypatch.setattr(helper, "transcribe_audio_file_via_local_whisper_api", fake_transcribe)
    monkeypatch.setattr(
        helper,
        "get_local_whisper_api_config",
        lambda: LocalWhisperAPIConfig(
            base_url="http://127.0.0.1:8001",
            transcribe_path="/transcribe/path",
            model="whisper",
            language="en",
            temperature="0",
            timeout_seconds=600,
            api_key=None,
        ),
    )

    video_path = tmp_path / "lesson.mp4"
    video_path.write_bytes(b"video")
    output_path = helper.transcribe_video_to_markdown(video_path, tmp_path)

    assert output_path == tmp_path / "lesson.md"
    assert calls[0][0] == "extract_mp3"
    assert calls[1] == ("transcribe", "audio.mp3", "whisper")


def test_run_batch_uses_worker_pool_and_skips_existing(monkeypatch, tmp_path):
    video_a = tmp_path / "a.mp4"
    video_b = tmp_path / "b.mp4"
    video_a.write_bytes(b"video")
    video_b.write_bytes(b"video")
    (tmp_path / "a.md").write_text("done", encoding="utf-8")

    called = []

    def fake_find_video_files(input_path, recursive=False):
        return [video_a, video_b]

    def fake_process_one_video(video_path, output_dir, overwrite=False):
        called.append(video_path.name)
        return output_dir / f"{video_path.stem}.md"

    monkeypatch.setattr(helper, "find_video_files", fake_find_video_files)
    monkeypatch.setattr(helper, "process_one_video", fake_process_one_video)

    result = helper.run_batch(tmp_path, output_dir=tmp_path, workers=2)

    assert result == 0
    assert called == ["b.mp4"]
