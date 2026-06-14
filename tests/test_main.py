import json

import main
from app.adapters.base import PublishResult
from app import utils
from app.downloader import NoSubtitleError
from app.utils import VideoNoteError


SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
First transcript line.

00:00:02.000 --> 00:00:04.000
You should keep this action item.
"""


def test_run_writes_dedicated_output_folder(monkeypatch, tmp_path):
    def fake_download_subtitle(url, output_path=None):
        output_path.write_text(SAMPLE_VTT, encoding="utf-8")
        return {
            "title": "Sample Video",
            "url": url,
            "source": "youtube",
            "upload_date": "20260102",
            "author": "Sample Channel",
            "duration": 321,
            "language": "en",
            "tags": ["sample", "video"],
            "processing_method": "youtube_subtitle",
            "subtitle_path": output_path,
            "is_automatic": False,
        }

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "download_subtitle", fake_download_subtitle)
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(
        main,
        "generate_llm_documents",
        lambda title, transcript: ("LLM cleaned content", "LLM notes outline"),
    )

    main.run("https://www.youtube.com/watch?v=example")

    output_dir = tmp_path / "2026-01-02-sample-video"
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "01_raw_transcript.txt",
        "02_formatted_transcript.md",
        "03_cleaned_content.md",
        "04_notes_outline.md",
        "metadata.json",
    ]

    assert (output_dir / "01_raw_transcript.txt").read_text(encoding="utf-8") == (
        "First transcript line.\nYou should keep this action item.\n"
    )
    assert (output_dir / "03_cleaned_content.md").read_text(encoding="utf-8") == (
        "LLM cleaned content\n"
    )
    assert (output_dir / "04_notes_outline.md").read_text(encoding="utf-8") == (
        "LLM notes outline\n"
    )

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["title"] == "Sample Video"
    assert metadata["url"] == "https://www.youtube.com/watch?v=example"
    assert metadata["source"] == "youtube"
    assert metadata["author"] == "Sample Channel"
    assert metadata["duration"] == "321"
    assert metadata["language"] == "en"
    assert metadata["tags"] == ["sample", "video"]
    assert metadata["status"] == "Processed"
    assert metadata["created_at"] == "2026-01-03T04:05:06+00:00"
    assert metadata["summary"] == ""
    assert metadata["processing_method"] == "youtube_subtitle"


def test_youtube_without_subtitles_falls_back_to_doubao_asr(monkeypatch, tmp_path):
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake audio")
    calls = []

    def fake_download_subtitle(url, output_path=None):
        calls.append(("subtitle", url))
        raise NoSubtitleError("No English or Chinese subtitles were found for this video.")

    def fake_download_youtube_audio(url, output_dir):
        calls.append(("audio", url))
        return {
            "title": "No Subtitle Video",
            "url": url,
            "source": "youtube_asr",
            "upload_date": "20260102",
            "author": "ASR Channel",
            "duration": 456,
            "language": "",
            "tags": ["asr"],
            "processing_method": "doubao_asr",
            "audio_path": audio_path,
        }

    def fake_transcribe_audio_file_via_tos(path):
        calls.append(("asr", path))
        return "ASR transcript text."

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(main, "download_subtitle", fake_download_subtitle)
    monkeypatch.setattr(main, "download_youtube_audio", fake_download_youtube_audio)
    monkeypatch.setattr(main, "transcribe_audio_file_via_tos", fake_transcribe_audio_file_via_tos)
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(
        main,
        "generate_llm_documents",
        lambda title, transcript: ("Cleaned ASR content", "ASR notes outline"),
    )
    monkeypatch.setattr(main, "publish_output", lambda output_dir: [])

    result = main.process_youtube_url("https://www.youtube.com/watch?v=no-subtitles")

    assert calls == [
        ("subtitle", "https://www.youtube.com/watch?v=no-subtitles"),
        ("audio", "https://www.youtube.com/watch?v=no-subtitles"),
        ("asr", audio_path),
    ]
    assert result.output_dir == tmp_path / "output" / "2026-01-02-no-subtitle-video"
    assert (result.output_dir / "01_raw_transcript.txt").read_text(encoding="utf-8") == (
        "ASR transcript text.\n"
    )

    metadata = json.loads((result.output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["source"] == "youtube_asr"
    assert metadata["author"] == "ASR Channel"
    assert metadata["duration"] == "456"
    assert metadata["language"] == ""
    assert metadata["tags"] == ["asr"]
    assert metadata["processing_method"] == "doubao_asr"


def test_write_output_files_avoids_overwriting_existing_video_workspace(monkeypatch, tmp_path):
    video_info = {
        "title": "Sample Video",
        "url": "https://www.youtube.com/watch?v=example",
        "source": "youtube",
        "upload_date": "20260102",
    }

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(
        main,
        "generate_llm_documents",
        lambda title, transcript: (_ for _ in ()).throw(VideoNoteError("LLM unavailable.")),
    )
    monkeypatch.setattr(main, "publish_output", lambda output_dir: [])

    first = main.write_output_files(video_info, "First transcript.")
    second = main.write_output_files(video_info, "Second transcript.")

    assert first.output_dir == tmp_path / "2026-01-02-sample-video"
    assert second.output_dir == tmp_path / "2026-01-02-sample-video-2"
    assert (first.output_dir / "01_raw_transcript.txt").read_text(encoding="utf-8") == (
        "First transcript.\n"
    )
    assert (second.output_dir / "01_raw_transcript.txt").read_text(encoding="utf-8") == (
        "Second transcript.\n"
    )


def test_write_output_files_preserves_workspace_when_adapter_fails(monkeypatch, tmp_path):
    video_info = {
        "title": "Adapter Failure Video",
        "url": "https://www.youtube.com/watch?v=example",
        "source": "youtube",
        "upload_date": "20260102",
    }

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(
        main,
        "generate_llm_documents",
        lambda title, transcript: ("Cleaned content", "Notes outline"),
    )
    monkeypatch.setattr(
        main,
        "publish_output",
        lambda output_dir: [PublishResult("notion", False, "Notion unavailable.", None)],
    )

    result = main.write_output_files(video_info, "Transcript text.")

    assert result.output_dir == tmp_path / "2026-01-02-adapter-failure-video"
    assert result.publish_results == [
        PublishResult("notion", False, "Notion unavailable.", None)
    ]
    assert sorted(path.name for path in result.output_dir.iterdir()) == [
        "01_raw_transcript.txt",
        "02_formatted_transcript.md",
        "03_cleaned_content.md",
        "04_notes_outline.md",
        "metadata.json",
    ]


def test_write_output_files_derives_three_ai_artifacts_from_transcript(monkeypatch, tmp_path):
    video_info = {
        "title": "AI Processing Video",
        "url": "https://www.youtube.com/watch?v=example",
        "source": "youtube",
        "upload_date": "20260102",
    }
    transcript = "Line one.\nLine two.\nLine three.\nLine four."
    llm_calls = []

    def fake_generate_llm_documents(title, transcript_text):
        llm_calls.append((title, transcript_text))
        return (
            "# Edited Transcript\n\nEdited transcript text.",
            "# Executive Summary\n\nSummary.\n\n# Key Takeaways\n\n- Point\n\n# Structured Outline\n\n1. Topic",
        )

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(main, "generate_llm_documents", fake_generate_llm_documents)
    monkeypatch.setattr(main, "publish_output", lambda output_dir: [])

    result = main.write_output_files(video_info, transcript)

    assert llm_calls == [("AI Processing Video", transcript)]
    assert "Line one. Line two. Line three." in (
        result.output_dir / "02_formatted_transcript.md"
    ).read_text(encoding="utf-8")
    assert (result.output_dir / "03_cleaned_content.md").read_text(encoding="utf-8") == (
        "# Edited Transcript\n\nEdited transcript text.\n"
    )
    assert "# Executive Summary" in (
        result.output_dir / "04_notes_outline.md"
    ).read_text(encoding="utf-8")


def test_write_output_files_keeps_local_artifacts_when_ai_processing_fails(monkeypatch, tmp_path):
    video_info = {
        "title": "Fallback Video",
        "url": "https://www.youtube.com/watch?v=example",
        "source": "youtube",
        "upload_date": "20260102",
    }

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(
        main,
        "generate_llm_documents",
        lambda title, transcript: (_ for _ in ()).throw(VideoNoteError("Qwen timeout.")),
    )
    monkeypatch.setattr(main, "publish_output", lambda output_dir: [])

    result = main.write_output_files(
        video_info,
        "This transcript explains the topic. You should review the notes.",
    )

    assert (result.output_dir / "01_raw_transcript.txt").exists()
    assert (result.output_dir / "02_formatted_transcript.md").exists()
    assert "# Edited Transcript" in (
        result.output_dir / "03_cleaned_content.md"
    ).read_text(encoding="utf-8")
    assert "# Executive Summary" in (
        result.output_dir / "04_notes_outline.md"
    ).read_text(encoding="utf-8")
    assert (result.output_dir / "metadata.json").exists()


def test_run_writes_local_video_output_with_mocked_transcription(monkeypatch, tmp_path):
    video_path = tmp_path / "Local Lesson.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(main, "current_timestamp", lambda: "2026-01-03T04:05:06+00:00")
    monkeypatch.setattr(
        main,
        "generate_llm_documents",
        lambda title, transcript: (_ for _ in ()).throw(VideoNoteError("Ollama unavailable.")),
    )
    monkeypatch.setattr(
        main,
        "transcribe_local_video",
        lambda path: "First transcribed line.\nYou should review this local video.",
    )

    main.run(str(video_path))

    output_root = tmp_path / "output"
    output_dir = next(output_root.iterdir())
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "01_raw_transcript.txt",
        "02_formatted_transcript.md",
        "03_cleaned_content.md",
        "04_notes_outline.md",
        "metadata.json",
    ]

    assert (output_dir / "01_raw_transcript.txt").read_text(encoding="utf-8") == (
        "First transcribed line.\nYou should review this local video.\n"
    )
    assert "# Edited Transcript" in (
        output_dir / "03_cleaned_content.md"
    ).read_text(encoding="utf-8")
    assert "# Action Items" in (output_dir / "04_notes_outline.md").read_text(encoding="utf-8")

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["title"] == "Local Lesson"
    assert metadata["url"] == str(video_path)
    assert metadata["source"] == "local_video"
    assert metadata["author"] == ""
    assert metadata["duration"] == ""
    assert metadata["language"] == ""
    assert metadata["tags"] == []
    assert metadata["status"] == "Processed"
    assert metadata["processing_method"] == "local_whisper"
