# Implementation Plan

## Purpose

This document defines the product roadmap for Video Note Agent.

The roadmap is local-first but cloud-ready.

The current implementation must keep working locally. Cloud deployment, cloud task orchestration, and ASR APIs are future architecture targets and are not implemented in this phase.

---

# Product Architecture

```text
Video Source
    ↓
Transcript Layer
    ↓
AI Note Processing
    ↓
Per-Video Local Workspace
    ↓
Output Adapter Layer
    ↓
Optional Cloud Orchestration
```

Core rule:

```text
Local files are always the source of truth.
```

External systems are optional destinations. The application must still work when external systems are unavailable.

---

# Phase 1 - YouTube Subtitle MVP

## Goal

Generate basic notes from a YouTube video that already has subtitles.

## Included

- YouTube URL input
- Subtitle download
- Transcript generation
- Basic notes
- Local output

## Output

```text
output/
```

## Status

- [x] Completed

---

# Phase 2 - Per-Video Output Workspace

## Goal

Create one local workspace folder per processed video.

## Output

```text
output/
└── <safe-video-folder-name>/
    ├── metadata.json
    ├── 01_raw_transcript.txt
    ├── 02_formatted_transcript.md
    ├── 03_cleaned_content.md
    └── 04_notes_outline.md
```

## Requirements

- Use video title and date to create a safe folder name.
- Avoid overwriting previous videos.
- Store metadata for the processed source.
- Keep all generated artifacts in the per-video workspace.
- Treat `metadata.json` and the four generated content files as the canonical source of truth for all output adapters.

## Metadata Schema

`metadata.json` must contain:

```json
{
  "title": "",
  "url": "",
  "source": "",
  "author": "",
  "duration": "",
  "language": "",
  "tags": [],
  "status": "Processed",
  "created_at": "",
  "summary": "",
  "processing_method": ""
}
```

Unavailable values should be stored as empty strings or empty arrays.

## Status

- [x] Completed in current implementation

---

# Phase 3 - AI Note Processing

## Goal

Process transcript text into derived knowledge artifacts.

## Derived Outputs

- `02_formatted_transcript.md`
- `03_cleaned_content.md`
- `04_notes_outline.md`

## Requirements

- Preserve the raw transcript.
- Use local files as the source of truth.
- Use configured AI providers only after transcript generation is complete.
- Fall back to rule-based output when AI processing fails.
- Do not make external systems required for local output generation.

## Status

- [x] Completed in current implementation

---

# Phase 4 - Transcription Provider Layer

## Goal

Define a replaceable transcription layer for future source and ASR expansion.

## Future Local Video Sources

- `.mp4`
- `.mov`
- `.mkv`

## ASR Providers

- Doubao Speech ASR: implemented for explicit audio URLs and TOS-backed local audio files
- Tencent ASR
- Alibaba ASR
- Deepgram
- AWS Transcribe

## Requirements

- All transcription providers must produce transcript text for the same downstream pipeline.
- Provider failures must return readable errors.
- ASR provider credentials must be explicit environment configuration.
- TOS temporary audio storage must not become permanent user storage.

## Doubao Speech ASR Provider

The first implemented ASR provider is:

```text
Doubao Speech - Big Model Recording File Recognition
```

This provider uses a two-step workflow:

```text
Submit task with audio URL
    ↓
Receive task ID
    ↓
Query result by task ID
    ↓
Return transcript text
```

The API requires an audio URL that Doubao Speech can access. Local files are not enough by themselves.

The implementation supports:

- Explicit audio URL transcription
- Local audio file upload to private Volcengine TOS
- YouTube audio fallback when supported subtitles are unavailable
- 1-hour presigned GET URL generation
- ASR polling by task ID
- Best-effort TOS object cleanup after ASR finishes

Credential boundaries:

- Volcengine TOS uses IAM AK/SK.
- Doubao Speech ASR uses old-console AppId and Access Token.
- Doubao Speech ASR must not use IAM AK/SK.
- Doubao Speech ASR must not use `open.volcengineapi.com`, `Action=SubmitRecognitionTask`, `Version=2023-08-01`, or HMAC-SHA256 signing.

TOS object key format:

