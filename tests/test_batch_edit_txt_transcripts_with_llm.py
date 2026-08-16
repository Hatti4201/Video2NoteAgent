from pathlib import Path

from app.utils import VideoNoteError
from scripts import batch_edit_txt_transcripts_with_llm as helper


SAMPLE_NAME = (
    "【黑马程序员】—黑马程序员2026最新AI版天机学堂全套视频课程，Spring AI+多智能体架构全栈实战项目，"
    "AI+Java微服务主流实战项目进阶一套通关 - P1【01.天机学堂AI助手智能体课程导学】—【2026-04-28】-中文.txt"
)


def test_extract_transcript_file_uses_part_number_and_unique_title(tmp_path):
    path = tmp_path / SAMPLE_NAME
    path.write_text("课程内容", encoding="utf-8")

    transcript_file = helper.extract_transcript_file(path)

    assert transcript_file.sequence == 1
    assert transcript_file.title == "天机学堂AI助手智能体课程导学"
    assert transcript_file.output_base_name() == "黑马Java+AI-1.天机学堂AI助手智能体课程导学"


def test_output_path_uses_lesson_name(tmp_path):
    transcript_file = helper.TranscriptFile(
        path=tmp_path / "lesson.txt",
        sequence=2,
        title="基本对话与课程咨询-熟悉项目-导入虚拟机",
    )

    path = helper.output_path(tmp_path / "out", transcript_file)

    assert path.name == "黑马Java+AI-2.基本对话与课程咨询-熟悉项目-导入虚拟机.md"


def test_output_path_accepts_custom_prefix(tmp_path):
    transcript_file = helper.TranscriptFile(
        path=tmp_path / "lesson.txt",
        sequence=1,
        title="天机学堂AI助手智能体课程导学",
    )

    path = helper.output_path(tmp_path / "out", transcript_file, prefix="黑马JAVA+AI")

    assert path.name == "黑马JAVA+AI-1.天机学堂AI助手智能体课程导学.md"


def test_process_one_calls_llm_and_writes_single_reformatted_output(monkeypatch, tmp_path):
    source = tmp_path / SAMPLE_NAME
    source.write_text("这里是原始文稿。需要减少口语化。", encoding="utf-8")
    transcript_file = helper.extract_transcript_file(source)
    calls = []

    def fake_generate(title, transcript):
        calls.append((title, transcript))
        return "# 编辑后文本\n\n整理后的正文。\n\n# 大纲\n\n- 主题\n\n# 关键要点\n\n- 要点"

    monkeypatch.setattr(helper, "generate_reformatted_transcript", fake_generate)

    target_path = helper.process_one(transcript_file, tmp_path / "out", prefix="黑马JAVA+AI")

    assert calls == [("天机学堂AI助手智能体课程导学", "这里是原始文稿。需要减少口语化。")]
    assert target_path.name == "黑马JAVA+AI-1.天机学堂AI助手智能体课程导学.md"
    content = target_path.read_text(encoding="utf-8")
    assert content.startswith("# 编辑后文本")
    assert "# 大纲" in content
    assert "# 关键要点" in content
    assert "Source:" not in content


def test_run_batch_skips_existing_output(monkeypatch, tmp_path):
    source = tmp_path / SAMPLE_NAME
    source.write_text("这里是原始文稿。", encoding="utf-8")
    transcript_file = helper.extract_transcript_file(source)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    target_path = helper.output_path(output_dir, transcript_file)
    target_path.write_text("done", encoding="utf-8")
    calls = []

    def fake_generate(title, transcript):
        calls.append((title, transcript))
        return "edited"

    monkeypatch.setattr(helper, "generate_reformatted_transcript", fake_generate)

    result = helper.run_batch(tmp_path, output_dir=output_dir)

    assert result == 0
    assert calls == []


def test_process_one_rejects_empty_transcript(tmp_path):
    source = tmp_path / SAMPLE_NAME
    source.write_text("   ", encoding="utf-8")
    transcript_file = helper.extract_transcript_file(source)

    try:
        helper.process_one(transcript_file, tmp_path / "out")
    except VideoNoteError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("Expected VideoNoteError")
