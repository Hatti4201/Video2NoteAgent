# Development Tasks

## Purpose

This document tracks implementation tasks for Video Note Agent.

The current roadmap is local-first but cloud-ready.

---

# Phase 1 - YouTube Subtitle MVP

Status:

- [x] Completed

## Tasks

- [x] Accept YouTube URL input
- [x] Validate YouTube URLs
- [x] Download subtitles
- [x] Generate transcript text
- [x] Generate basic notes
- [x] Write local output
- [x] Handle invalid URLs with readable errors
- [x] Handle missing subtitles with readable errors
- [x] Add basic tests

---

# Phase 2 - Per-Video Output Workspace

Status:

- [x] Completed in current implementation

## Tasks

- [x] Create one folder per processed video
- [x] Use video title and date to create a safe folder name
- [x] Avoid overwriting previous video outputs
- [x] Write `metadata.json`
- [x] Include metadata foundation fields for multi-platform adapters
- [x] Write `01_raw_transcript.txt`
- [x] Write `02_formatted_transcript.md`
- [x] Write `03_cleaned_content.md`
- [x] Write `04_notes_outline.md`
- [x] Add tests for output folder creation and required files

---

# Phase 3 - AI Note Processing

Status:

- [x] Completed in current implementation

## Tasks

- [x] Generate formatted transcript from raw transcript
- [x] Generate cleaned content from transcript
- [x] Generate notes outline from transcript
- [x] Keep local files as source of truth
- [x] Keep rule-based fallback when AI processing fails
- [x] Read configured LLM provider from environment variables
- [x] Add tests for AI success and fallback behavior

---

# Phase 4 - Transcription Provider Layer

Status:

- [ ] In progress: implemented providers work; additional providers remain

## Local Video Inputs

- [x] `.mp4`
- [x] `.mov`
- [x] `.mkv`

## Future ASR Providers

- [x] Doubao Speech explicit audio URL transcription
- [x] Doubao Speech TOS-backed local audio transcription helper
- [x] Local faster-whisper transcription
- [x] Local Whisper API transcription
- [ ] Tencent ASR
- [ ] Alibaba ASR
- [ ] Deepgram
- [ ] AWS Transcribe

## Tasks

- [x] Add Doubao Speech ASR configuration from environment variables
- [x] Submit Doubao Speech ASR jobs from an audio URL
- [x] Poll Doubao Speech ASR result by task ID
- [x] Upload local audio files to private TOS for temporary ASR access
- [x] Generate presigned TOS GET URLs
- [x] Delete temporary TOS audio objects after ASR finishes
- [x] Keep TOS IAM AK/SK separate from Doubao Speech AppId/Access Token
- [x] Ensure Doubao Speech/TOS failures are readable
- [ ] Define shared transcription provider contract
- [ ] Ensure every provider returns transcript text
- [x] Keep downstream note pipeline provider-independent
- [x] Document required environment variables for implemented providers

`main.py` processes local video through faster-whisper or the configured local Whisper API.
The optional batch helper can process local video through Doubao/TOS, but Doubao is not yet
selectable for local video through `main.py`.

---

# Phase 5 - Output Adapter Layer

Status:

- [x] Adapter architecture implemented for current destinations
- [ ] Google Docs remains

## Destinations

- [x] Local Markdown
- [x] Feishu Docs
- [x] Notion
- [ ] Google Docs
- [x] Obsidian

## Tasks

- [x] Define adapter boundary for publishing generated local assets
- [x] Preserve local files when an adapter fails
- [x] Publish local Markdown output
- [x] Publish to Notion when configured
- [x] Publish Notion database page when configured
- [x] Publish to Feishu when configured
- [x] Publish Feishu Bitable record when configured
- [x] Publish to Obsidian when configured
- [ ] Add Google Docs adapter
- [x] Convert Feishu output to structured document blocks instead of raw Markdown

## Feishu Structured Block Tasks

- [x] Convert Heading 1
- [x] Convert Heading 2
- [x] Convert Heading 3
- [x] Convert Paragraph
- [x] Convert Bullet List
- [x] Convert Numbered List

---

# Phase 6 - Cloud Deployment

Status:

- [ ] Planned

## Tasks

- [ ] Define cloud task orchestration model
- [ ] Define ASR-by-API execution path
- [ ] Define output adapter publishing in cloud
- [ ] Define secret management requirements
- [ ] Keep home workstation optional
- [ ] Keep local workflow functional without cloud deployment

No cloud deployment is implemented in this documentation update.
