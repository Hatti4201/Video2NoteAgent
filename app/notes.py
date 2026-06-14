from pathlib import Path
import re

from app.utils import collapse_whitespace, detect_content_language, write_text_file


SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s*")
ACTION_WORDS = (
    "should",
    "need to",
    "must",
    "try",
    "practice",
    "remember",
    "use",
    "avoid",
    "make sure",
    "应该",
    "需要",
    "必须",
    "尝试",
    "练习",
    "记住",
    "使用",
    "避免",
    "确保",
)
ACTION_PATTERNS = [
    re.compile(
        re.escape(word)
        if any("\u3400" <= character <= "\u9fff" for character in word)
        else rf"(?<!\w){re.escape(word)}(?!\w)",
        re.IGNORECASE,
    )
    for word in ACTION_WORDS
]

HEADINGS = {
    "english": {
        "executive_summary": "Executive Summary",
        "key_takeaways": "Key Takeaways",
        "structured_outline": "Structured Outline",
        "action_items": "Action Items",
        "edited_transcript": "Edited Transcript",
        "fallback_note": "Rule-based fallback: LLM transcript editing was unavailable.",
    },
    "chinese": {
        "executive_summary": "执行摘要",
        "key_takeaways": "关键要点",
        "structured_outline": "结构化大纲",
        "action_items": "行动项",
        "edited_transcript": "编辑后文本",
        "fallback_note": "规则回退：LLM 文本编辑暂时不可用。",
    },
}


def _headings(transcript: str) -> dict:
    return HEADINGS[detect_content_language(transcript)]


def _sentences(transcript: str) -> list[str]:
    normalized = collapse_whitespace(transcript)
    return [sentence.strip() for sentence in SENTENCE_RE.split(normalized) if sentence.strip()]


def generate_summary(transcript: str) -> str:
    sentences = _sentences(transcript)
    if not sentences:
        return "No transcript content available."
    return " ".join(sentences[:3])


def generate_key_points(transcript: str) -> list[str]:
    sentences = _sentences(transcript)
    points = sentences[:3]

    while len(points) < 3:
        points.append("Review the transcript for additional details.")

    return points[:3]


def generate_action_items(transcript: str) -> list[str]:
    sentences = _sentences(transcript)
    actions = [
        sentence
        for sentence in sentences
        if any(pattern.search(sentence) for pattern in ACTION_PATTERNS)
    ]

    if not actions:
        return ["No explicit action items found."]

    return actions[:5]


def generate_notes(title: str, transcript: str, output_path: Path | None = None) -> str:
    summary = generate_summary(transcript)
    key_points = generate_key_points(transcript)
    action_items = generate_action_items(transcript)
    explicit_actions = action_items != ["No explicit action items found."]
    headings = _headings(transcript)

    lines = [
        f"# {headings['executive_summary']}",
        "",
        summary,
        "",
        f"# {headings['key_takeaways']}",
        "",
        *[f"- {point}" for point in key_points],
        "",
        f"# {headings['structured_outline']}",
        "",
        f"1. {title}",
        *[f"   - {point}" for point in key_points],
        "",
    ]

    if explicit_actions:
        lines.extend(
            [
                f"# {headings['action_items']}",
                "",
                *[f"- [ ] {item}" for item in action_items],
                "",
            ]
        )

    markdown = "\n".join(lines)

    output_path = output_path or Path("output/notes.md")
    write_text_file(output_path, markdown)
    return markdown


def generate_edited_transcript_fallback(
    title: str,
    transcript: str,
    output_path: Path | None = None,
) -> str:
    headings = _headings(transcript)
    markdown = "\n".join(
        [
            f"# {headings['edited_transcript']}",
            "",
            f"## {title}",
            "",
            collapse_whitespace(transcript),
            "",
        ]
    )

    if output_path:
        write_text_file(output_path, markdown)

    return markdown


def generate_cleaned_content_fallback(
    title: str,
    transcript: str,
    output_path: Path | None = None,
) -> str:
    headings = _headings(transcript)
    markdown = "\n".join(
        [
            f"# {headings['edited_transcript']}",
            "",
            f"## {title}",
            "",
            f"> {headings['fallback_note']}",
            "",
            collapse_whitespace(transcript),
            "",
        ]
    )

    if output_path:
        write_text_file(output_path, markdown)

    return markdown
