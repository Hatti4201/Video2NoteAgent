# PRD

## Purpose

This Product Requirements Document defines the goals, scope, requirements, roadmap, and success criteria for Video Note Agent.

## Project Name

Video Note Agent

## Overview

Video Note Agent is a local-first but cloud-ready personal tool that converts video content into transcripts and structured notes.

The user provides a video source.

The system automatically:

1. Retrieves subtitles or transcript content
2. Extracts transcript
3. Cleans transcript
4. Generates knowledge assets
5. Saves results as local source-of-truth files
6. Optionally publishes generated assets through output adapters

The core product objective is to capture knowledge from video content regardless of source.

All supported sources should converge into a common transcript layer before downstream processing.

The transcript is the primary system artifact because cleaned content, notes, summaries, and future integrations all depend on obtaining transcript text first.

Generated local files are the source of truth.

The long-term architecture should support optional cloud orchestration without making cloud deployment required for local usage.

External systems such as Notion, Feishu Docs, Google Docs, and Obsidian are optional publishing destinations.

The goal is to help users efficiently consume educational and informational content.

## Target Architecture

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

All video and ASR sources should converge into the transcript layer before downstream processing.

Cloud deployment is a future runtime option, not a requirement.

## Roadmap Summary

```text
Phase 1 - YouTube Subtitle MVP
Phase 2 - Per-Video Output Workspace
Phase 3 - AI Note Processing
Phase 4 - Transcription Provider Layer
Phase 5 - Output Adapter Layer
Phase 6 - Cloud Deployment
```

## Problem Statement

Many valuable videos contain useful information but are difficult to review later.

Users often:

- Watch long videos
- Forget important points
- Need searchable notes
- Need a clean transcript
- Need structured summaries

Manually creating notes is time-consuming.

The system should automate this process.

## Target User

Primary User:

- Single user
- Personal usage
- Technical background
- Uses online and local video content for learning

Current version is not intended for public users.

## MVP Goal

The MVP remains YouTube-only.

### Input

A YouTube video URL

### Output

```text
output/
└── <safe-video-folder-name>/
    ├── metadata.json
    ├── 01_raw_transcript.txt
    ├── 02_formatted_transcript.md
    ├── 03_cleaned_content.md
    └── 04_notes_outline.md
```

Generated notes should be readable and organized.

## User Flow

User runs:

```bash
python main.py <youtube_url>
```

Workflow:

1. System downloads subtitles
2. System extracts transcript
3. System cleans transcript
4. System generates notes
5. System saves files
6. User reads results

## Functional Requirements

### FR-1 Video Source Input

The MVP must accept:

- YouTube URL

Example:

```text
https://www.youtube.com/watch?v=xxxx
```

Future versions should support:

- YouTube URLs
- Local MP4 files
- Local MOV files
- Local MKV files
- ASR provider transcript generation

All source types should produce transcript text before using the existing notes pipeline.

### FR-2 Subtitle Retrieval

The system should:

- Detect available subtitles
- Download subtitles

Supported:

- English subtitles
- Chinese subtitles

If subtitles are unavailable:

Return an error message.

### FR-3 Transcript Generation

The system must create:

```text
output/<safe-video-folder-name>/01_raw_transcript.txt
```

Requirements:

- Plain text
- Human readable
- No timestamps
- No subtitle metadata

### FR-4 Note Generation

The system must create:

```text
output/<safe-video-folder-name>/04_notes_outline.md
```

Required Sections:

```markdown
# Executive Summary

# Key Takeaways

# Structured Outline

# Action Items
```

`03_cleaned_content.md` contains the Edited Transcript.

`04_notes_outline.md` contains distilled knowledge sections.

### FR-5 Output Storage

All outputs must be stored locally.

Directory:

```text
output/<safe-video-folder-name>/
```

Files:

```text
metadata.json
01_raw_transcript.txt
02_formatted_transcript.md
03_cleaned_content.md
04_notes_outline.md
```

`metadata.json` schema:

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

Unavailable metadata values should use empty strings or empty arrays.

### FR-6 Output Adapter Layer

Publishing destinations must be optional.

Local files remain the source of truth.

Future output adapters may include:

- Local Markdown
- Notion
- Feishu Docs
- Google Docs
- Obsidian

Adapter failures must not delete, corrupt, or prevent local output generation.

All publishing destinations must consume the same canonical local files:

- `metadata.json`
- `01_raw_transcript.txt`
- `02_formatted_transcript.md`
- `03_cleaned_content.md`
- `04_notes_outline.md`