```text
audio/{yyyy-mm-dd}/{uuid}.{ext}
```

Planned environment variables:

```text
TRANSCRIPTION_PROVIDER=doubao
DOUBAO_ASR_APP_ID=2614672586
DOUBAO_ASR_ACCESS_TOKEN=
DOUBAO_ASR_RESOURCE_ID=volc.seedasr.auc
DOUBAO_ASR_SUBMIT_URL=https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit
DOUBAO_ASR_QUERY_URL=https://openspeech.bytedance.com/api/v3/auc/bigmodel/query
DOUBAO_ASR_LANGUAGE=zh-CN
DOUBAO_ASR_AUDIO_FORMAT=mp3
DOUBAO_ASR_ENABLE_ITN=true
DOUBAO_ASR_ENABLE_PUNC=true
DOUBAO_ASR_ENABLE_DDC=true
DOUBAO_ASR_SHOW_UTTERANCES=true
VOLCENGINE_ACCESS_KEY_ID=
VOLCENGINE_SECRET_ACCESS_KEY=
TOS_BUCKET=nika-mnemo
TOS_REGION=cn-beijing
TOS_ENDPOINT=tos-cn-beijing.volces.com
```

## Status

- [ ] In progress
- [x] Doubao Speech explicit audio URL path implemented
- [x] Doubao Speech TOS temporary audio upload path implemented
- [x] YouTube no-subtitle fallback to temporary audio plus Doubao Speech ASR
- [ ] Local video extraction into ASR is not yet wired into the main pipeline

---

# Phase 5 - Output Adapter Layer

## Goal

Publish generated local knowledge assets to optional external destinations.

## Output Destinations

- Local Markdown
- Feishu Docs
- Notion
- Google Docs
- Obsidian

## Requirements

- Local files remain the source of truth.
- Adapter failures must not prevent local file generation.
- Future adapters must be replaceable without changing transcript or note generation logic.
- All adapters must consume `metadata.json` and the four canonical note assets.

## Obsidian Design Note

Obsidian notes should use YAML frontmatter generated from `metadata.json`:

```markdown
---
title:
url:
source:
author:
duration:
language:
tags:
status:
created_at:
processing_method:
---
```

## Notion Design Note

Notion should use a database architecture.

When `NOTION_DATABASE_ID` is configured, it is the preferred publishing target. `NOTION_PARENT_PAGE_ID` remains a fallback for page-under-page publishing.

Database properties:

- Title
- URL
- Source
- Author
- Tags
- Duration
- Language
- Status
- Created At
- Summary
- Processing Method

Each database row should have a dedicated page. The page body should contain:

- Summary
- Key Topics
- Action Items
- Formatted Transcript
- Cleaned Content
- Notes Outline

## Feishu Design Note

Feishu should not receive raw Markdown.

Feishu should create documents under `FEISHU_VIDEO_NOTES_FOLDER_TOKEN` when configured, falling back to `FEISHU_PARENT_FOLDER_TOKEN`.

The Feishu adapter should convert generated notes into structured Feishu document blocks:

- Heading 1
- Heading 2
- Heading 3
- Paragraph
- Bullet List
- Numbered List

Metadata should be rendered as a document header section.

When `FEISHU_BITABLE_APP_TOKEN` and `FEISHU_BITABLE_TABLE_ID` are configured, Feishu should also create one Bitable record with metadata fields and `Doc URL`.

## Status

- [ ] Planned architecture
- [x] Some adapters exist in the current implementation

---

# Phase 6 - Cloud Deployment

## Goal

Allow the system to run as a cloud-ready workflow while preserving local-first behavior.

## Future Scope

- Task orchestration in cloud
- ASR by API
- Publishing by adapters
- Home workstation optional

## Requirements

- Cloud deployment must not become required for local usage.
- Secrets must be stored in environment variables or managed secret stores.
- Cloud services must not bypass local source-of-truth output.
- No cloud deployment is implemented as part of this documentation update.

## Status

- [ ] Planned

---

# Current Implementation Notes

The implementation currently includes capabilities that were added during earlier iteration, including configurable LLM processing, optional output adapters, Telegram input, and Docker packaging.

These capabilities should be preserved, but future planning should use the six-phase roadmap above.
