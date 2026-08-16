from pathlib import Path
import subprocess

from scripts import extract_local_video_audio as helper


def test_extract_audio_to_mp3_uses_expected_ffmpeg_settings(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, check, stdout, stderr, text):
        calls.append((command, check, stdout, stderr, text))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    video_path = tmp_path / "lesson.mp4"
    output_path = helper.extract_audio_to_mp3(video_path, tmp_path)

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
        "-af",
        "pan=mono|c0=c0",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(tmp_path / "lesson.mp3"),
    ]
    assert check is True
    assert stdout == subprocess.DEVNULL
    assert stderr == subprocess.PIPE
    assert text is True
    assert output_path == tmp_path / "lesson.mp3"


def test_run_batch_skips_existing_audio_files(monkeypatch, tmp_path):
    video_a = tmp_path / "a.mp4"
    video_b = tmp_path / "b.mp4"
    video_a.write_bytes(b"video")
    video_b.write_bytes(b"video")
    (tmp_path / "a.mp3").write_text("done", encoding="utf-8")

    called = []

    def fake_find_video_files(input_path, recursive=False):
        return [video_a, video_b]

    def fake_process_one_video(video_path, output_dir, overwrite=False):
        called.append(video_path.name)
        return output_dir / f"{video_path.stem}.mp3"

    monkeypatch.setattr(helper, "find_video_files", fake_find_video_files)
    monkeypatch.setattr(helper, "process_one_video", fake_process_one_video)

    result = helper.run_batch(tmp_path, output_dir=tmp_path, workers=2)

    assert result == 0
    assert called == ["b.mp4"]


def test_unique_audio_path_avoids_overwrite(tmp_path):
    video_path = tmp_path / "lesson.mp4"
    (tmp_path / "lesson.mp3").write_text("done", encoding="utf-8")

    assert helper.unique_audio_path(tmp_path, video_path) == tmp_path / "lesson-2.mp3"
    assert helper.unique_audio_path(tmp_path, video_path, overwrite=True) == tmp_path / "lesson.mp3"