Notion should use a database architecture when `NOTION_DATABASE_ID` is configured, with properties for Title, URL, Source, Author, Tags, Duration, Language, Status, Created At, Summary, and Processing Method. Each row should have a dedicated page body containing Summary, Key Topics, Action Items, Formatted Transcript, Cleaned Content, and Notes Outline. Parent-page publishing remains a fallback.

Obsidian should use YAML frontmatter generated from `metadata.json`.

Feishu should not receive raw Markdown. The Feishu adapter should convert generated notes into structured Feishu document blocks:

- Heading 1
- Heading 2
- Heading 3
- Paragraph
- Bullet List
- Numbered List

Feishu metadata should be rendered as a document header section.

Feishu should create a Bitable record with metadata and Doc URL when Bitable configuration is present.

### FR-7 Transcription Provider Layer

Future transcription providers should support:

- Local video files:
  - `.mp4`
  - `.mov`
  - `.mkv`
- ASR providers:
  - Volcengine
  - Tencent ASR
  - Alibaba ASR
  - Deepgram
  - AWS Transcribe

All providers must output transcript text for the common transcript layer.

Doubao Speech ASR is implemented for:

- Explicit audio URLs
- Local audio files uploaded temporarily to private Volcengine TOS

TOS is transport storage only. Audio objects should be deleted after ASR finishes.

TOS uses IAM AK/SK. Doubao Speech ASR uses old-console AppId and Access Token and must not use IAM AK/SK.

## Non-Functional Requirements

### Simplicity

The MVP should remain small and easy to understand.

### Local-First

No cloud services.

No external databases.

### Maintainability

Code should be organized into small modules.

Avoid unnecessary abstractions.

### Security

Only process user-provided video sources.

Do not access personal files outside the project workspace.

Do not access email accounts.

Do not access cloud storage accounts.

Do not execute arbitrary commands.

## Out of Scope

The following are explicitly excluded from MVP:

- Local video files
- Whisper
- Ollama
- Local LLM
- OpenAI API
- Claude API
- Telegram Bot
- Discord Bot
- Feishu Bot
- Notion Integration
- Docker
- Web UI
- Authentication
- Multi-user support

## Future Roadmap

### Phase 1 - YouTube + Subtitle

Status:

```text
Completed
```

Included:

- YouTube URL input
- Subtitle download
- Transcript generation
- Rule-based notes

### Phase 2 - Local Video Support + Whisper

Status:

```text
Completed
```

Additional Inputs:

```text
.mp4
.mov
.mkv
```

Workflow:

```text
Local Video
    ↓
Audio Extraction
    ↓
Whisper / faster-whisper
    ↓
Transcript
    ↓
Existing Notes Pipeline
```

Expected output remains:

```text
metadata.json
01_raw_transcript.txt
02_formatted_transcript.md
03_cleaned_content.md
04_notes_outline.md
```

### Phase 3 - Remote Private Ollama Notes

Status:

```text
Completed
```

- Ollama integration
- Remote private Ollama API support
- Improved note quality
- Better summaries
- Better action items

### Phase 4 - Output Adapter Architecture

- Define output adapter contract
- Treat local markdown files as the primary output
- Keep publishing destinations optional
- Ensure adapter failures do not break local output generation

### Phase 5 - Notion Adapter

- Create Notion pages automatically
- Store generated notes
- Return page URL

### Phase 6 - Additional Output Adapters

Status:

```text
Completed
```

Included:

- Obsidian

Future adapters:

- Feishu Docs
- Google Docs

### Phase 7 - Telegram Bot

Status:

```text
Completed
```

- Remote chat interface
- URL submission
- Allowed user ID control
- Status notifications
- Result delivery

### Phase 8 - Docker Deployment

- Dockerfile
- docker-compose
- Environment management

### Phase 9 - Windows Home Server Deployment

- WSL2 deployment
- Local model deployment
- Long-running service setup

### Phase 10 - Secure Remote Access

- Tailscale
- ZeroTier
- Cloudflare Tunnel

### Future - Personal Knowledge System

Additional Inputs:

```text
PDF
Podcast
Web Article
Meeting Recording
```

Additional Outputs:

```text
Knowledge Base
Daily Digest
Topic Collections
```

### Future - Personal Assistant Ecosystem

Specialized Agents:

```text
Video Agent
Document Agent
Calendar Agent
Email Agent
```

## Success Criteria

The project is successful when:

### Input

```bash
python main.py <youtube_url>
```

### Output

```text
output/
└── <safe-video-folder-name>/
    ├── metadata.json
    ├── 01_raw_transcript.txt
    ├── 02_formatted_transcript.md
    ├── 03_cleaned_content.md
    └── 04_notes_outline.md
```

All files are generated successfully and contain useful content.

The workflow completes without manual intervention.

The generated notes are readable, organized, and useful for future reference.
